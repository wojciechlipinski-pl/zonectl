from __future__ import annotations

import json
import getpass
import os
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .runner import run


@dataclass(frozen=True, slots=True)
class ZoneDisablePlan:
    zone_name: str
    zone_file: Path
    declaration_file: Path
    managed_index: Path
    root_config: Path
    disabled_directory: Path
    archived_declaration: Path
    include_line: str
    reason: str


@dataclass(slots=True)
class ZoneDisableStep:
    name: str
    ok: bool
    message: str


@dataclass(slots=True)
class ZoneDisableResult:
    transaction_id: str
    zone: str
    status: str
    reason: str
    committed: bool = False
    rolled_back: bool = False
    manifest: str | None = None
    steps: list[ZoneDisableStep] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.steps) and all(step.ok for step in self.steps)


ZoneAction = Callable[[str], ZoneDisableStep]
ConfigValidator = Callable[[Path], ZoneDisableStep]


class ZoneDisableError(RuntimeError):
    """Nie można bezpiecznie zaplanować wyłączenia strefy."""


class ZoneDisableTransaction:
    """Odwracalnie usuwa strefę z aktywnej konfiguracji BIND."""

    def __init__(
        self,
        manifest_directory: Path,
        *,
        config_validator: ConfigValidator | None = None,
        activator: ZoneAction | None = None,
        unavailable_verifier: ZoneAction | None = None,
    ) -> None:
        self.manifest_directory = manifest_directory
        self.config_validator = config_validator or self._validate_config
        self.activator = activator or self._activate_bind
        self.unavailable_verifier = (
            unavailable_verifier or self._verify_unavailable
        )

    @staticmethod
    def plan(
        zone_name: str,
        *,
        zone_file: Path,
        declaration_file: Path,
        managed_index: Path,
        root_config: Path = Path("/etc/bind/named.conf"),
        disabled_root: Path = Path("/var/lib/zonectl/disabled-zones"),
        reason: str,
    ) -> ZoneDisablePlan:
        name = zone_name.strip().rstrip(".").casefold()
        if not name or not reason.strip():
            raise ZoneDisableError("Wymagana jest nazwa strefy i przyczyna")
        for path, label in (
            (zone_file, "plik strefy"),
            (declaration_file, "deklaracja"),
            (managed_index, "indeks"),
        ):
            if not path.is_file():
                raise ZoneDisableError(f"Brak {label}: {path}")
        include_line = f'include "{declaration_file}";'
        occurrences = sum(
            line.strip() == include_line
            for line in managed_index.read_text(encoding="utf-8").splitlines()
        )
        if occurrences != 1:
            raise ZoneDisableError(
                f"Oczekiwano jednego include strefy, znaleziono: {occurrences}"
            )
        directory = disabled_root / name
        archived = directory / declaration_file.name
        if archived.exists():
            raise ZoneDisableError(f"Archiwum już istnieje: {archived}")
        return ZoneDisablePlan(
            name,
            zone_file,
            declaration_file,
            managed_index,
            root_config,
            directory,
            archived,
            include_line,
            reason.strip(),
        )

    def apply(
        self,
        plan: ZoneDisablePlan,
        *,
        commit: bool = False,
    ) -> ZoneDisableResult:
        txid = (
            datetime.now().strftime("%Y%m%d-%H%M%S")
            + f"-disable-{plan.zone_name}-{uuid.uuid4().hex[:8]}"
        )
        result = ZoneDisableResult(txid, plan.zone_name, "PLAN", plan.reason)
        if not commit:
            result.status = "DRY-RUN"
            result.steps.append(
                ZoneDisableStep("dry-run", True, "Nie zmieniono konfiguracji")
            )
            return result

        index_original = plan.managed_index.read_bytes()
        declaration_original = plan.declaration_file.read_bytes()
        declaration_stat = plan.declaration_file.stat()
        index_stat = plan.managed_index.stat()
        archived = False
        index_written = False
        activation_attempted = False
        try:
            plan.disabled_directory.mkdir(parents=True, mode=0o750)
            self._atomic_write(
                plan.archived_declaration,
                declaration_original,
                0o640,
                declaration_stat.st_uid,
                declaration_stat.st_gid,
            )
            archived = True
            plan.declaration_file.unlink()
            result.steps.append(
                ZoneDisableStep(
                    "archive-declaration",
                    True,
                    f"Archiwum: {plan.archived_declaration}",
                )
            )

            kept = [
                line
                for line in index_original.decode("utf-8").splitlines(keepends=True)
                if line.strip() != plan.include_line
            ]
            self._atomic_write(
                plan.managed_index,
                "".join(kept).encode("utf-8"),
                index_stat.st_mode & 0o777,
                index_stat.st_uid,
                index_stat.st_gid,
            )
            index_written = True
            result.steps.append(
                ZoneDisableStep("managed-index", True, "Usunięto include strefy")
            )

            check = self.config_validator(plan.root_config)
            result.steps.append(check)
            if not check.ok:
                raise RuntimeError(check.message)

            activation_attempted = True
            activation = self.activator(plan.zone_name)
            result.steps.append(activation)
            if not activation.ok:
                raise RuntimeError(activation.message)

            unavailable = self.unavailable_verifier(plan.zone_name)
            result.steps.append(unavailable)
            if not unavailable.ok:
                raise RuntimeError(unavailable.message)

            result.committed = True
            result.status = "DISABLED"
            return self._save(result)
        except Exception as exc:
            result.steps.append(ZoneDisableStep("transaction", False, str(exc)))
            rollback_ok = True
            try:
                if index_written:
                    self._atomic_write(
                        plan.managed_index,
                        index_original,
                        index_stat.st_mode & 0o777,
                        index_stat.st_uid,
                        index_stat.st_gid,
                    )
                if archived:
                    self._atomic_write(
                        plan.declaration_file,
                        declaration_original,
                        declaration_stat.st_mode & 0o777,
                        declaration_stat.st_uid,
                        declaration_stat.st_gid,
                    )
                    plan.archived_declaration.unlink(missing_ok=True)
                if activation_attempted:
                    restored = self.activator(plan.zone_name)
                    result.steps.append(
                        ZoneDisableStep(
                            "rndc-reconfig-rollback",
                            restored.ok,
                            restored.message,
                        )
                    )
                    if not restored.ok:
                        raise RuntimeError(restored.message)
            except Exception as rollback_error:
                rollback_ok = False
                result.steps.append(
                    ZoneDisableStep("rollback", False, str(rollback_error))
                )
            else:
                result.steps.append(
                    ZoneDisableStep("rollback", True, "Przywrócono aktywną strefę")
                )
            result.rolled_back = rollback_ok
            result.status = "ROLLED-BACK" if rollback_ok else "ROLLBACK-FAILED"
            return self._save(result)

    def _save(self, result: ZoneDisableResult) -> ZoneDisableResult:
        self.manifest_directory.mkdir(parents=True, exist_ok=True, mode=0o750)
        path = self.manifest_directory / f"{result.transaction_id}.json"
        result.manifest = str(path)
        payload = asdict(result)
        payload["operator"] = getpass.getuser()
        payload["saved_at"] = datetime.now(timezone.utc).astimezone().isoformat(
            timespec="seconds"
        )
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result

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
            os.chown(temporary, uid, gid)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _validate_config(path: Path) -> ZoneDisableStep:
        outcome = run(["named-checkconf", str(path)], 30)
        return ZoneDisableStep(
            "named-checkconf",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}",
        )

    @staticmethod
    def _activate_bind(_name: str) -> ZoneDisableStep:
        outcome = run(["rndc", "reconfig"], 30)
        return ZoneDisableStep(
            "rndc-reconfig",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}",
        )

    @staticmethod
    def _verify_unavailable(name: str) -> ZoneDisableStep:
        outcome = None
        for attempt in range(10):
            outcome = run(["rndc", "zonestatus", name], 30)
            if outcome.returncode != 0:
                return ZoneDisableStep(
                    "rndc-zone-unavailable", True, "Strefa nie jest załadowana"
                )
            if attempt < 9:
                time.sleep(0.25)
        return ZoneDisableStep(
            "rndc-zone-unavailable", False, "Strefa nadal jest załadowana"
        )
