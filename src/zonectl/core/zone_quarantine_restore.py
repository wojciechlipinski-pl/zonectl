from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from .runner import run


@dataclass(frozen=True, slots=True)
class QuarantineRestorePlan:
    zone_name: str
    package_directory: Path
    package_manifest: Path
    packaged_zone: Path
    packaged_declaration: Path
    zone_file: Path
    active_declaration: Path
    managed_index: Path
    root_config: Path
    include_line: str


@dataclass(slots=True)
class QuarantineRestoreStep:
    name: str
    ok: bool
    message: str


@dataclass(slots=True)
class QuarantineRestoreResult:
    transaction_id: str
    zone: str
    status: str
    package_directory: str
    committed: bool = False
    rolled_back: bool = False
    steps: list[QuarantineRestoreStep] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.steps) and all(step.ok for step in self.steps)


ZoneValidator = Callable[[str, Path], QuarantineRestoreStep]
ConfigValidator = Callable[[Path], QuarantineRestoreStep]
ZoneAction = Callable[[str], QuarantineRestoreStep]


class QuarantineRestoreError(RuntimeError):
    """Pakiet kwarantanny nie pozwala na bezpieczne odtworzenie."""


class QuarantineRestoreTransaction:
    """Odtwarza i aktywuje strefę ze zweryfikowanego pakietu kwarantanny."""

    def __init__(
        self,
        *,
        zone_validator: ZoneValidator | None = None,
        config_validator: ConfigValidator | None = None,
        activator: ZoneAction | None = None,
        loaded_verifier: ZoneAction | None = None,
    ) -> None:
        self.zone_validator = zone_validator or self._validate_zone
        self.config_validator = config_validator or self._validate_config
        self.activator = activator or self._activate_bind
        self.loaded_verifier = loaded_verifier or self._verify_loaded

    @staticmethod
    def plan(
        zone_name: str,
        *,
        package_directory: Path,
        zone_file: Path,
        active_declaration: Path,
        managed_index: Path,
        root_config: Path = Path("/etc/bind/named.conf"),
    ) -> QuarantineRestorePlan:
        name = zone_name.strip().rstrip(".").casefold()
        manifest_path = package_directory / "manifest.json"
        zone_copy = package_directory / "zone.db"
        declaration_copy = package_directory / "zone.conf"
        for path in (manifest_path, zone_copy, declaration_copy, managed_index):
            if not path.is_file():
                raise QuarantineRestoreError(f"Brak wymaganego pliku: {path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("zone") != name or manifest.get("status") != "QUARANTINED":
            raise QuarantineRestoreError("Manifest nie opisuje wskazanej strefy")
        for filename, expected in manifest.get("files", {}).items():
            path = package_directory / filename
            if not path.is_file() or QuarantineRestoreTransaction._sha256(path) != expected:
                raise QuarantineRestoreError(f"Błędna suma kontrolna: {filename}")
        if set(manifest.get("files", {})) != {"zone.db", "zone.conf"}:
            raise QuarantineRestoreError("Manifest ma niekompletną listę plików")
        if zone_file.exists() or active_declaration.exists():
            raise QuarantineRestoreError("Docelowe pliki strefy już istnieją")
        include_line = f'include "{active_declaration}";'
        if any(
            line.strip() == include_line
            for line in managed_index.read_text(encoding="utf-8").splitlines()
        ):
            raise QuarantineRestoreError("Indeks już zawiera strefę")
        return QuarantineRestorePlan(
            name,
            package_directory,
            manifest_path,
            zone_copy,
            declaration_copy,
            zone_file,
            active_declaration,
            managed_index,
            root_config,
            include_line,
        )

    def apply(
        self,
        plan: QuarantineRestorePlan,
        *,
        commit: bool = False,
    ) -> QuarantineRestoreResult:
        txid = (
            datetime.now().strftime("%Y%m%d-%H%M%S")
            + f"-restore-quarantine-{plan.zone_name}-{uuid.uuid4().hex[:8]}"
        )
        result = QuarantineRestoreResult(
            txid, plan.zone_name, "PLAN", str(plan.package_directory)
        )
        if not commit:
            result.status = "DRY-RUN"
            result.steps.append(
                QuarantineRestoreStep("dry-run", True, "Nie odtworzono danych")
            )
            return result

        index_original = plan.managed_index.read_bytes()
        index_stat = plan.managed_index.stat()
        zone_parent = plan.zone_file.parent.stat()
        declaration_parent = plan.active_declaration.parent.stat()
        zone_created = declaration_created = index_written = False
        activation_attempted = False
        try:
            self._atomic_write(
                plan.zone_file,
                plan.packaged_zone.read_bytes(),
                0o640,
                zone_parent.st_uid,
                zone_parent.st_gid,
            )
            zone_created = True
            result.steps.append(
                QuarantineRestoreStep("zone-file", True, f"Odtworzono {plan.zone_file}")
            )
            check_zone = self.zone_validator(plan.zone_name, plan.zone_file)
            result.steps.append(check_zone)
            if not check_zone.ok:
                raise RuntimeError(check_zone.message)

            self._atomic_write(
                plan.active_declaration,
                plan.packaged_declaration.read_bytes(),
                0o640,
                declaration_parent.st_uid,
                declaration_parent.st_gid,
            )
            declaration_created = True
            separator = b"" if not index_original or index_original.endswith(b"\n") else b"\n"
            self._atomic_write(
                plan.managed_index,
                index_original + separator + (plan.include_line + "\n").encode(),
                index_stat.st_mode & 0o777,
                index_stat.st_uid,
                index_stat.st_gid,
            )
            index_written = True
            result.steps.append(
                QuarantineRestoreStep("configuration", True, "Odtworzono deklarację i include")
            )
            check_config = self.config_validator(plan.root_config)
            result.steps.append(check_config)
            if not check_config.ok:
                raise RuntimeError(check_config.message)
            activation_attempted = True
            activation = self.activator(plan.zone_name)
            result.steps.append(activation)
            if not activation.ok:
                raise RuntimeError(activation.message)
            loaded = self.loaded_verifier(plan.zone_name)
            result.steps.append(loaded)
            if not loaded.ok:
                raise RuntimeError(loaded.message)
            result.committed = True
            result.status = "RESTORED"
            return result
        except Exception as exc:
            result.steps.append(QuarantineRestoreStep("transaction", False, str(exc)))
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
                    plan.active_declaration.unlink(missing_ok=True)
                if zone_created:
                    plan.zone_file.unlink(missing_ok=True)
                if activation_attempted:
                    restored = self.activator(plan.zone_name)
                    result.steps.append(
                        QuarantineRestoreStep("rndc-reconfig-rollback", restored.ok, restored.message)
                    )
                    if not restored.ok:
                        raise RuntimeError(restored.message)
            except Exception as rollback_error:
                rollback_ok = False
                result.steps.append(
                    QuarantineRestoreStep("rollback", False, str(rollback_error))
                )
            else:
                result.steps.append(
                    QuarantineRestoreStep("rollback", True, "Usunięto odtworzone kopie robocze")
                )
            result.rolled_back = rollback_ok
            result.status = "ROLLED-BACK" if rollback_ok else "ROLLBACK-FAILED"
            return result

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _atomic_write(path: Path, content: bytes, mode: int, uid: int, gid: int) -> None:
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
    def _validate_zone(name: str, path: Path) -> QuarantineRestoreStep:
        outcome = run(["named-checkzone", name, str(path)], 30)
        return QuarantineRestoreStep("named-checkzone", outcome.returncode == 0, (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}")

    @staticmethod
    def _validate_config(path: Path) -> QuarantineRestoreStep:
        outcome = run(["named-checkconf", str(path)], 30)
        return QuarantineRestoreStep("named-checkconf", outcome.returncode == 0, (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}")

    @staticmethod
    def _activate_bind(_name: str) -> QuarantineRestoreStep:
        outcome = run(["rndc", "reconfig"], 30)
        return QuarantineRestoreStep("rndc-reconfig", outcome.returncode == 0, (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}")

    @staticmethod
    def _verify_loaded(name: str) -> QuarantineRestoreStep:
        outcome = None
        for attempt in range(10):
            outcome = run(["rndc", "zonestatus", name], 30)
            if outcome.returncode == 0:
                break
            if attempt < 9:
                time.sleep(0.25)
        assert outcome is not None
        return QuarantineRestoreStep("rndc-zonestatus", outcome.returncode == 0, (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}")
