from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


def format_days_pl(value: int) -> str:
    """Return a compact Polish day count used by retention reports."""
    return f"{value} dzień" if value == 1 else f"{value} dni"


@dataclass(frozen=True, slots=True)
class QuarantineRetentionRecord:
    zone: str
    transaction_id: str
    created_at: str
    age_days: int | None
    retention_days: int
    state: str
    reason: str
    package: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class QuarantineRetentionAuditor:
    """Build a read-only, integrity-aware quarantine retention plan."""

    def __init__(
        self,
        quarantine_root: Path = Path("/var/lib/zonectl/quarantine"),
        retention_days: int = 90,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if retention_days < 1:
            raise ValueError("okres retencji musi wynosić co najmniej 1 dzień")
        self.quarantine_root = quarantine_root
        self.retention_days = retention_days
        self._now = now or (lambda: datetime.now(timezone.utc))

    def records(self) -> list[QuarantineRetentionRecord]:
        if not self.quarantine_root.is_dir():
            return []
        records = [
            self._inspect(path)
            for path in sorted(self.quarantine_root.glob("*/*/manifest.json"))
        ]
        return sorted(records, key=lambda item: (item.zone, item.created_at, item.package))

    def inspect_package(self, package: Path) -> QuarantineRetentionRecord:
        """Inspect one direct child package without changing it."""
        manifest = package / "manifest.json"
        if not manifest.is_file():
            return self._blocked(package, package.parent.name, "brak pliku manifest.json")
        return self._inspect(manifest)

    def _inspect(self, manifest_path: Path) -> QuarantineRetentionRecord:
        package = manifest_path.parent
        fallback_zone = package.parent.name
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return self._blocked(package, fallback_zone, f"niepoprawny manifest: {exc}")
        if not isinstance(payload, dict):
            return self._blocked(package, fallback_zone, "manifest nie jest obiektem JSON")

        zone = str(payload.get("zone") or fallback_zone)
        transaction_id = str(payload.get("transaction_id") or "-")
        created_text = str(payload.get("created_at") or "")
        if payload.get("status") != "QUARANTINED":
            return self._blocked(package, zone, "manifest nie ma stanu QUARANTINED", transaction_id, created_text)
        if zone != fallback_zone:
            return self._blocked(package, zone, "nazwa strefy nie zgadza się ze ścieżką pakietu", transaction_id, created_text)
        if package.is_symlink() or manifest_path.is_symlink():
            return self._blocked(package, zone, "pakiet lub manifest jest dowiązaniem symbolicznym", transaction_id, created_text)

        try:
            created = datetime.fromisoformat(created_text)
            if created.tzinfo is None:
                raise ValueError("brak strefy czasowej")
            created = created.astimezone(timezone.utc)
        except ValueError as exc:
            return self._blocked(package, zone, f"niepoprawna data utworzenia: {exc}", transaction_id, created_text)

        integrity_error = self._integrity_error(package, payload.get("files"))
        if integrity_error:
            return self._blocked(package, zone, integrity_error, transaction_id, created_text)

        age = self._now().astimezone(timezone.utc) - created
        if age.total_seconds() < 0:
            return self._blocked(package, zone, "data utworzenia leży w przyszłości", transaction_id, created_text)
        age_days = age.days
        eligible = age_days >= self.retention_days
        return QuarantineRetentionRecord(
            zone=zone,
            transaction_id=transaction_id,
            created_at=created_text,
            age_days=age_days,
            retention_days=self.retention_days,
            state="ELIGIBLE" if eligible else "RETAIN",
            reason=(
                "okres retencji minął; kandydat do osobno zatwierdzanej operacji"
                if eligible
                else f"pozostało {format_days_pl(self.retention_days - age_days)} retencji"
            ),
            package=str(package),
        )

    @staticmethod
    def _integrity_error(package: Path, files: object) -> str | None:
        if not isinstance(files, dict) or not files:
            return "manifest nie zawiera sum kontrolnych plików"
        for name, expected in files.items():
            if not isinstance(name, str) or Path(name).name != name:
                return "manifest zawiera niedozwoloną nazwę pliku"
            path = package / name
            if path.is_symlink() or not path.is_file():
                return f"brak pliku {name}"
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if not isinstance(expected, str) or actual.casefold() != expected.casefold():
                return f"niezgodna suma SHA-256 pliku {name}"
        return None

    def _blocked(
        self,
        package: Path,
        zone: str,
        reason: str,
        transaction_id: str = "-",
        created_at: str = "-",
    ) -> QuarantineRetentionRecord:
        return QuarantineRetentionRecord(
            zone=zone,
            transaction_id=transaction_id,
            created_at=created_at or "-",
            age_days=None,
            retention_days=self.retention_days,
            state="BLOCKED",
            reason=reason,
            package=str(package),
        )
