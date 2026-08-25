from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class InactiveZone:
    zone: str
    state: str
    timestamp: str
    operator: str
    reason: str
    transaction_id: str
    location: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class ZoneInventory:
    """Read-only inventory of disabled and quarantined zones."""

    def __init__(
        self,
        disabled_root: Path = Path("/var/lib/zonectl/disabled-zones"),
        quarantine_root: Path = Path("/var/lib/zonectl/quarantine"),
        disable_manifest_directory: Path = Path(
            "/var/backups/zonectl-zone-disable/manifests"
        ),
    ) -> None:
        self.disabled_root = disabled_root
        self.quarantine_root = quarantine_root
        self.disable_manifest_directory = disable_manifest_directory

    def records(self) -> list[InactiveZone]:
        records = [*self._disabled(), *self._quarantined()]
        return sorted(
            records,
            key=lambda item: (item.timestamp, item.zone, item.location),
            reverse=True,
        )

    def _disabled(self) -> list[InactiveZone]:
        if not self.disabled_root.is_dir():
            return []
        records: list[InactiveZone] = []
        for directory in sorted(self.disabled_root.iterdir()):
            if not directory.is_dir():
                continue
            zone = directory.name
            declaration = directory / f"{zone}.conf"
            if not declaration.is_file():
                continue
            manifest = self._latest_disable_manifest(zone)
            records.append(
                self._record(
                    zone=zone,
                    state="DISABLED",
                    location=declaration,
                    manifest=manifest,
                    fallback_timestamp=self._mtime(declaration),
                )
            )
        return records

    def _quarantined(self) -> list[InactiveZone]:
        if not self.quarantine_root.is_dir():
            return []
        records: list[InactiveZone] = []
        for manifest_path in sorted(
            self.quarantine_root.glob("*/*/manifest.json")
        ):
            manifest = self._load_json(manifest_path)
            if not manifest:
                continue
            zone = str(manifest.get("zone") or manifest_path.parents[1].name)
            records.append(
                self._record(
                    zone=zone,
                    state="QUARANTINED",
                    location=manifest_path.parent,
                    manifest=manifest,
                    fallback_timestamp=self._mtime(manifest_path),
                )
            )
        return records

    def _latest_disable_manifest(self, zone: str) -> dict[str, object]:
        if not self.disable_manifest_directory.is_dir():
            return {}
        candidates: list[tuple[str, dict[str, object]]] = []
        for path in self.disable_manifest_directory.glob("*.json"):
            payload = self._load_json(path)
            if (
                payload.get("zone") == zone
                and payload.get("status") == "DISABLED"
            ):
                candidates.append(
                    (str(payload.get("saved_at") or self._mtime(path)), payload)
                )
        return max(candidates, default=("", {}), key=lambda item: item[0])[1]

    @staticmethod
    def _record(
        *,
        zone: str,
        state: str,
        location: Path,
        manifest: dict[str, object],
        fallback_timestamp: str,
    ) -> InactiveZone:
        return InactiveZone(
            zone=zone,
            state=state,
            timestamp=str(
                manifest.get("created_at")
                or manifest.get("saved_at")
                or fallback_timestamp
            ),
            operator=str(manifest.get("operator") or "-"),
            reason=str(manifest.get("reason") or "-"),
            transaction_id=str(manifest.get("transaction_id") or "-"),
            location=str(location),
        )

    @staticmethod
    def _load_json(path: Path) -> dict[str, object]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        return {str(key): value for key, value in payload.items()}

    @staticmethod
    def _mtime(path: Path) -> str:
        return datetime.fromtimestamp(
            path.stat().st_mtime, timezone.utc
        ).astimezone().isoformat(timespec="seconds")
