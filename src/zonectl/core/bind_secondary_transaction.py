"""Transactional application of a validated BIND secondary-group plan."""

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

from .bind_secondary_plan import BindSecondaryPlan
from .runner import run


@dataclass(slots=True)
class BindSecondaryStep:
    name: str
    ok: bool
    message: str


@dataclass(slots=True)
class BindSecondaryResult:
    transaction_id: str
    group: str
    status: str
    roles: tuple[str, ...] = ()
    old_addresses: tuple[str, ...] = ()
    new_addresses: tuple[str, ...] = ()
    zones: tuple[str, ...] = ()
    committed: bool = False
    rolled_back: bool = False
    backup: str | None = None
    manifest: str | None = None
    steps: list[BindSecondaryStep] = field(default_factory=list)


ConfigValidator = Callable[[Path], BindSecondaryStep]
Activator = Callable[[], BindSecondaryStep]


class BindSecondaryTransaction:
    def __init__(
        self,
        backup_root: Path,
        manifest_directory: Path,
        *,
        root_config: Path = Path("/etc/bind/named.conf"),
        config_validator: ConfigValidator | None = None,
        activator: Activator | None = None,
    ) -> None:
        self.backup_root = backup_root
        self.manifest_directory = manifest_directory
        self.root_config = root_config
        self.config_validator = config_validator or self._validate_config
        self.activator = activator or self._activate

    def apply(
        self,
        plan: BindSecondaryPlan,
        *,
        commit: bool = False,
        activate: bool = False,
    ) -> BindSecondaryResult:
        txid = (
            datetime.now().strftime("%Y%m%d-%H%M%S")
            + f"-secondary-{plan.name}-{uuid.uuid4().hex[:8]}"
        )
        result = BindSecondaryResult(
            txid,
            plan.name,
            "PLAN",
            roles=plan.roles,
            old_addresses=plan.old_addresses,
            new_addresses=plan.new_addresses,
            zones=plan.zones,
        )
        current = plan.source.read_text(encoding="utf-8", errors="replace")
        if current != plan.original_text:
            result.status = "CONFLICT"
            result.steps.append(BindSecondaryStep(
                "preflight", False, f"Plik zmienił się: {plan.source}"
            ))
            return result
        if not plan.validation_ok:
            result.status = "BLOCKED"
            result.steps.append(BindSecondaryStep(
                "candidate-validation", False, plan.validation_message
            ))
            return result
        if not commit:
            result.status = "DRY-RUN"
            result.steps.append(BindSecondaryStep(
                "dry-run", True, "Nie zmieniono konfiguracji ani BIND"
            ))
            return result

        self.backup_root.mkdir(parents=True, exist_ok=True, mode=0o750)
        backup = self.backup_root / f"{txid}-{plan.source.name}"
        result.backup = str(backup)
        metadata = plan.source.stat()
        activation_attempted = False
        try:
            shutil.copy2(plan.source, backup)
            result.steps.append(BindSecondaryStep("backup", True, f"Backup: {backup}"))
            self._atomic_write(
                plan.source,
                plan.candidate_text.encode("utf-8"),
                metadata.st_mode & 0o777,
                metadata.st_uid,
                metadata.st_gid,
            )
            result.steps.append(BindSecondaryStep(
                "configuration", True, f"Zaktualizowano {plan.source}"
            ))
            check = self.config_validator(self.root_config)
            result.steps.append(check)
            if not check.ok:
                raise RuntimeError(check.message)
            if activate:
                activation_attempted = True
                reload_step = self.activator()
                result.steps.append(reload_step)
                if not reload_step.ok:
                    raise RuntimeError(reload_step.message)
            result.committed = True
            result.status = "COMMIT"
        except Exception as exc:
            result.steps.append(BindSecondaryStep("transaction", False, str(exc)))
            rollback_ok = True
            try:
                self._atomic_write(
                    plan.source,
                    plan.original_text.encode("utf-8"),
                    metadata.st_mode & 0o777,
                    metadata.st_uid,
                    metadata.st_gid,
                )
                if activation_attempted:
                    rollback_reload = self.activator()
                    result.steps.append(BindSecondaryStep(
                        "rndc-reconfig-rollback",
                        rollback_reload.ok,
                        rollback_reload.message,
                    ))
                    rollback_ok = rollback_reload.ok
            except OSError as rollback_error:
                rollback_ok = False
                result.steps.append(BindSecondaryStep(
                    "rollback", False, str(rollback_error)
                ))
            if rollback_ok:
                result.steps.append(BindSecondaryStep(
                    "rollback", True, "Przywrócono konfigurację sprzed transakcji"
                ))
            result.rolled_back = rollback_ok
            result.status = "ROLLED-BACK" if rollback_ok else "ROLLBACK-FAILED"
        self._write_manifest(result)
        return result

    def _write_manifest(self, result: BindSecondaryResult) -> None:
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
    def _validate_config(root: Path) -> BindSecondaryStep:
        outcome = run(["named-checkconf", str(root)], 30)
        detail = (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}"
        return BindSecondaryStep("named-checkconf", outcome.returncode == 0, detail)

    @staticmethod
    def _activate() -> BindSecondaryStep:
        outcome = run(["rndc", "reconfig"], 30)
        detail = (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}"
        return BindSecondaryStep("rndc-reconfig", outcome.returncode == 0, detail)
