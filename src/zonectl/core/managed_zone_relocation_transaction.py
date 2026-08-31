"""Transactional relocation of an already managed BIND zone file."""

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

from .managed_zone_relocation import ManagedZoneRelocationPlan
from .managed_zone_migration_transaction import ManagedZoneMigrationStep
from .runner import run


@dataclass(slots=True)
class ManagedZoneRelocationResult:
    """Final status, backup and rollback state for zone-file relocation."""

    transaction_id: str
    zone: str
    status: str
    committed: bool = False
    rolled_back: bool = False
    backup_directory: str | None = None
    manifest: str | None = None
    steps: list[ManagedZoneMigrationStep] = field(default_factory=list)


ZoneValidator = Callable[[str, Path], ManagedZoneMigrationStep]
ConfigValidator = Callable[[Path], ManagedZoneMigrationStep]
ZoneAction = Callable[[str], ManagedZoneMigrationStep]
LoadedVerifier = Callable[[str, Path], ManagedZoneMigrationStep]


class ManagedZoneRelocationTransaction:
    """Relocate an already managed zone file with validation and rollback."""

    def __init__(
        self,
        backup_root: Path,
        manifest_directory: Path,
        *,
        root_config: Path = Path("/etc/bind/named.conf"),
        zone_validator: ZoneValidator | None = None,
        config_validator: ConfigValidator | None = None,
        activator: ZoneAction | None = None,
        loaded_verifier: LoadedVerifier | None = None,
    ) -> None:
        self.backup_root = backup_root
        self.manifest_directory = manifest_directory
        self.root_config = root_config
        self.zone_validator = zone_validator or self._validate_zone
        self.config_validator = config_validator or self._validate_config
        self.activator = activator or self._activate
        self.loaded_verifier = loaded_verifier or self._verify_loaded

    def apply(
        self,
        plan: ManagedZoneRelocationPlan,
        *,
        commit: bool = False,
        activate: bool = False,
    ) -> ManagedZoneRelocationResult:
        """Apply a verified relocation plan or return its dry-run result."""
        txid = datetime.now().strftime("%Y%m%d-%H%M%S") + (
            f"-zone-relocate-{plan.zone}-{uuid.uuid4().hex[:8]}"
        )
        result = ManagedZoneRelocationResult(txid, plan.zone, "PLAN")
        conflict = self._preflight(plan)
        if conflict:
            result.steps.append(conflict)
            result.status = "CONFLICT"
            return result
        if not commit:
            check = self.zone_validator(plan.zone, plan.source_file)
            result.steps.extend(
                (
                    check,
                    ManagedZoneMigrationStep(
                        "dry-run", True, "Nie zmieniono plików ani BIND"
                    ),
                )
            )
            result.status = "DRY-RUN" if check.ok else "CONFLICT"
            return result

        backup = self.backup_root / txid
        result.backup_directory = str(backup)
        declaration_stat = plan.declaration_file.stat()
        source_stat = plan.source_file.stat()
        activation_attempted = False
        try:
            backup.mkdir(parents=True, mode=0o750)
            shutil.copy2(plan.declaration_file, backup / plan.declaration_file.name)
            shutil.copy2(plan.source_file, backup / plan.source_file.name)
            result.steps.append(
                ManagedZoneMigrationStep("backup", True, f"Backup: {backup}")
            )
            self._atomic_copy(plan.source_file, plan.target_file, source_stat)
            check = self.zone_validator(plan.zone, plan.target_file)
            result.steps.append(check)
            if not check.ok:
                raise RuntimeError(check.message)
            self._atomic_write(
                plan.declaration_file,
                plan.declaration_candidate.encode(),
                declaration_stat,
            )
            check = self.config_validator(self.root_config)
            result.steps.append(check)
            if not check.ok:
                raise RuntimeError(check.message)
            if activate:
                activation_attempted = True
                for step in (
                    self.activator(plan.zone),
                    self.loaded_verifier(plan.zone, plan.target_file),
                ):
                    result.steps.append(step)
                    if not step.ok:
                        raise RuntimeError(step.message)
            plan.source_file.unlink()
            result.steps.append(
                ManagedZoneMigrationStep(
                    "source-retired",
                    True,
                    f"Stary plik usunięty po walidacji: {plan.source_file}",
                )
            )
            result.committed = True
            result.status = "COMMIT"
        except Exception as exc:
            result.steps.append(
                ManagedZoneMigrationStep("transaction", False, str(exc))
            )
            rollback_ok = True
            try:
                self._atomic_write(
                    plan.declaration_file,
                    plan.declaration_original.encode(),
                    declaration_stat,
                )
                if not plan.source_file.exists() and backup.exists():
                    self._atomic_copy(
                        backup / plan.source_file.name, plan.source_file, source_stat
                    )
                plan.target_file.unlink(missing_ok=True)
                if activation_attempted:
                    step = self.activator(plan.zone)
                    result.steps.append(
                        ManagedZoneMigrationStep(
                            "rndc-reconfig-rollback", step.ok, step.message
                        )
                    )
                    rollback_ok = step.ok
            except Exception as rollback_error:
                rollback_ok = False
                result.steps.append(
                    ManagedZoneMigrationStep("rollback", False, str(rollback_error))
                )
            result.rolled_back = rollback_ok
            result.steps.append(
                ManagedZoneMigrationStep(
                    "rollback",
                    rollback_ok,
                    "Przywrócono stan sprzed relokacji"
                    if rollback_ok
                    else "Rollback niepełny",
                )
            )
            result.status = "ROLLED-BACK" if rollback_ok else "ROLLBACK-FAILED"
        self._write_manifest(result)
        return result

    @staticmethod
    def _preflight(
        plan: ManagedZoneRelocationPlan,
    ) -> ManagedZoneMigrationStep | None:
        if not plan.source_file.is_file():
            return ManagedZoneMigrationStep(
                "preflight", False, f"Brak źródła: {plan.source_file}"
            )
        if plan.target_file.exists():
            return ManagedZoneMigrationStep(
                "preflight", False, f"Cel już istnieje: {plan.target_file}"
            )
        if (
            plan.declaration_file.read_text(encoding="utf-8")
            != plan.declaration_original
        ):
            return ManagedZoneMigrationStep(
                "preflight", False, "Deklaracja zmieniła się od utworzenia planu"
            )
        return None

    def _write_manifest(self, result: ManagedZoneRelocationResult) -> None:
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

    @staticmethod
    def _atomic_write(
        path: Path,
        content: bytes,
        metadata: os.stat_result,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, metadata.st_mode & 0o777)
            chown = getattr(os, "chown", None)
            if chown is not None:
                chown(temporary, metadata.st_uid, metadata.st_gid)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @classmethod
    def _atomic_copy(
        cls,
        source: Path,
        target: Path,
        metadata: os.stat_result,
    ) -> None:
        cls._atomic_write(target, source.read_bytes(), metadata)

    @staticmethod
    def _validate_zone(zone: str, path: Path) -> ManagedZoneMigrationStep:
        outcome = run(["named-checkzone", zone, str(path)], 30)
        detail = (
            outcome.stdout or outcome.stderr
        ).strip() or f"kod {outcome.returncode}"
        return ManagedZoneMigrationStep(
            "named-checkzone", outcome.returncode == 0, detail
        )

    @staticmethod
    def _validate_config(root: Path) -> ManagedZoneMigrationStep:
        outcome = run(["named-checkconf", str(root)], 30)
        detail = (
            outcome.stdout or outcome.stderr
        ).strip() or f"kod {outcome.returncode}"
        return ManagedZoneMigrationStep(
            "named-checkconf", outcome.returncode == 0, detail
        )

    @staticmethod
    def _activate(_zone: str) -> ManagedZoneMigrationStep:
        outcome = run(["rndc", "reconfig"], 30)
        detail = (
            outcome.stdout or outcome.stderr
        ).strip() or f"kod {outcome.returncode}"
        return ManagedZoneMigrationStep(
            "rndc-reconfig", outcome.returncode == 0, detail
        )

    @staticmethod
    def _verify_loaded(zone: str, target: Path) -> ManagedZoneMigrationStep:
        outcome = run(["rndc", "zonestatus", zone], 30)
        detail = (
            outcome.stdout or outcome.stderr
        ).strip() or f"kod {outcome.returncode}"
        ok = outcome.returncode == 0 and str(target) in outcome.stdout
        if outcome.returncode == 0 and not ok:
            detail = f"rndc zonestatus nie potwierdził ścieżki {target}"
        return ManagedZoneMigrationStep("rndc-zonestatus", ok, detail)
