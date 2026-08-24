"""Packaging of disabled zones into verified quarantine artifacts."""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ZoneQuarantinePlan:
    """Validated source paths and destination for quarantining one zone."""
    zone_name: str
    zone_file: Path
    archived_declaration: Path
    managed_index: Path
    quarantine_root: Path
    reason: str


@dataclass(slots=True)
class ZoneQuarantineStep:
    """One observable step of a zone quarantine transaction."""
    name: str
    ok: bool
    message: str


@dataclass(slots=True)
class ZoneQuarantineResult:
    """Final status, package path and rollback state for quarantine."""
    transaction_id: str
    zone: str
    status: str
    reason: str
    package_directory: str | None = None
    committed: bool = False
    rolled_back: bool = False
    steps: list[ZoneQuarantineStep] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Return whether every recorded transaction step succeeded."""
        return bool(self.steps) and all(step.ok for step in self.steps)


class ZoneQuarantineError(RuntimeError):
    """Strefa nie spełnia warunków bezpiecznej kwarantanny."""


class ZoneQuarantineTransaction:
    """Przenosi uprzednio wyłączoną strefę do pakietu odtworzeniowego."""

    @staticmethod
    def plan(
        zone_name: str,
        *,
        zone_file: Path,
        archived_declaration: Path,
        active_declaration: Path,
        managed_index: Path,
        quarantine_root: Path = Path("/var/lib/zonectl/quarantine"),
        reason: str,
    ) -> ZoneQuarantinePlan:
        """Validate disabled state and build a side-effect-free plan."""
        name = zone_name.strip().rstrip(".").casefold()
        if not name or not reason.strip():
            raise ZoneQuarantineError("Wymagana jest nazwa strefy i przyczyna")
        if not zone_file.is_file():
            raise ZoneQuarantineError(f"Brak pliku strefy: {zone_file}")
        if not archived_declaration.is_file():
            raise ZoneQuarantineError(
                f"Strefa nie jest wyłączona lub brak archiwum: "
                f"{archived_declaration}"
            )
        if active_declaration.exists():
            raise ZoneQuarantineError(
                f"Strefa nadal ma aktywną deklarację: {active_declaration}"
            )
        if not managed_index.is_file():
            raise ZoneQuarantineError(f"Brak indeksu: {managed_index}")
        include_line = f'include "{active_declaration}";'
        if any(
            line.strip() == include_line
            for line in managed_index.read_text(encoding="utf-8").splitlines()
        ):
            raise ZoneQuarantineError("Strefa nadal występuje w aktywnym indeksie")
        return ZoneQuarantinePlan(
            name,
            zone_file,
            archived_declaration,
            managed_index,
            quarantine_root,
            reason.strip(),
        )

    def apply(
        self,
        plan: ZoneQuarantinePlan,
        *,
        commit: bool = False,
        confirmation: str | None = None,
    ) -> ZoneQuarantineResult:
        """Create a verified package or return a side-effect-free dry-run."""
        txid = (
            datetime.now().strftime("%Y%m%d-%H%M%S")
            + f"-quarantine-{plan.zone_name}-{uuid.uuid4().hex[:8]}"
        )
        result = ZoneQuarantineResult(
            txid, plan.zone_name, "PLAN", plan.reason
        )
        if not commit:
            result.status = "DRY-RUN"
            result.steps.append(
                ZoneQuarantineStep("dry-run", True, "Nie przeniesiono danych")
            )
            return result
        if (confirmation or "").strip().rstrip(".").casefold() != plan.zone_name:
            result.status = "CONFIRMATION-REQUIRED"
            result.steps.append(
                ZoneQuarantineStep(
                    "confirmation",
                    False,
                    "Potwierdzenie nie odpowiada pełnej nazwie strefy",
                )
            )
            return result

        package = plan.quarantine_root / plan.zone_name / txid
        result.package_directory = str(package)
        zone_content = plan.zone_file.read_bytes()
        declaration_content = plan.archived_declaration.read_bytes()
        zone_stat = plan.zone_file.stat()
        declaration_stat = plan.archived_declaration.stat()
        zone_removed = False
        declaration_removed = False
        try:
            package.mkdir(parents=True, mode=0o750)
            package.chmod(0o750)
            zone_copy = package / "zone.db"
            declaration_copy = package / "zone.conf"
            self._atomic_write(zone_copy, zone_content, 0o640)
            self._atomic_write(declaration_copy, declaration_content, 0o640)

            manifest = {
                "transaction_id": txid,
                "zone": plan.zone_name,
                "status": "QUARANTINED",
                "reason": plan.reason,
                "operator": getpass.getuser(),
                "created_at": datetime.now(timezone.utc).astimezone().isoformat(
                    timespec="seconds"
                ),
                "original_paths": {
                    "zone_file": str(plan.zone_file),
                    "declaration": str(plan.archived_declaration),
                },
                "files": {
                    "zone.db": self._sha256(zone_copy),
                    "zone.conf": self._sha256(declaration_copy),
                },
                "metadata": {
                    "zone.db": {
                        "uid": zone_stat.st_uid,
                        "gid": zone_stat.st_gid,
                        "mode": zone_stat.st_mode & 0o777,
                    },
                    "zone.conf": {
                        "uid": declaration_stat.st_uid,
                        "gid": declaration_stat.st_gid,
                        "mode": declaration_stat.st_mode & 0o777,
                    },
                },
            }
            manifest_path = package / "manifest.json"
            self._atomic_write(
                manifest_path,
                json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
                0o640,
            )
            for filename, expected in manifest["files"].items():
                if self._sha256(package / filename) != expected:
                    raise RuntimeError(f"Błędna suma kontrolna: {filename}")
            result.steps.append(
                ZoneQuarantineStep("package", True, f"Pakiet: {package}")
            )

            plan.zone_file.unlink()
            zone_removed = True
            plan.archived_declaration.unlink()
            declaration_removed = True
            try:
                plan.archived_declaration.parent.rmdir()
            except OSError:
                pass
            result.steps.append(
                ZoneQuarantineStep(
                    "remove-working-copies",
                    True,
                    "Usunięto kopie robocze po weryfikacji pakietu",
                )
            )
            result.committed = True
            result.status = "QUARANTINED"
            return result
        except Exception as exc:
            result.steps.append(ZoneQuarantineStep("transaction", False, str(exc)))
            rollback_ok = True
            try:
                if zone_removed:
                    self._atomic_write(
                        plan.zone_file,
                        zone_content,
                        zone_stat.st_mode & 0o777,
                        zone_stat.st_uid,
                        zone_stat.st_gid,
                    )
                if declaration_removed:
                    self._atomic_write(
                        plan.archived_declaration,
                        declaration_content,
                        declaration_stat.st_mode & 0o777,
                        declaration_stat.st_uid,
                        declaration_stat.st_gid,
                    )
                for generated in (
                    package / "manifest.json",
                    package / "zone.conf",
                    package / "zone.db",
                ):
                    generated.unlink(missing_ok=True)
                package.rmdir()
            except Exception as rollback_error:
                rollback_ok = False
                result.steps.append(
                    ZoneQuarantineStep("rollback", False, str(rollback_error))
                )
            else:
                result.steps.append(
                    ZoneQuarantineStep("rollback", True, "Przywrócono dane robocze")
                )
            result.rolled_back = rollback_ok
            result.status = "ROLLED-BACK" if rollback_ok else "ROLLBACK-FAILED"
            return result

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _atomic_write(
        path: Path,
        content: bytes,
        mode: int,
        uid: int | None = None,
        gid: int | None = None,
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
            if uid is not None and gid is not None:
                os.chown(temporary, uid, gid)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
