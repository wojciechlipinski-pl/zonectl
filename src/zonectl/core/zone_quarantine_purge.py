from __future__ import annotations

import getpass
import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .zone_quarantine_retention import QuarantineRetentionAuditor


@dataclass(frozen=True, slots=True)
class QuarantinePurgePlan:
    zone: str
    package: Path
    package_id: str
    retention_days: int
    age_days: int
    reason: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["package"] = str(self.package)
        return payload


@dataclass(slots=True)
class QuarantinePurgeStep:
    name: str
    ok: bool
    message: str


@dataclass(slots=True)
class QuarantinePurgeResult:
    transaction_id: str
    zone: str
    package: str
    status: str
    committed: bool = False
    manifest: str | None = None
    steps: list[QuarantinePurgeStep] = field(default_factory=list)


class QuarantinePurgeError(RuntimeError):
    """A quarantine package does not satisfy permanent-purge gates."""


class QuarantinePurgeTransaction:
    """Permanently remove one verified package after explicit confirmations."""

    def __init__(
        self,
        *,
        quarantine_root: Path = Path("/var/lib/zonectl/quarantine"),
        audit_directory: Path = Path("/var/backups/zonectl-quarantine-purge/manifests"),
        retention_days: int = 90,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.quarantine_root = quarantine_root
        self.audit_directory = audit_directory
        self.retention_days = retention_days
        self._now = now or (lambda: datetime.now(timezone.utc))

    def plan(self, zone: str, package: Path, *, reason: str) -> QuarantinePurgePlan:
        name = zone.strip().rstrip(".").casefold()
        if not name or not reason.strip():
            raise QuarantinePurgeError("wymagana jest nazwa strefy i przyczyna")
        try:
            root = self.quarantine_root.resolve(strict=True)
            resolved = package.resolve(strict=True)
        except OSError as exc:
            raise QuarantinePurgeError(f"nie można odczytać pakietu: {exc}") from exc
        if resolved.parent.parent != root or resolved.parent.name != name:
            raise QuarantinePurgeError("pakiet nie jest bezpośrednim pakietem wskazanej strefy")
        entries = {item.name for item in resolved.iterdir()}
        if entries != {"manifest.json", "zone.db", "zone.conf"}:
            raise QuarantinePurgeError("pakiet ma nieoczekiwaną lub niekompletną zawartość")
        record = QuarantineRetentionAuditor(
            root, self.retention_days, now=self._now
        ).inspect_package(resolved)
        if record.state != "ELIGIBLE" or record.age_days is None:
            raise QuarantinePurgeError(
                f"pakiet nie kwalifikuje się do usunięcia: {record.state} — {record.reason}"
            )
        if record.zone != name:
            raise QuarantinePurgeError("manifest nie opisuje wskazanej strefy")
        return QuarantinePurgePlan(
            name, resolved, resolved.name, self.retention_days,
            record.age_days, reason.strip()
        )

    def apply(
        self,
        plan: QuarantinePurgePlan,
        *,
        commit: bool = False,
        confirmation: str | None = None,
        package_confirmation: str | None = None,
    ) -> QuarantinePurgeResult:
        txid = (
            self._now().astimezone().strftime("%Y%m%d-%H%M%S")
            + f"-purge-{plan.zone}-{uuid.uuid4().hex[:8]}"
        )
        result = QuarantinePurgeResult(txid, plan.zone, str(plan.package), "DRY-RUN")
        if not commit:
            result.steps.append(QuarantinePurgeStep("dry-run", True, "Nie usunięto pakietu"))
            return result
        if (confirmation or "").strip().rstrip(".").casefold() != plan.zone:
            result.status = "CONFIRMATION-REQUIRED"
            result.steps.append(QuarantinePurgeStep("zone-confirmation", False, "potwierdzenie strefy jest niezgodne"))
            return result
        if (package_confirmation or "").strip() != plan.package_id:
            result.status = "CONFIRMATION-REQUIRED"
            result.steps.append(QuarantinePurgeStep("package-confirmation", False, "potwierdzenie identyfikatora pakietu jest niezgodne"))
            return result

        # Rebuild the plan immediately before the irreversible operation.
        try:
            fresh = self.plan(plan.zone, plan.package, reason=plan.reason)
        except QuarantinePurgeError as exc:
            result.status = "BLOCKED"
            result.steps.append(QuarantinePurgeStep("preflight", False, str(exc)))
            return result

        audit = self.audit_directory / f"{txid}.json"
        payload = {
            "transaction_id": txid,
            "zone": fresh.zone,
            "package_id": fresh.package_id,
            "package": str(fresh.package),
            "status": "PREPARED",
            "reason": fresh.reason,
            "operator": getpass.getuser(),
            "retention_days": fresh.retention_days,
            "age_days": fresh.age_days,
            "created_at": self._now().astimezone().isoformat(timespec="seconds"),
        }
        try:
            self._write_manifest(audit, payload)
            result.manifest = str(audit)
            result.steps.append(QuarantinePurgeStep("audit-manifest", True, str(audit)))
            for name in ("zone.db", "zone.conf", "manifest.json"):
                (fresh.package / name).unlink()
            fresh.package.rmdir()
            try:
                fresh.package.parent.rmdir()
            except OSError:
                pass
            payload["status"] = "PURGED"
            payload["completed_at"] = self._now().astimezone().isoformat(timespec="seconds")
            self._write_manifest(audit, payload)
            result.status = "PURGED"
            result.committed = True
            result.steps.append(QuarantinePurgeStep("purge", True, "Pakiet trwale usunięto"))
        except Exception as exc:
            payload["status"] = "PURGE-FAILED"
            payload["error"] = str(exc)
            try:
                self._write_manifest(audit, payload)
            except Exception:
                pass
            result.status = "PURGE-FAILED"
            result.steps.append(QuarantinePurgeStep("purge", False, str(exc)))
        return result

    @staticmethod
    def _write_manifest(path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o640)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
