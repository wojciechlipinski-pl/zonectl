"""Guarded transaction migrating an external RPZ updater to MANAGED mode."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .rpz_external_migration_dry_run import RpzExternalMigrationDryRun
from .audit_store import AuditStore, ResourceKind, Risk
from .family_audit_adapter import FamilyAuditAdapter
from .rpz_external_migration_plan import RpzExternalMigrationPlan
from .runner import CommandResult, run


@dataclass(frozen=True, slots=True)
class RpzMigrationTransactionStep:
    name: str
    ok: bool
    message: str


@dataclass(slots=True)
class RpzMigrationTransactionResult:
    transaction_id: str
    zone: str
    status: str
    committed: bool = False
    activated: bool = False
    rolled_back: bool = False
    backup: str | None = None
    manifest: str | None = None
    steps: list[RpzMigrationTransactionStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class RpzExternalMigrationTransaction:
    """Install parallel MANAGED artifacts and switch timers with rollback."""

    def __init__(
        self,
        backup_root: Path = Path("/var/backups/zonectl-rpz/migrations"),
        manifest_directory: Path = Path("/var/backups/zonectl-rpz/manifests"),
        *,
        root_config: Path = Path("/etc/bind/named.conf"),
        command_runner: Callable[[list[str], int], CommandResult] = run,
        clock: Callable[[], float] = time.time,
        max_zone_age: int = 600,
        audit_store: AuditStore | None = None,
    ) -> None:
        self.backup_root = backup_root
        self.manifest_directory = manifest_directory
        self.root_config = root_config
        self.command_runner = command_runner
        self.clock = clock
        self.max_zone_age = max_zone_age
        self.audit_v1 = FamilyAuditAdapter(
            audit_store or FamilyAuditAdapter.default_store(manifest_directory),
            manifest_directory=manifest_directory,
            backup_root=backup_root,
        )

    def apply(
        self,
        plan: RpzExternalMigrationPlan,
        *,
        commit: bool = False,
        activate: bool = False,
        confirm: str | None = None,
    ) -> RpzMigrationTransactionResult:
        txid = (
            datetime.now().strftime("%Y%m%d-%H%M%S")
            + f"-rpz-migrate-{uuid.uuid4().hex[:8]}"
        )
        result = RpzMigrationTransactionResult(txid, plan.zone, "PLAN")
        self.audit_v1.start(
            txid,
            "rpz.migrate",
            ResourceKind.RPZ,
            plan.zone,
            risk=Risk.CRITICAL if commit else Risk.MEDIUM,
        )
        if plan.status != "READY":
            return self._blocked(result, "; ".join(plan.blockers) or plan.status)
        if commit != activate:
            return self._rejected(
                result, "Właściwa migracja wymaga jednocześnie --commit i --activate"
            )
        if commit and confirm != plan.zone:
            return self._rejected(
                result, f"Potwierdzenie musi mieć dokładną wartość: {plan.zone}"
            )
        integrity_error = self._integrity_error(plan)
        if integrity_error:
            return self._blocked(result, integrity_error)

        dry_run = RpzExternalMigrationDryRun(
            root_config=self.root_config, command_runner=self.command_runner
        ).execute(plan)
        for step in dry_run.steps:
            result.steps.append(
                RpzMigrationTransactionStep(
                    f"dry-run:{step.name}", step.ok, step.message
                )
            )
        if dry_run.status != "DRY-RUN":
            result.status = "BLOCKED"
            return self._finish_audit(result)
        if not commit:
            result.status = "DRY-RUN"
            return self._finish_audit(result)

        integrity_error = self._integrity_error(plan)
        if integrity_error:
            return self._blocked(result, integrity_error)

        originals = {item.role: item.path for item in plan.artifacts if item.path}
        serial_before = self._zone_serial(plan.zone)
        if serial_before is None:
            return self._blocked(
                result, "Nie można ustalić seriala RPZ przed przełączeniem"
            )
        backup = self.backup_root / txid
        result.backup = str(backup)
        external_was_enabled = plan.current_enabled
        external_was_active = plan.current_active
        switched = False
        try:
            backup.mkdir(parents=True, mode=0o750)
            for role, path in originals.items():
                shutil.copy2(path, backup / f"{role}-{path.name}")
            result.steps.append(
                RpzMigrationTransactionStep("backup", True, f"Backup: {backup}")
            )
            self._write_manifest(result)

            updater_source = originals["updater"]
            service_source = originals["service-unit"]
            timer_source = originals["timer-unit"]
            self._atomic_copy(updater_source, plan.managed_updater)
            service_text = service_source.read_text(encoding="utf-8", errors="replace")
            service_text = service_text.replace(
                str(updater_source), str(plan.managed_updater)
            )
            self._atomic_write(
                plan.managed_service, service_text.encode("utf-8"), service_source
            )
            timer_text = timer_source.read_text(encoding="utf-8", errors="replace")
            if plan.current_service:
                timer_text = timer_text.replace(
                    plan.current_service, plan.managed_service.name
                )
            self._atomic_write(
                plan.managed_timer, timer_text.encode("utf-8"), timer_source
            )
            result.steps.append(
                RpzMigrationTransactionStep(
                    "managed-artifacts", True, "Zapisano równoległe artefakty MANAGED"
                )
            )

            self._must_run(["systemctl", "daemon-reload"], "daemon-reload", result)
            self._must_run(
                ["systemctl", "disable", "--now", plan.current_timer or ""],
                "external-stop",
                result,
            )
            switched = True
            self._must_run(
                ["systemctl", "enable", "--now", plan.managed_timer.name],
                "managed-enable",
                result,
            )
            self._must_run(
                ["systemctl", "start", plan.managed_service.name],
                "managed-first-run",
                result,
            )
            self._post_activation_gate(
                plan, originals["zone-file"], serial_before, result
            )
            result.status = "COMMIT"
            result.committed = True
            result.activated = True
            self._write_manifest(result)
        except (OSError, RuntimeError) as exc:
            result.steps.append(
                RpzMigrationTransactionStep("transaction", False, str(exc))
            )
            result.rolled_back = self._rollback(
                plan, result, switched, external_was_enabled, external_was_active
            )
            result.status = "ROLLED-BACK" if result.rolled_back else "ROLLBACK-FAILED"
            try:
                self._write_manifest(result)
            except OSError as manifest_error:
                result.steps.append(
                    RpzMigrationTransactionStep(
                        "manifest",
                        False,
                        f"Nie zapisano wyniku rollbacku: {manifest_error}",
                    )
                )
        return self._finish_audit(result)

    def _blocked(
        self, result: RpzMigrationTransactionResult, message: str
    ) -> RpzMigrationTransactionResult:
        result.status = "BLOCKED"
        result.steps.append(RpzMigrationTransactionStep("preflight", False, message))
        return self._finish_audit(result)

    def _rejected(
        self, result: RpzMigrationTransactionResult, message: str
    ) -> RpzMigrationTransactionResult:
        result.status = "REJECTED"
        result.steps.append(RpzMigrationTransactionStep("guard", False, message))
        return self._finish_audit(result)

    def _finish_audit(
        self, result: RpzMigrationTransactionResult
    ) -> RpzMigrationTransactionResult:
        self.audit_v1.finish_result(result)
        return result

    @staticmethod
    def _integrity_error(plan: RpzExternalMigrationPlan) -> str | None:
        for item in plan.artifacts:
            if not item.path or not item.path.is_file():
                return f"Brak artefaktu od czasu utworzenia planu: {item.path}"
            current = hashlib.sha256(item.path.read_bytes()).hexdigest()
            if item.sha256 != current:
                return f"Suma SHA-256 zmieniła się od utworzenia planu: {item.path}"
        return None

    def _must_run(
        self, command: list[str], name: str, result: RpzMigrationTransactionResult
    ) -> None:
        outcome = self.command_runner(command, 30)
        message = (
            outcome.stdout or outcome.stderr
        ).strip() or f"kod {outcome.returncode}"
        result.steps.append(
            RpzMigrationTransactionStep(name, outcome.returncode == 0, message)
        )
        if outcome.returncode != 0:
            raise RuntimeError(f"{name}: {message}")

    def _post_activation_gate(
        self,
        plan: RpzExternalMigrationPlan,
        zone_file: Path,
        serial_before: int,
        result: RpzMigrationTransactionResult,
    ) -> None:
        checks = (
            ("managed-enabled", ["systemctl", "is-enabled", plan.managed_timer.name]),
            ("managed-active", ["systemctl", "is-active", plan.managed_timer.name]),
            ("bind-active", ["systemctl", "is-active", "bind9"]),
        )
        for name, command in checks:
            self._must_run(command, name, result)

        old = self.command_runner(
            ["systemctl", "is-active", plan.current_timer or ""], 30
        )
        old_inactive = old.returncode != 0 and old.stdout.strip() != "active"
        result.steps.append(
            RpzMigrationTransactionStep(
                "external-inactive",
                old_inactive,
                old.stdout.strip() or "inactive",
            )
        )
        if not old_inactive:
            raise RuntimeError("Timer EXTERNAL nadal jest aktywny")

        service = self.command_runner(
            [
                "systemctl",
                "show",
                plan.managed_service.name,
                "--property=Result",
                "--value",
            ],
            30,
        )
        service_result = service.stdout.strip()
        service_ok = service.returncode == 0 and service_result == "success"
        result.steps.append(
            RpzMigrationTransactionStep(
                "managed-service-result",
                service_ok,
                service_result or f"kod {service.returncode}",
            )
        )
        if not service_ok:
            raise RuntimeError("Usługa MANAGED nie zakończyła się wynikiem success")

        serial_after = self._zone_serial(plan.zone)
        serial_ok = serial_after is not None and serial_after >= serial_before
        result.steps.append(
            RpzMigrationTransactionStep(
                "serial",
                serial_ok,
                f"{serial_before} -> {serial_after if serial_after is not None else '-'}",
            )
        )
        if not serial_ok:
            raise RuntimeError("Serial RPZ jest niedostępny lub cofnął się")

        age = max(0, int(self.clock() - zone_file.stat().st_mtime))
        fresh = age <= self.max_zone_age
        result.steps.append(
            RpzMigrationTransactionStep(
                "freshness", fresh, f"wiek {age} s, limit {self.max_zone_age} s"
            )
        )
        if not fresh:
            raise RuntimeError("Plik RPZ nie jest świeży po przełączeniu")

    def _zone_serial(self, zone: str) -> int | None:
        outcome = self.command_runner(["rndc", "zonestatus", zone], 30)
        if outcome.returncode != 0:
            return None
        for line in outcome.stdout.splitlines():
            if line.strip().casefold().startswith("serial:"):
                value = line.split(":", 1)[1].strip()
                return int(value) if value.isdigit() else None
        return None

    def _rollback(
        self,
        plan: RpzExternalMigrationPlan,
        result: RpzMigrationTransactionResult,
        switched: bool,
        external_was_enabled: bool,
        external_was_active: bool,
    ) -> bool:
        ok = True
        if (
            switched
            and self.command_runner(
                ["systemctl", "disable", "--now", plan.managed_timer.name], 30
            ).returncode
            != 0
        ):
            ok = False
        for target in (plan.managed_timer, plan.managed_service, plan.managed_updater):
            try:
                if target.exists():
                    target.unlink()
            except OSError:
                ok = False
        if self.command_runner(["systemctl", "daemon-reload"], 30).returncode != 0:
            ok = False
        if switched:
            if external_was_enabled or external_was_active:
                action = "enable" if external_was_enabled else "start"
                command = ["systemctl", action]
                if external_was_active:
                    command.append("--now")
                command.append(plan.current_timer or "")
                if self.command_runner(command, 30).returncode != 0:
                    ok = False
        result.steps.append(
            RpzMigrationTransactionStep(
                "rollback",
                ok,
                "Usunięto MANAGED i przywrócono stan timera EXTERNAL"
                if ok
                else "Nie udało się w pełni przywrócić integracji EXTERNAL",
            )
        )
        return ok

    @staticmethod
    def _atomic_copy(source: Path, target: Path) -> None:
        RpzExternalMigrationTransaction._atomic_write(
            target, source.read_bytes(), source
        )

    @staticmethod
    def _atomic_write(target: Path, payload: bytes, metadata_source: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        metadata = metadata_source.stat()
        fd, raw = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        temporary = Path(raw)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, metadata.st_mode & 0o777)
            chown = getattr(os, "chown", None)
            if chown is not None:
                chown(temporary, metadata.st_uid, metadata.st_gid)
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()

    def _write_manifest(self, result: RpzMigrationTransactionResult) -> None:
        self.manifest_directory.mkdir(parents=True, exist_ok=True, mode=0o750)
        path = self.manifest_directory / f"{result.transaction_id}.json"
        result.manifest = str(path)
        payload = result.to_dict()
        payload["saved_at"] = (
            datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        )
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
