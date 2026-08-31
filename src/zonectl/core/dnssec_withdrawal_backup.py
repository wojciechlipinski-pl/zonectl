"""Verified recovery package created before DNSSEC withdrawal."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .dnssec_disable_plan import DnssecDisablePlan


@dataclass(slots=True)
class DnssecWithdrawalBackupStep:
    name: str
    ok: bool
    message: str


@dataclass(slots=True)
class DnssecWithdrawalBackupResult:
    transaction_id: str
    zone: str
    status: str
    committed: bool = False
    package: str | None = None
    manifest: str | None = None
    steps: list[DnssecWithdrawalBackupStep] = field(default_factory=list)


class DnssecWithdrawalBackupError(RuntimeError):
    """A complete and verified recovery package could not be created."""


class DnssecWithdrawalBackup:
    """Copy every withdrawal input into an atomically published package."""

    def __init__(self, backup_root: Path) -> None:
        self.backup_root = backup_root

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def _copy_record(
        cls,
        source: Path,
        package: Path,
        relative: Path,
    ) -> dict[str, object]:
        target = package / relative
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        source_stat = source.stat()
        source_hash = cls._sha256(source)
        shutil.copy2(source, target)
        if hasattr(os, "chown"):
            os.chown(target, source_stat.st_uid, source_stat.st_gid)
        target_hash = cls._sha256(target)
        if target_hash != source_hash:
            raise DnssecWithdrawalBackupError(f"Niezgodna suma SHA-256 kopii: {source}")
        return {
            "source": str(source),
            "stored_as": str(relative),
            "sha256": source_hash,
            "size": source_stat.st_size,
            "mode": oct(source_stat.st_mode & 0o7777),
            "uid": source_stat.st_uid,
            "gid": source_stat.st_gid,
        }

    @staticmethod
    def _sources(plan: DnssecDisablePlan) -> tuple[tuple[Path, Path], ...]:
        entries: list[tuple[Path, Path]] = [
            (plan.declaration_file, Path("bind-declaration.conf")),
            (plan.zone_file, Path("zone.db")),
        ]
        entries.extend((path, Path("keys") / path.name) for path in plan.key_files)
        entries.extend(
            (path, Path("artifacts") / path.name) for path in plan.signing_artifacts
        )
        return tuple(entries)

    @classmethod
    def _preflight(cls, plan: DnssecDisablePlan) -> None:
        if plan.declaration_file.read_text(encoding="utf-8") != plan.original_text:
            raise DnssecWithdrawalBackupError(
                "Konfiguracja zmieniła się od utworzenia planu"
            )
        missing = [
            source for source, _relative in cls._sources(plan) if not source.is_file()
        ]
        if missing:
            raise DnssecWithdrawalBackupError(f"Brak pliku do backupu: {missing[0]}")
        if not plan.key_files:
            raise DnssecWithdrawalBackupError("Brak materiału kluczowego strefy")

    def create(
        self,
        plan: DnssecDisablePlan,
        *,
        commit: bool = False,
        dnssec_report: dict[str, object] | None = None,
        ds_check: dict[str, object] | None = None,
    ) -> DnssecWithdrawalBackupResult:
        txid = (
            datetime.now().strftime("%Y%m%d-%H%M%S")
            + f"-dnssec-withdrawal-backup-{plan.zone}-{uuid.uuid4().hex[:8]}"
        )
        result = DnssecWithdrawalBackupResult(txid, plan.zone, "PLAN")
        try:
            self._preflight(plan)
        except (OSError, DnssecWithdrawalBackupError) as exc:
            result.status = "CONFLICT"
            result.steps.append(
                DnssecWithdrawalBackupStep("preflight", False, str(exc))
            )
            return result
        if not commit:
            result.status = "DRY-RUN"
            result.steps.append(
                DnssecWithdrawalBackupStep(
                    "dry-run", True, "Nie utworzono pakietu i nie zmieniono BIND"
                )
            )
            return result

        zone_root = self.backup_root / plan.zone.rstrip(".")
        zone_root.mkdir(parents=True, exist_ok=True, mode=0o750)
        final = zone_root / txid
        temporary = Path(tempfile.mkdtemp(prefix=f".{txid}.", dir=zone_root))
        try:
            records = [
                self._copy_record(source, temporary, relative)
                for source, relative in self._sources(plan)
            ]
            result.steps.append(
                DnssecWithdrawalBackupStep(
                    "files", True, f"Skopiowano i zweryfikowano {len(records)} plików"
                )
            )
            payload = {
                "transaction_id": txid,
                "zone": plan.zone,
                "status": "BACKUP-CREATED",
                "created_at": datetime.now(timezone.utc)
                .astimezone()
                .isoformat(timespec="seconds"),
                "policy": plan.policy,
                "candidate_diff_after_safe_withdrawal": plan.unified_diff,
                "files": records,
                "dnssec_report": dnssec_report,
                "ds_check": ds_check,
            }
            manifest = temporary / "manifest.json"
            manifest.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.chmod(manifest, 0o640)
            os.replace(temporary, final)
            result.status = "BACKUP-CREATED"
            result.committed = True
            result.package = str(final)
            result.manifest = str(final / "manifest.json")
            result.steps.append(
                DnssecWithdrawalBackupStep(
                    "package", True, f"Pakiet odtworzeniowy: {final}"
                )
            )
            return result
        except Exception as exc:
            shutil.rmtree(temporary, ignore_errors=True)
            result.status = "FAILED"
            result.steps.append(DnssecWithdrawalBackupStep("package", False, str(exc)))
            return result
