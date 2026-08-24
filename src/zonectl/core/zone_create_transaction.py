from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .runner import run
from .zone_lifecycle import ZoneCreatePlan


@dataclass(slots=True)
class ZoneCreateStep:
    name: str
    ok: bool
    message: str


@dataclass(slots=True)
class ZoneCreateResult:
    transaction_id: str
    zone: str
    status: str
    committed: bool = False
    rolled_back: bool = False
    manifest: str | None = None
    steps: list[ZoneCreateStep] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.steps) and all(step.ok for step in self.steps)


Validator = Callable[[str, Path], ZoneCreateStep]
ConfigValidator = Callable[[Path], ZoneCreateStep]
ZoneAction = Callable[[str], ZoneCreateStep]


class ZoneCreateTransaction:
    """Atomowo zastosuj plan utworzenia strefy z rollbackiem."""

    def __init__(
        self,
        manifest_directory: Path,
        *,
        root_config: Path = Path("/etc/bind/named.conf"),
        zone_validator: Validator | None = None,
        config_validator: ConfigValidator | None = None,
        activator: ZoneAction | None = None,
        loaded_verifier: ZoneAction | None = None,
    ) -> None:
        self.manifest_directory = manifest_directory
        self.root_config = root_config
        self.zone_validator = zone_validator or self._validate_zone
        self.config_validator = (
            config_validator or self._validate_config
        )
        self.activator = activator or self._activate_bind
        self.loaded_verifier = (
            loaded_verifier or self._verify_loaded
        )

    def apply(
        self,
        plan: ZoneCreatePlan,
        *,
        commit: bool = False,
        activate: bool = False,
    ) -> ZoneCreateResult:
        txid = (
            datetime.now().strftime("%Y%m%d-%H%M%S")
            + f"-create-{plan.zone_name}-{uuid.uuid4().hex[:8]}"
        )
        result = ZoneCreateResult(
            transaction_id=txid,
            zone=plan.zone_name,
            status="PLAN",
        )
        if plan.zone_file.exists():
            return self._finish(
                result,
                "CONFLICT",
                ZoneCreateStep(
                    "zone-file",
                    False,
                    f"Plik już istnieje: {plan.zone_file}",
                ),
            )
        if plan.zone_declaration_file.exists():
            return self._finish(
                result,
                "CONFLICT",
                ZoneCreateStep(
                    "zone-declaration",
                    False,
                    f"Plik już istnieje: {plan.zone_declaration_file}",
                ),
            )
        if not commit:
            return self._finish(
                result,
                "DRY-RUN",
                ZoneCreateStep(
                    "dry-run",
                    True,
                    "Nie utworzono plików",
                ),
                write_manifest=False,
            )

        config_existed = plan.managed_config.exists()
        original_config = (
            plan.managed_config.read_bytes()
            if config_existed
            else None
        )
        groups_existed = plan.groups_config.exists()
        original_groups = (
            plan.groups_config.read_bytes()
            if groups_existed
            else None
        )
        zone_created = False
        config_written = False
        declaration_created = False
        groups_written = False
        activation_attempted = False
        try:
            self._atomic_write(
                plan.zone_file,
                plan.zone_text.encode("utf-8"),
            )
            zone_created = True
            result.steps.append(
                ZoneCreateStep(
                    "zone-file",
                    True,
                    f"Utworzono {plan.zone_file}",
                )
            )

            self._atomic_write(
                plan.zone_declaration_file,
                plan.bind_declaration.encode("utf-8"),
            )
            declaration_created = True
            result.steps.append(
                ZoneCreateStep(
                    "zone-declaration",
                    True,
                    f"Utworzono {plan.zone_declaration_file}",
                )
            )

            current = original_config or b""
            separator = b"" if not current or current.endswith(b"\n") else b"\n"
            include_line = (
                f'include "{plan.zone_declaration_file}";\n'
            ).encode("utf-8")
            if include_line in current.splitlines(keepends=True):
                raise RuntimeError(
                    "Indeks już zawiera deklarację strefy"
                )
            updated = (
                current
                + separator
                + include_line
            )
            self._atomic_write(plan.managed_config, updated)
            config_written = True
            result.steps.append(
                ZoneCreateStep(
                    "managed-config",
                    True,
                    f"Zaktualizowano {plan.managed_config}",
                )
            )

            if plan.groups_text is not None:
                self._atomic_write(
                    plan.groups_config,
                    plan.groups_text.encode("utf-8"),
                )
                groups_written = True
                result.steps.append(
                    ZoneCreateStep(
                        "groups-config",
                        True,
                        f"Przypisano strefę do grupy {plan.group}",
                    )
                )

            zone_step = self.zone_validator(
                plan.zone_name,
                plan.zone_file,
            )
            result.steps.append(zone_step)
            if not zone_step.ok:
                raise RuntimeError(zone_step.message)

            config_step = self.config_validator(self.root_config)
            result.steps.append(config_step)
            if not config_step.ok:
                raise RuntimeError(config_step.message)

            if activate:
                activation_attempted = True
                activation_step = self.activator(plan.zone_name)
                result.steps.append(activation_step)
                if not activation_step.ok:
                    raise RuntimeError(activation_step.message)

                loaded_step = self.loaded_verifier(plan.zone_name)
                result.steps.append(loaded_step)
                if not loaded_step.ok:
                    raise RuntimeError(loaded_step.message)

            result.committed = True
            return self._finish(result, "COMMIT")

        except Exception as exc:
            result.steps.append(
                ZoneCreateStep("transaction", False, str(exc))
            )
            rollback_ok = True
            try:
                if config_written:
                    if original_config is None:
                        plan.managed_config.unlink(missing_ok=True)
                    else:
                        self._atomic_write(
                            plan.managed_config,
                            original_config,
                        )
                if groups_written:
                    if original_groups is None:
                        plan.groups_config.unlink(missing_ok=True)
                    else:
                        self._atomic_write(
                            plan.groups_config,
                            original_groups,
                        )
                if zone_created:
                    plan.zone_file.unlink(missing_ok=True)
                if declaration_created:
                    plan.zone_declaration_file.unlink(
                        missing_ok=True
                    )
                if activation_attempted:
                    restore_step = self.activator(plan.zone_name)
                    result.steps.append(
                        ZoneCreateStep(
                            "rndc-reconfig-rollback",
                            restore_step.ok,
                            restore_step.message,
                        )
                    )
                    if not restore_step.ok:
                        raise RuntimeError(restore_step.message)
            except Exception as rollback_error:
                rollback_ok = False
                result.steps.append(
                    ZoneCreateStep(
                        "rollback",
                        False,
                        str(rollback_error),
                    )
                )
            else:
                result.steps.append(
                    ZoneCreateStep(
                        "rollback",
                        True,
                        "Przywrócono stan sprzed transakcji",
                    )
                )
            result.rolled_back = rollback_ok
            return self._finish(
                result,
                "ROLLED-BACK" if rollback_ok else "ROLLBACK-FAILED",
            )

    def _finish(
        self,
        result: ZoneCreateResult,
        status: str,
        step: ZoneCreateStep | None = None,
        *,
        write_manifest: bool = True,
    ) -> ZoneCreateResult:
        result.status = status
        if step is not None:
            result.steps.append(step)
        if write_manifest:
            self.manifest_directory.mkdir(
                parents=True,
                exist_ok=True,
                mode=0o750,
            )
            path = (
                self.manifest_directory
                / f"{result.transaction_id}.json"
            )
            result.manifest = str(path)
            payload = asdict(result)
            payload["saved_at"] = (
                datetime.now(timezone.utc)
                .astimezone()
                .isoformat(timespec="seconds")
            )
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return result

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        if path.exists():
            owner = path.stat()
            uid, gid = owner.st_uid, owner.st_gid
            mode = owner.st_mode & 0o777
        else:
            parent = path.parent.stat()
            uid, gid = parent.st_uid, parent.st_gid
            mode = 0o640
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            dir=path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, mode)
            os.chown(temporary, uid, gid)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _validate_zone(name: str, path: Path) -> ZoneCreateStep:
        command = ["named-checkzone", name, str(path)]
        outcome = run(command, 30)
        return ZoneCreateStep(
            "named-checkzone",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip()
            or f"kod {outcome.returncode}",
        )

    @staticmethod
    def _validate_config(path: Path) -> ZoneCreateStep:
        command = ["named-checkconf", str(path)]
        outcome = run(command, 30)
        return ZoneCreateStep(
            "named-checkconf",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip()
            or f"kod {outcome.returncode}",
        )

    @staticmethod
    def _activate_bind(_name: str) -> ZoneCreateStep:
        outcome = run(["rndc", "reconfig"], 30)
        return ZoneCreateStep(
            "rndc-reconfig",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip()
            or f"kod {outcome.returncode}",
        )

    @staticmethod
    def _verify_loaded(name: str) -> ZoneCreateStep:
        outcome = None
        for attempt in range(10):
            outcome = run(["rndc", "zonestatus", name], 30)
            if outcome.returncode == 0:
                break
            if attempt < 9:
                time.sleep(0.25)
        assert outcome is not None
        return ZoneCreateStep(
            "rndc-zonestatus",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip()
            or f"kod {outcome.returncode}",
        )
