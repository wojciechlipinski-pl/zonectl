"""Transactional migration of one legacy BIND zone declaration."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .managed_zone_migration import ManagedZoneMigrationPlan
from .runner import run


@dataclass(slots=True)
class ManagedZoneMigrationStep:
    name: str
    ok: bool
    message: str


@dataclass(slots=True)
class ManagedZoneMigrationResult:
    transaction_id: str
    zone: str
    status: str
    committed: bool = False
    rolled_back: bool = False
    backup_directory: str | None = None
    manifest: str | None = None
    steps: list[ManagedZoneMigrationStep] = field(default_factory=list)


ConfigValidator = Callable[[Path], ManagedZoneMigrationStep]
ZoneAction = Callable[[str], ManagedZoneMigrationStep]


class ManagedZoneMigrationTransaction:
    """Apply a precomputed plan atomically and restore all files on failure."""

    def __init__(
        self,
        backup_root: Path,
        manifest_directory: Path,
        *,
        root_config: Path = Path("/etc/bind/named.conf"),
        config_validator: ConfigValidator | None = None,
        activator: ZoneAction | None = None,
        loaded_verifier: ZoneAction | None = None,
    ) -> None:
        self.backup_root = backup_root
        self.manifest_directory = manifest_directory
        self.root_config = root_config
        self.config_validator = config_validator or self._validate_config
        self.activator = activator or self._activate
        self.loaded_verifier = loaded_verifier or self._verify_loaded

    def apply(
        self,
        plan: ManagedZoneMigrationPlan,
        *,
        commit: bool = False,
        activate: bool = False,
    ) -> ManagedZoneMigrationResult:
        txid = (
            datetime.now().strftime("%Y%m%d-%H%M%S")
            + f"-zone-migrate-{plan.zone}-{uuid.uuid4().hex[:8]}"
        )
        result = ManagedZoneMigrationResult(txid, plan.zone, "PLAN")
        conflict = self._preflight(plan)
        if conflict:
            result.steps.append(conflict)
            result.status = "CONFLICT"
            return result
        if not commit:
            result.steps.append(
                ManagedZoneMigrationStep(
                    "dry-run", True, "Nie zmieniono plików ani BIND"
                )
            )
            result.status = "DRY-RUN"
            return result

        backup = self.backup_root / txid
        result.backup_directory = str(backup)
        source_stat = plan.source_config.stat()
        index_stat = plan.managed_config.stat()
        activation_attempted = False
        try:
            backup.mkdir(parents=True, mode=0o750)
            shutil.copy2(plan.source_config, backup / "named.conf.local")
            shutil.copy2(plan.managed_config, backup / "zonectl-zones.conf")
            result.steps.append(
                ManagedZoneMigrationStep("backup", True, f"Backup: {backup}")
            )
            self._atomic_write(
                plan.declaration_file,
                plan.declaration_text.encode(),
                0o640,
                plan.managed_config.stat().st_uid,
                plan.managed_config.stat().st_gid,
            )
            self._atomic_write(
                plan.source_config,
                plan.source_candidate.encode(),
                source_stat.st_mode & 0o777,
                source_stat.st_uid,
                source_stat.st_gid,
            )
            self._atomic_write(
                plan.managed_config,
                plan.managed_candidate.encode(),
                index_stat.st_mode & 0o777,
                index_stat.st_uid,
                index_stat.st_gid,
            )
            result.steps.append(
                ManagedZoneMigrationStep(
                    "configuration", True, "Zapisano deklarację i indeks ZoneCTL"
                )
            )
            check = self.config_validator(self.root_config)
            result.steps.append(check)
            if not check.ok:
                raise RuntimeError(check.message)
            if activate:
                activation_attempted = True
                for action in (self.activator, self.loaded_verifier):
                    step = action(plan.zone)
                    result.steps.append(step)
                    if not step.ok:
                        raise RuntimeError(step.message)
            result.committed = True
            result.status = "COMMIT"
        except Exception as exc:
            result.steps.append(ManagedZoneMigrationStep("transaction", False, str(exc)))
            rollback_ok = True
            try:
                self._atomic_write(
                    plan.source_config, plan.source_original.encode(),
                    source_stat.st_mode & 0o777, source_stat.st_uid, source_stat.st_gid,
                )
                self._atomic_write(
                    plan.managed_config, plan.managed_original.encode(),
                    index_stat.st_mode & 0o777, index_stat.st_uid, index_stat.st_gid,
                )
                plan.declaration_file.unlink(missing_ok=True)
                if activation_attempted:
                    step = self.activator(plan.zone)
                    result.steps.append(ManagedZoneMigrationStep(
                        "rndc-reconfig-rollback", step.ok, step.message
                    ))
                    if not step.ok:
                        rollback_ok = False
            except OSError as rollback_error:
                rollback_ok = False
                result.steps.append(ManagedZoneMigrationStep(
                    "rollback", False, str(rollback_error)
                ))
            if rollback_ok:
                result.steps.append(ManagedZoneMigrationStep(
                    "rollback", True, "Przywrócono stan sprzed transakcji"
                ))
            result.rolled_back = rollback_ok
            result.status = "ROLLED-BACK" if rollback_ok else "ROLLBACK-FAILED"

        self._write_manifest(result)
        return result

    @staticmethod
    def _preflight(plan: ManagedZoneMigrationPlan) -> ManagedZoneMigrationStep | None:
        if plan.declaration_file.exists():
            return ManagedZoneMigrationStep(
                "preflight", False, f"Plik już istnieje: {plan.declaration_file}"
            )
        if plan.source_config.read_text(encoding="utf-8") != plan.source_original:
            return ManagedZoneMigrationStep(
                "preflight", False, "named.conf.local zmienił się od utworzenia planu"
            )
        if plan.managed_config.read_text(encoding="utf-8") != plan.managed_original:
            return ManagedZoneMigrationStep(
                "preflight", False, "zonectl-zones.conf zmienił się od utworzenia planu"
            )
        return None

    def _write_manifest(self, result: ManagedZoneMigrationResult) -> None:
        self.manifest_directory.mkdir(parents=True, exist_ok=True, mode=0o750)
        path = self.manifest_directory / f"{result.transaction_id}.json"
        result.manifest = str(path)
        payload = asdict(result)
        payload["saved_at"] = datetime.now(timezone.utc).astimezone().isoformat(
            timespec="seconds"
        )
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _atomic_write(path: Path, content: bytes, mode: int, uid: int, gid: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, mode)
            os.chown(temporary, uid, gid)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _validate_config(root: Path) -> ManagedZoneMigrationStep:
        outcome = run(["named-checkconf", str(root)], 30)
        detail = (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}"
        return ManagedZoneMigrationStep("named-checkconf", outcome.returncode == 0, detail)

    @staticmethod
    def _activate(_zone: str) -> ManagedZoneMigrationStep:
        outcome = run(["rndc", "reconfig"], 30)
        detail = (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}"
        return ManagedZoneMigrationStep("rndc-reconfig", outcome.returncode == 0, detail)

    @staticmethod
    def _verify_loaded(zone: str) -> ManagedZoneMigrationStep:
        outcome = run(["rndc", "zonestatus", zone], 30)
        detail = (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}"
        return ManagedZoneMigrationStep("rndc-zonestatus", outcome.returncode == 0, detail)
