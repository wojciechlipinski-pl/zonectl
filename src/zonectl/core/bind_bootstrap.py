from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .runner import run


@dataclass(frozen=True, slots=True)
class BindBootstrapPlan:
    local_config: Path
    managed_index: Path
    managed_zone_directory: Path
    root_config: Path
    include_line: str
    include_present: bool

    @property
    def actions(self) -> tuple[str, ...]:
        actions: list[str] = []
        if not self.managed_zone_directory.exists():
            actions.append(f"utwórz katalog {self.managed_zone_directory}")
        if not self.managed_index.exists():
            actions.append(f"utwórz indeks {self.managed_index}")
        if not self.include_present:
            actions.append(f"dodaj include do {self.local_config}")
        actions.extend(
            (
                f"wykonaj named-checkconf {self.root_config}",
                "zapisz manifest operacji",
            )
        )
        return tuple(actions)


@dataclass(slots=True)
class BindBootstrapStep:
    name: str
    ok: bool
    message: str


@dataclass(slots=True)
class BindBootstrapResult:
    transaction_id: str
    status: str
    committed: bool = False
    rolled_back: bool = False
    manifest: str | None = None
    backup: str | None = None
    steps: list[BindBootstrapStep] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.steps) and all(step.ok for step in self.steps)


ConfigValidator = Callable[[Path], BindBootstrapStep]


class BindBootstrapError(RuntimeError):
    """Błąd planowania bezpiecznego fragmentu konfiguracji BIND."""


class BindBootstrapTransaction:
    """Instaluje zarządzany include ZoneCTL z walidacją i rollbackiem."""

    def __init__(
        self,
        manifest_directory: Path,
        *,
        backup_directory: Path | None = None,
        config_validator: ConfigValidator | None = None,
    ) -> None:
        self.manifest_directory = manifest_directory
        self.backup_directory = backup_directory or manifest_directory / "backups"
        self.config_validator = config_validator or self._validate_config

    @staticmethod
    def plan(
        *,
        local_config: Path = Path("/etc/bind/named.conf.local"),
        managed_index: Path = Path("/etc/bind/zonectl-zones.conf"),
        managed_zone_directory: Path = Path("/etc/bind/zonectl-zones.d"),
        root_config: Path = Path("/etc/bind/named.conf"),
    ) -> BindBootstrapPlan:
        if not local_config.is_file():
            raise BindBootstrapError(
                f"Nie istnieje konfiguracja lokalna BIND: {local_config}"
            )
        include_line = f'include "{managed_index}";'
        lines = [
            line.strip()
            for line in local_config.read_text(encoding="utf-8").splitlines()
        ]
        occurrences = sum(line == include_line for line in lines)
        if occurrences > 1:
            raise BindBootstrapError(
                f"Powielony include ZoneCTL w {local_config}: {occurrences}"
            )
        if managed_index.exists() and not managed_index.is_file():
            raise BindBootstrapError(
                f"Indeks nie jest zwykłym plikiem: {managed_index}"
            )
        if managed_zone_directory.exists() and not managed_zone_directory.is_dir():
            raise BindBootstrapError(
                f"Ścieżka deklaracji nie jest katalogiem: "
                f"{managed_zone_directory}"
            )
        return BindBootstrapPlan(
            local_config=local_config,
            managed_index=managed_index,
            managed_zone_directory=managed_zone_directory,
            root_config=root_config,
            include_line=include_line,
            include_present=occurrences == 1,
        )

    def apply(
        self,
        plan: BindBootstrapPlan,
        *,
        commit: bool = False,
    ) -> BindBootstrapResult:
        txid = (
            datetime.now().strftime("%Y%m%d-%H%M%S")
            + f"-bind-bootstrap-{uuid.uuid4().hex[:8]}"
        )
        result = BindBootstrapResult(txid, "PLAN")
        if not commit:
            result.steps.append(
                BindBootstrapStep("dry-run", True, "Nie zmieniono konfiguracji")
            )
            result.status = "DRY-RUN"
            return result

        local_original = plan.local_config.read_bytes()
        index_existed = plan.managed_index.exists()
        directory_existed = plan.managed_zone_directory.exists()
        include_added = False
        index_created = False
        directory_created = False
        try:
            self.backup_directory.mkdir(parents=True, exist_ok=True, mode=0o750)
            backup = self.backup_directory / f"{txid}-named.conf.local"
            self._atomic_write(backup, local_original)
            result.backup = str(backup)
            result.steps.append(
                BindBootstrapStep("backup", True, f"Backup: {backup}")
            )

            if not directory_existed:
                plan.managed_zone_directory.mkdir(
                    parents=True, mode=0o750
                )
                directory_created = True
                result.steps.append(
                    BindBootstrapStep(
                        "declaration-directory",
                        True,
                        f"Utworzono {plan.managed_zone_directory}",
                    )
                )

            if not index_existed:
                self._atomic_write(
                    plan.managed_index,
                    (
                        "# ZoneCTL managed zone includes\n"
                        "# One include per managed zone.\n"
                    ).encode("utf-8"),
                )
                index_created = True
                result.steps.append(
                    BindBootstrapStep(
                        "managed-index",
                        True,
                        f"Utworzono {plan.managed_index}",
                    )
                )

            if not plan.include_present:
                separator = (
                    b"" if not local_original or local_original.endswith(b"\n")
                    else b"\n"
                )
                updated = (
                    local_original
                    + separator
                    + b"\n// ZoneCTL managed zones\n"
                    + (plan.include_line + "\n").encode("utf-8")
                )
                self._atomic_write(plan.local_config, updated)
                include_added = True
                result.steps.append(
                    BindBootstrapStep(
                        "local-config",
                        True,
                        f"Dodano include do {plan.local_config}",
                    )
                )

            validation = self.config_validator(plan.root_config)
            result.steps.append(validation)
            if not validation.ok:
                raise RuntimeError(validation.message)

            result.committed = True
            result.status = "COMMIT"
            return self._save_manifest(result)
        except Exception as exc:
            result.steps.append(
                BindBootstrapStep("transaction", False, str(exc))
            )
            rollback_ok = True
            try:
                if include_added:
                    self._atomic_write(plan.local_config, local_original)
                if index_created:
                    plan.managed_index.unlink(missing_ok=True)
                if directory_created:
                    plan.managed_zone_directory.rmdir()
            except OSError as rollback_error:
                rollback_ok = False
                result.steps.append(
                    BindBootstrapStep("rollback", False, str(rollback_error))
                )
            else:
                result.steps.append(
                    BindBootstrapStep(
                        "rollback",
                        True,
                        "Przywrócono konfigurację sprzed transakcji",
                    )
                )
            result.rolled_back = rollback_ok
            result.status = (
                "ROLLED-BACK" if rollback_ok else "ROLLBACK-FAILED"
            )
            return self._save_manifest(result)

    def _save_manifest(
        self, result: BindBootstrapResult
    ) -> BindBootstrapResult:
        self.manifest_directory.mkdir(parents=True, exist_ok=True, mode=0o750)
        path = self.manifest_directory / f"{result.transaction_id}.json"
        result.manifest = str(path)
        payload = asdict(result)
        payload["saved_at"] = (
            datetime.now(timezone.utc)
            .astimezone()
            .isoformat(timespec="seconds")
        )
        self._atomic_write(
            path,
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        return result

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o640)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _validate_config(path: Path) -> BindBootstrapStep:
        outcome = run(["named-checkconf", str(path)], 30)
        return BindBootstrapStep(
            "named-checkconf",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip()
            or f"kod {outcome.returncode}",
        )
