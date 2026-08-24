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


@dataclass(frozen=True, slots=True)
class ZoneRestorePlan:
    zone_name: str
    zone_file: Path
    declaration_file: Path
    archived_declaration: Path
    managed_index: Path
    root_config: Path
    include_line: str


@dataclass(slots=True)
class ZoneRestoreStep:
    name: str
    ok: bool
    message: str


@dataclass(slots=True)
class ZoneRestoreResult:
    transaction_id: str
    zone: str
    status: str
    committed: bool = False
    rolled_back: bool = False
    manifest: str | None = None
    steps: list[ZoneRestoreStep] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.steps) and all(step.ok for step in self.steps)


ZoneValidator = Callable[[str, Path], ZoneRestoreStep]
ConfigValidator = Callable[[Path], ZoneRestoreStep]
ZoneAction = Callable[[str], ZoneRestoreStep]


class ZoneRestoreError(RuntimeError):
    """Nie można bezpiecznie zaplanować przywrócenia strefy."""


class ZoneRestoreTransaction:
    """Przywraca wyłączoną strefę do aktywnej konfiguracji BIND."""

    def __init__(
        self,
        manifest_directory: Path,
        *,
        zone_validator: ZoneValidator | None = None,
        config_validator: ConfigValidator | None = None,
        activator: ZoneAction | None = None,
        loaded_verifier: ZoneAction | None = None,
    ) -> None:
        self.manifest_directory = manifest_directory
        self.zone_validator = zone_validator or self._validate_zone
        self.config_validator = config_validator or self._validate_config
        self.activator = activator or self._activate_bind
        self.loaded_verifier = loaded_verifier or self._verify_loaded

    @staticmethod
    def plan(
        zone_name: str,
        *,
        zone_file: Path,
        declaration_file: Path,
        managed_index: Path,
        disabled_root: Path = Path("/var/lib/zonectl/disabled-zones"),
        root_config: Path = Path("/etc/bind/named.conf"),
    ) -> ZoneRestorePlan:
        name = zone_name.strip().rstrip(".").casefold()
        archived = disabled_root / name / declaration_file.name
        if not name:
            raise ZoneRestoreError("Wymagana jest nazwa strefy")
        if not zone_file.is_file():
            raise ZoneRestoreError(f"Brak pliku strefy: {zone_file}")
        if not archived.is_file():
            raise ZoneRestoreError(f"Brak archiwalnej deklaracji: {archived}")
        if declaration_file.exists():
            raise ZoneRestoreError(
                f"Aktywna deklaracja już istnieje: {declaration_file}"
            )
        if not managed_index.is_file():
            raise ZoneRestoreError(f"Brak indeksu: {managed_index}")
        include_line = f'include "{declaration_file}";'
        occurrences = sum(
            line.strip() == include_line
            for line in managed_index.read_text(encoding="utf-8").splitlines()
        )
        if occurrences:
            raise ZoneRestoreError("Indeks już zawiera przywracaną strefę")
        return ZoneRestorePlan(
            name,
            zone_file,
            declaration_file,
            archived,
            managed_index,
            root_config,
            include_line,
        )

    def apply(
        self,
        plan: ZoneRestorePlan,
        *,
        commit: bool = False,
    ) -> ZoneRestoreResult:
        txid = (
            datetime.now().strftime("%Y%m%d-%H%M%S")
            + f"-restore-{plan.zone_name}-{uuid.uuid4().hex[:8]}"
        )
        result = ZoneRestoreResult(txid, plan.zone_name, "PLAN")
        if not commit:
            result.status = "DRY-RUN"
            result.steps.append(
                ZoneRestoreStep("dry-run", True, "Nie zmieniono konfiguracji")
            )
            return result

        index_original = plan.managed_index.read_bytes()
        index_stat = plan.managed_index.stat()
        archived_content = plan.archived_declaration.read_bytes()
        archived_stat = plan.archived_declaration.stat()
        declaration_created = False
        index_written = False
        activation_attempted = False
        try:
            zone_check = self.zone_validator(plan.zone_name, plan.zone_file)
            result.steps.append(zone_check)
            if not zone_check.ok:
                raise RuntimeError(zone_check.message)

            self._atomic_write(
                plan.declaration_file,
                archived_content,
                archived_stat.st_mode & 0o777,
                archived_stat.st_uid,
                archived_stat.st_gid,
            )
            declaration_created = True
            result.steps.append(
                ZoneRestoreStep(
                    "restore-declaration",
                    True,
                    f"Przywrócono {plan.declaration_file}",
                )
            )

            separator = (
                b"" if not index_original or index_original.endswith(b"\n") else b"\n"
            )
            updated = (
                index_original
                + separator
                + (plan.include_line + "\n").encode("utf-8")
            )
            self._atomic_write(
                plan.managed_index,
                updated,
                index_stat.st_mode & 0o777,
                index_stat.st_uid,
                index_stat.st_gid,
            )
            index_written = True
            result.steps.append(
                ZoneRestoreStep("managed-index", True, "Dodano include strefy")
            )

            config_check = self.config_validator(plan.root_config)
            result.steps.append(config_check)
            if not config_check.ok:
                raise RuntimeError(config_check.message)

            activation_attempted = True
            activation = self.activator(plan.zone_name)
            result.steps.append(activation)
            if not activation.ok:
                raise RuntimeError(activation.message)

            loaded = self.loaded_verifier(plan.zone_name)
            result.steps.append(loaded)
            if not loaded.ok:
                raise RuntimeError(loaded.message)

            plan.archived_declaration.unlink()
            try:
                plan.archived_declaration.parent.rmdir()
            except OSError:
                pass
            result.steps.append(
                ZoneRestoreStep("consume-archive", True, "Usunięto użyte archiwum")
            )
            result.committed = True
            result.status = "RESTORED"
            return self._save(result)
        except Exception as exc:
            result.steps.append(ZoneRestoreStep("transaction", False, str(exc)))
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
                if declaration_created:
                    plan.declaration_file.unlink(missing_ok=True)
                if activation_attempted:
                    restored = self.activator(plan.zone_name)
                    result.steps.append(
                        ZoneRestoreStep(
                            "rndc-reconfig-rollback", restored.ok, restored.message
                        )
                    )
                    if not restored.ok:
                        raise RuntimeError(restored.message)
            except Exception as rollback_error:
                rollback_ok = False
                result.steps.append(
                    ZoneRestoreStep("rollback", False, str(rollback_error))
                )
            else:
                result.steps.append(
                    ZoneRestoreStep("rollback", True, "Strefa pozostała wyłączona")
                )
            result.rolled_back = rollback_ok
            result.status = "ROLLED-BACK" if rollback_ok else "ROLLBACK-FAILED"
            return self._save(result)

    def _save(self, result: ZoneRestoreResult) -> ZoneRestoreResult:
        self.manifest_directory.mkdir(parents=True, exist_ok=True, mode=0o750)
        path = self.manifest_directory / f"{result.transaction_id}.json"
        result.manifest = str(path)
        payload = asdict(result)
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
    def _validate_zone(name: str, path: Path) -> ZoneRestoreStep:
        outcome = run(["named-checkzone", name, str(path)], 30)
        return ZoneRestoreStep(
            "named-checkzone",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}",
        )

    @staticmethod
    def _validate_config(path: Path) -> ZoneRestoreStep:
        outcome = run(["named-checkconf", str(path)], 30)
        return ZoneRestoreStep(
            "named-checkconf",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}",
        )

    @staticmethod
    def _activate_bind(_name: str) -> ZoneRestoreStep:
        outcome = run(["rndc", "reconfig"], 30)
        return ZoneRestoreStep(
            "rndc-reconfig",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}",
        )

    @staticmethod
    def _verify_loaded(name: str) -> ZoneRestoreStep:
        outcome = None
        for attempt in range(10):
            outcome = run(["rndc", "zonestatus", name], 30)
            if outcome.returncode == 0:
                break
            if attempt < 9:
                time.sleep(0.25)
        assert outcome is not None
        return ZoneRestoreStep(
            "rndc-zonestatus",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}",
        )
