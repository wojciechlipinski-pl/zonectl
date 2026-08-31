"""Guarded permanent deletion of eligible quarantine packages."""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import tarfile
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .zone_quarantine_retention import QuarantineRetentionAuditor


@dataclass(frozen=True, slots=True)
class QuarantinePurgePlan:
    """Immutable, verified plan for one package purge."""

    zone: str
    package: Path
    package_id: str
    retention_days: int
    age_days: int
    reason: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-ready representation."""
        payload = asdict(self)
        payload["package"] = str(self.package)
        return payload


@dataclass(slots=True)
class QuarantinePurgeStep:
    """One observable step of a purge transaction."""

    name: str
    ok: bool
    message: str


@dataclass(slots=True)
class QuarantinePurgeResult:
    """Final state and audit details of a purge attempt."""

    transaction_id: str
    zone: str
    package: str
    status: str
    committed: bool = False
    rolled_back: bool = False
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
        staging_root: Path = Path("/var/lib/zonectl/purge-staging"),
        retention_days: int = 90,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.quarantine_root = quarantine_root
        self.audit_directory = audit_directory
        self.staging_root = staging_root
        self.retention_days = retention_days
        self._now = now or (lambda: datetime.now(timezone.utc))

    def plan(self, zone: str, package: Path, *, reason: str) -> QuarantinePurgePlan:
        """Validate retention, location, contents and integrity without changes."""
        name = zone.strip().rstrip(".").casefold()
        if not name or not reason.strip():
            raise QuarantinePurgeError("wymagana jest nazwa strefy i przyczyna")
        try:
            root = self.quarantine_root.resolve(strict=True)
            resolved = package.resolve(strict=True)
        except OSError as exc:
            raise QuarantinePurgeError(f"nie można odczytać pakietu: {exc}") from exc
        if resolved.parent.parent != root or resolved.parent.name != name:
            raise QuarantinePurgeError(
                "pakiet nie jest bezpośrednim pakietem wskazanej strefy"
            )
        entries = {item.name for item in resolved.iterdir()}
        if entries != {"manifest.json", "zone.db", "zone.conf"}:
            raise QuarantinePurgeError(
                "pakiet ma nieoczekiwaną lub niekompletną zawartość"
            )
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
            name,
            resolved,
            resolved.name,
            self.retention_days,
            record.age_days,
            reason.strip(),
        )

    def apply(
        self,
        plan: QuarantinePurgePlan,
        *,
        commit: bool = False,
        confirmation: str | None = None,
        package_confirmation: str | None = None,
    ) -> QuarantinePurgeResult:
        """Run dry-run or a multiply confirmed permanent purge transaction."""
        txid = (
            self._now().astimezone().strftime("%Y%m%d-%H%M%S")
            + f"-purge-{plan.zone}-{uuid.uuid4().hex[:8]}"
        )
        result = QuarantinePurgeResult(txid, plan.zone, str(plan.package), "DRY-RUN")
        if not commit:
            result.steps.append(
                QuarantinePurgeStep("dry-run", True, "Nie usunięto pakietu")
            )
            return result
        if (confirmation or "").strip().rstrip(".").casefold() != plan.zone:
            result.status = "CONFIRMATION-REQUIRED"
            result.steps.append(
                QuarantinePurgeStep(
                    "zone-confirmation", False, "potwierdzenie strefy jest niezgodne"
                )
            )
            return result
        if (package_confirmation or "").strip() != plan.package_id:
            result.status = "CONFIRMATION-REQUIRED"
            result.steps.append(
                QuarantinePurgeStep(
                    "package-confirmation",
                    False,
                    "potwierdzenie identyfikatora pakietu jest niezgodne",
                )
            )
            return result

        # Rebuild the plan immediately before the irreversible operation.
        try:
            fresh = self.plan(plan.zone, plan.package, reason=plan.reason)
        except QuarantinePurgeError as exc:
            result.status = "BLOCKED"
            result.steps.append(QuarantinePurgeStep("preflight", False, str(exc)))
            return result

        audit = self.audit_directory / f"{txid}.json"
        staged = self.staging_root / f"{txid}.package"
        recovery = self.staging_root / f"{txid}.recovery.tar"
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
            "staging_path": str(staged),
            "recovery_archive": str(recovery),
        }
        moved = False
        recovery_created = False
        try:
            self._write_manifest(audit, payload)
            result.manifest = str(audit)
            result.steps.append(QuarantinePurgeStep("audit-manifest", True, str(audit)))
            self.staging_root.mkdir(parents=True, exist_ok=True, mode=0o750)
            if self.staging_root.stat().st_dev != fresh.package.parent.stat().st_dev:
                raise RuntimeError(
                    "katalog staging nie znajduje się na tym samym systemie plików"
                )
            if staged.exists() or recovery.exists():
                raise RuntimeError("docelowe artefakty staging już istnieją")
            os.replace(fresh.package, staged)
            moved = True
            payload["status"] = "STAGED"
            self._write_manifest(audit, payload)
            result.steps.append(QuarantinePurgeStep("stage", True, str(staged)))

            self._create_recovery_archive(staged, recovery)
            recovery_created = True
            payload["recovery_sha256"] = self._sha256(recovery)
            payload["status"] = "RECOVERY-VERIFIED"
            self._write_manifest(audit, payload)
            result.steps.append(
                QuarantinePurgeStep("recovery-archive", True, str(recovery))
            )

            self._remove_staged_package(staged)
            try:
                fresh.package.parent.rmdir()
            except OSError:
                pass
            payload["status"] = "PURGE-COMMITTED"
            payload["completed_at"] = (
                self._now().astimezone().isoformat(timespec="seconds")
            )
            self._write_manifest(audit, payload)
            recovery.unlink()
            recovery_created = False
            payload["status"] = "PURGED"
            payload["recovery_archive_removed"] = True
            self._write_manifest(audit, payload)
            result.status = "PURGED"
            result.committed = True
            result.steps.append(
                QuarantinePurgeStep("purge", True, "Pakiet trwale usunięto")
            )
        except Exception as exc:
            rollback_ok = False
            if (
                moved
                and staged.is_dir()
                and not recovery_created
                and not fresh.package.exists()
            ):
                try:
                    fresh.package.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
                    os.replace(staged, fresh.package)
                    moved = False
                    rollback_ok = True
                    result.steps.append(
                        QuarantinePurgeStep(
                            "rollback", True, "Przywrócono pakiet z staging"
                        )
                    )
                except Exception as rollback_exc:
                    result.steps.append(
                        QuarantinePurgeStep("rollback", False, str(rollback_exc))
                    )
            payload["status"] = "PURGE-FAILED"
            payload["error"] = str(exc)
            payload["recovery_available"] = recovery.is_file()
            try:
                self._write_manifest(audit, payload)
            except Exception:
                pass
            result.status = "PURGE-FAILED"
            result.rolled_back = rollback_ok
            result.steps.append(QuarantinePurgeStep("purge", False, str(exc)))
        return result

    @staticmethod
    def _create_recovery_archive(source: Path, target: Path) -> None:
        fd, name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        os.close(fd)
        temporary = Path(name)
        temporary.unlink()
        try:
            with tarfile.open(temporary, "w") as archive:
                for filename in ("manifest.json", "zone.db", "zone.conf"):
                    archive.add(source / filename, arcname=filename, recursive=False)
            with temporary.open("rb") as handle:
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o640)
            os.replace(temporary, target)
            with tarfile.open(target, "r") as archive:
                if set(archive.getnames()) != {"manifest.json", "zone.db", "zone.conf"}:
                    raise RuntimeError("niekompletne archiwum ratunkowe")
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _remove_staged_package(package: Path) -> None:
        for name in ("zone.db", "zone.conf", "manifest.json"):
            (package / name).unlink()
        package.rmdir()

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

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
