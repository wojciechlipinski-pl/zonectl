"""Transakcyjne zastosowanie planu włączenia DNSSEC."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .dnssec_enable_plan import DnssecEnablePlan
from .audit_store import AuditStore, ResourceKind, Risk
from .family_audit_adapter import FamilyAuditAdapter
from .runner import run


@dataclass(slots=True)
class DnssecEnableStep:
    name: str
    ok: bool
    message: str


@dataclass(slots=True)
class DnssecEnableResult:
    transaction_id: str
    zone: str
    status: str
    committed: bool = False
    rolled_back: bool = False
    manifest: str | None = None
    backup_directory: str | None = None
    steps: list[DnssecEnableStep] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.steps) and all(step.ok for step in self.steps)


ZoneValidator = Callable[[str, Path], DnssecEnableStep]
ConfigValidator = Callable[[Path], DnssecEnableStep]
ZoneAction = Callable[[str], DnssecEnableStep]


class DnssecEnableTransaction:
    """Stosuje plan DNSSEC z backupem i pełnym rollbackiem plików."""

    def __init__(
        self,
        backup_root: Path,
        manifest_directory: Path,
        *,
        root_config: Path = Path("/etc/bind/named.conf"),
        zone_validator: ZoneValidator | None = None,
        config_validator: ConfigValidator | None = None,
        activator: ZoneAction | None = None,
        loaded_verifier: ZoneAction | None = None,
        dnssec_verifier: ZoneAction | None = None,
        audit_store: AuditStore | None = None,
    ) -> None:
        self.backup_root = backup_root
        self.manifest_directory = manifest_directory
        self.root_config = root_config
        self.zone_validator = zone_validator or self._validate_zone
        self.config_validator = config_validator or self._validate_config
        self.activator = activator or self._activate_bind
        self.loaded_verifier = loaded_verifier or self._verify_loaded
        self.dnssec_verifier = dnssec_verifier or self._verify_dnssec
        self.audit_v1 = FamilyAuditAdapter(
            audit_store or FamilyAuditAdapter.default_store(manifest_directory),
            manifest_directory=manifest_directory,
            backup_root=backup_root,
        )

    def apply(
        self,
        plan: DnssecEnablePlan,
        *,
        commit: bool = False,
        activate: bool = False,
    ) -> DnssecEnableResult:
        txid = (
            datetime.now().strftime("%Y%m%d-%H%M%S")
            + f"-dnssec-enable-{plan.zone}-{uuid.uuid4().hex[:8]}"
        )
        result = DnssecEnableResult(txid, plan.zone, "PLAN")
        self.audit_v1.start(
            txid,
            "dnssec.enable",
            ResourceKind.ZONE,
            plan.zone,
            risk=Risk.HIGH if commit else Risk.LOW,
        )
        conflict = self._preflight(plan)
        if conflict is not None:
            return self._finish(result, "CONFLICT", conflict, write_manifest=False)
        if not commit:
            return self._finish(
                result,
                "DRY-RUN",
                DnssecEnableStep("dry-run", True, "Nie zmieniono plików ani BIND"),
                write_manifest=False,
            )

        backup_directory = self.backup_root / txid
        result.backup_directory = str(backup_directory)
        declaration_stat = plan.declaration_file.stat()
        target_created = False
        config_written = False
        activation_attempted = False
        before_sidecars = set(
            plan.target_zone_file.parent.glob(plan.target_zone_file.name + ".*")
        )
        before_keys = (
            set(plan.key_directory.glob(f"K{plan.zone.rstrip('.')}.*"))
            if plan.key_directory.exists()
            else set()
        )
        try:
            backup_directory.mkdir(parents=True, mode=0o750)
            self._copy_backup(
                plan.declaration_file, backup_directory / "bind-declaration.conf"
            )
            self._copy_backup(
                plan.source_zone_file, backup_directory / "zone-source.db"
            )
            result.steps.append(
                DnssecEnableStep("backup", True, f"Backup: {backup_directory}")
            )

            plan.key_directory.mkdir(parents=True, exist_ok=True, mode=0o750)
            result.steps.append(
                DnssecEnableStep("key-directory", True, str(plan.key_directory))
            )

            if plan.migration_required:
                self._atomic_copy_to_parent_owner(
                    plan.source_zone_file, plan.target_zone_file
                )
                target_created = True
                result.steps.append(
                    DnssecEnableStep(
                        "zone-migration", True, f"Skopiowano {plan.target_zone_file}"
                    )
                )

            zone_step = self.zone_validator(plan.zone, plan.target_zone_file)
            result.steps.append(zone_step)
            if not zone_step.ok:
                raise RuntimeError(zone_step.message)

            self._atomic_write(
                plan.declaration_file,
                plan.candidate_text.encode("utf-8"),
                declaration_stat.st_mode & 0o777,
                declaration_stat.st_uid,
                declaration_stat.st_gid,
            )
            config_written = True
            result.steps.append(
                DnssecEnableStep(
                    "configuration", True, f"Zaktualizowano {plan.declaration_file}"
                )
            )

            config_step = self.config_validator(self.root_config)
            result.steps.append(config_step)
            if not config_step.ok:
                raise RuntimeError(config_step.message)

            if activate:
                activation_attempted = True
                for action in (
                    self.activator,
                    self.loaded_verifier,
                    self.dnssec_verifier,
                ):
                    step = action(plan.zone)
                    result.steps.append(step)
                    if not step.ok:
                        raise RuntimeError(step.message)

            result.committed = True
            return self._finish(result, "COMMIT")
        except Exception as exc:
            result.steps.append(DnssecEnableStep("transaction", False, str(exc)))
            rollback_ok = True
            try:
                if config_written:
                    self._atomic_write(
                        plan.declaration_file,
                        (backup_directory / "bind-declaration.conf").read_bytes(),
                        declaration_stat.st_mode & 0o777,
                        declaration_stat.st_uid,
                        declaration_stat.st_gid,
                    )
                if activation_attempted:
                    restore = self.activator(plan.zone)
                    result.steps.append(
                        DnssecEnableStep(
                            "rndc-reconfig-rollback", restore.ok, restore.message
                        )
                    )
                    if not restore.ok:
                        rollback_ok = False
                if target_created:
                    plan.target_zone_file.unlink(missing_ok=True)
                self._remove_new_artifacts(
                    plan.target_zone_file.parent.glob(
                        plan.target_zone_file.name + ".*"
                    ),
                    before_sidecars,
                )
                self._remove_new_artifacts(
                    plan.key_directory.glob(f"K{plan.zone.rstrip('.')}.*"),
                    before_keys,
                )
            except OSError as rollback_error:
                rollback_ok = False
                result.steps.append(
                    DnssecEnableStep("rollback", False, str(rollback_error))
                )
            else:
                result.steps.append(
                    DnssecEnableStep(
                        "rollback", rollback_ok, "Przywrócono stan sprzed transakcji"
                    )
                )
            result.rolled_back = rollback_ok
            return self._finish(
                result, "ROLLED-BACK" if rollback_ok else "ROLLBACK-FAILED"
            )

    @staticmethod
    def _preflight(plan: DnssecEnablePlan) -> DnssecEnableStep | None:
        if not plan.declaration_file.is_file() or not plan.source_zone_file.is_file():
            return DnssecEnableStep(
                "preflight", False, "Brak deklaracji lub pliku źródłowego"
            )
        if plan.declaration_file.read_text(encoding="utf-8") != plan.original_text:
            return DnssecEnableStep(
                "preflight", False, "Konfiguracja zmieniła się od utworzenia planu"
            )
        if plan.migration_required and plan.target_zone_file.exists():
            return DnssecEnableStep(
                "preflight", False, f"Cel już istnieje: {plan.target_zone_file}"
            )
        sidecars = list(
            plan.target_zone_file.parent.glob(plan.target_zone_file.name + ".*")
        )
        if sidecars:
            return DnssecEnableStep(
                "preflight",
                False,
                f"Istnieją artefakty docelowej strefy: {sidecars[0]}",
            )
        if plan.key_directory.exists():
            keys = list(plan.key_directory.glob(f"K{plan.zone.rstrip('.')}.*"))
            if keys:
                return DnssecEnableStep(
                    "preflight",
                    False,
                    f"Istnieje materiał kluczowy strefy: {keys[0]}",
                )
        return None

    def _finish(
        self,
        result: DnssecEnableResult,
        status: str,
        step: DnssecEnableStep | None = None,
        *,
        write_manifest: bool = True,
    ) -> DnssecEnableResult:
        result.status = status
        if step is not None:
            result.steps.append(step)
        if write_manifest:
            self.manifest_directory.mkdir(parents=True, exist_ok=True, mode=0o750)
            path = self.manifest_directory / f"{result.transaction_id}.json"
            result.manifest = str(path)
            payload = asdict(result)
            payload["saved_at"] = (
                datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
            )
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        self.audit_v1.finish_result(result)
        return result

    @staticmethod
    def _copy_backup(source: Path, target: Path) -> None:
        shutil.copy2(source, target)
        if hasattr(os, "chown"):
            owner = source.stat()
            os.chown(target, owner.st_uid, owner.st_gid)

    @staticmethod
    def _atomic_write(
        path: Path, content: bytes, mode: int, uid: int, gid: int
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, mode)
            if hasattr(os, "chown"):
                os.chown(temporary, uid, gid)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @classmethod
    def _atomic_copy_exact(cls, source: Path, target: Path) -> None:
        stat = source.stat()
        cls._atomic_write(
            target, source.read_bytes(), stat.st_mode & 0o777, stat.st_uid, stat.st_gid
        )

    @classmethod
    def _atomic_copy_to_parent_owner(cls, source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        parent = target.parent.stat()
        cls._atomic_write(
            target, source.read_bytes(), 0o640, parent.st_uid, parent.st_gid
        )

    @staticmethod
    def _remove_new_artifacts(
        current: Iterable[Path],
        before: set[Path],
    ) -> None:
        for path in set(current) - before:
            if path.is_file():
                path.unlink()

    @staticmethod
    def _validate_zone(zone: str, path: Path) -> DnssecEnableStep:
        outcome = run(["named-checkzone", zone, str(path)], 30)
        return DnssecEnableStep(
            "named-checkzone",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}",
        )

    @staticmethod
    def _validate_config(path: Path) -> DnssecEnableStep:
        outcome = run(["named-checkconf", str(path)], 30)
        return DnssecEnableStep(
            "named-checkconf",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}",
        )

    @staticmethod
    def _activate_bind(_zone: str) -> DnssecEnableStep:
        outcome = run(["rndc", "reconfig"], 30)
        return DnssecEnableStep(
            "rndc-reconfig",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}",
        )

    @staticmethod
    def _verify_loaded(zone: str) -> DnssecEnableStep:
        outcome = run(["rndc", "zonestatus", zone], 30)
        return DnssecEnableStep(
            "rndc-zonestatus",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}",
        )

    @staticmethod
    def _verify_dnssec(zone: str) -> DnssecEnableStep:
        outcome = run(["rndc", "dnssec", "-status", zone], 30)
        ok = outcome.returncode == 0 and "zone signing" in outcome.stdout.casefold()
        return DnssecEnableStep(
            "dnssec-status",
            ok,
            (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}",
        )
