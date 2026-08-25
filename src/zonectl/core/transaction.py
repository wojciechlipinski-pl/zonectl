from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import stat
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Any, Callable, TextIO, cast

from .audit import AuditLog
from .config import ToolkitConfig
from .models import Zone
from .paths import (
    AUDIT_LOG,
    LOCK_DIR,
    STATE_DIR,
    TRANSACTION_BACKUP_DIR,
    TRANSACTION_DIR,
)
from .runner import CommandResult, run


_flock = cast(Callable[[int, int], None], getattr(fcntl, "flock"))
_LOCK_EX = cast(int, getattr(fcntl, "LOCK_EX"))
_LOCK_NB = cast(int, getattr(fcntl, "LOCK_NB"))
_LOCK_UN = cast(int, getattr(fcntl, "LOCK_UN"))


@dataclass(slots=True)
class StepResult:
    name: str
    ok: bool
    message: str
    command: list[str] | None = None
    stdout: str = ""
    stderr: str = ""


@dataclass(slots=True)
class TransactionResult:
    transaction_id: str
    zone: str
    committed: bool
    status: str = "UNKNOWN"
    rolled_back: bool = False
    backup: str | None = None
    steps: list[StepResult] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return bool(self.steps) and all(step.ok for step in self.steps) and (self.committed or not self.rolled_back)


class ZoneLock:
    def __init__(self, path: Path):
        self.path = path
        self.handle: TextIO | None = None

    def __enter__(self) -> "ZoneLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+")
        try:
            _flock(self.handle.fileno(), _LOCK_EX | _LOCK_NB)
        except BlockingIOError as exc:
            self.handle.close()
            raise RuntimeError(f"Strefa jest już objęta inną transakcją: {self.path.stem}") from exc
        self.handle.seek(0)
        self.handle.truncate()
        self.handle.write(f"pid={os.getpid()} time={int(time.time())}\n")
        self.handle.flush()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self.handle:
            _flock(self.handle.fileno(), _LOCK_UN)
            self.handle.close()
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


class TransactionEngine:
    """Atomic zone-file replacement with validation, backup, reload and rollback."""

    def __init__(self, config: ToolkitConfig):
        self.config = config
        t = config.toolkit
        self.state_dir = Path(t.get("state_dir", str(STATE_DIR)))
        self.backup_dir = Path(
            t.get(
                "transaction_backup_dir",
                str(
                    self.state_dir / "backups"
                    if self.state_dir != STATE_DIR
                    else TRANSACTION_BACKUP_DIR
                ),
            )
        )
        self.transaction_dir = Path(
            t.get(
                "transaction_dir",
                str(
                    self.state_dir / "transactions"
                    if self.state_dir != STATE_DIR
                    else TRANSACTION_DIR
                ),
            )
        )
        self.lock_dir = Path(
            t.get(
                "lock_dir",
                str(
                    self.state_dir / "locks"
                    if self.state_dir != STATE_DIR
                    else LOCK_DIR
                ),
            )
        )
        self.audit = AuditLog(
            Path(t.get("audit_log", str(AUDIT_LOG)))
        )
        self.timeout = int(t.get("command_timeout", "20"))
        self.local_server = t.get("local_server", "127.0.0.1")
        self.read_only = str(
            t.get("read_only", "no")
        ).strip().casefold() in {"1", "yes", "true", "on"}

    def find_zone(self, name: str) -> Zone:
        wanted = name.rstrip(".").casefold()
        for zone in self.config.zones():
            if zone.name.rstrip(".").casefold() == wanted:
                return zone
        raise RuntimeError(f"Nie znaleziono strefy w zones.conf: {name}")

    @staticmethod
    def _safe_zone_name(name: str) -> str:
        return "".join(c if c.isalnum() or c in ".-_" else "_" for c in name)

    @staticmethod
    def _digest(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _step_command(self, name: str, command: list[str], timeout: int | None = None) -> StepResult:
        result = run(command, timeout or self.timeout)
        message = "OK" if result.returncode == 0 else f"kod {result.returncode}"
        return StepResult(name, result.returncode == 0, message, command, result.stdout, result.stderr)

    def _zone_validation(self, zone: Zone, candidate: Path) -> StepResult:
        return self._step_command("named-checkzone", ["named-checkzone", zone.name, str(candidate)])

    def _config_validation(self) -> StepResult:
        return self._step_command("named-checkconf", ["named-checkconf", "-z"])

    def _zone_serial(self, zone: Zone, candidate: Path) -> str | None:
        result = run(["named-checkzone", zone.name, str(candidate)], self.timeout)
        if result.returncode != 0:
            return None
        marker = "loaded serial "
        for line in result.stdout.splitlines():
            if marker in line:
                return line.split(marker, 1)[1].strip()
        return None

    def _serial(self, zone: str) -> str | None:
        result = run(["dig", f"@{self.local_server}", zone, "SOA", "+short", "+time=3", "+tries=1"], 6)
        if result.returncode != 0 or not result.stdout.strip():
            return None
        parts = result.stdout.splitlines()[0].split()
        return parts[2] if len(parts) >= 3 else None

    def _loaded_serial(self, zone: str) -> str | None:
        result = run(["rndc", "zonestatus", zone], self.timeout)
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            if line.startswith("serial:"):
                return line.split(":", 1)[1].strip()
        return None

    def _verify_loaded_zone(
        self,
        zone: Zone,
        expected_serial: str,
    ) -> tuple[StepResult, str | None, str | None]:
        loaded_serial = self._loaded_serial(zone.name)
        served_serial = self._serial(zone.name)
        serial_ok = loaded_serial is not None and loaded_serial == expected_serial

        step = StepResult(
            "verify-soa",
            serial_ok,
            (
                f"serial oczekiwany={expected_serial} "
                f"załadowany={loaded_serial or '-'} "
                f"serwowany={served_serial or '-'}"
            ),
        )
        return step, loaded_serial, served_serial

    def validate(self, zone_name: str, source: Path | None = None) -> TransactionResult:
        zone = self.find_zone(zone_name)
        candidate = source or zone.file
        txid = self._new_id(zone.name)
        result = TransactionResult(txid, zone.name, committed=False)
        if not candidate:
            result.steps.append(StepResult("candidate", False, "Brak ścieżki pliku strefy"))
            return result
        if not candidate.is_file():
            result.steps.append(StepResult("candidate", False, f"Plik nie istnieje: {candidate}"))
            return result
        result.steps.append(StepResult("candidate", True, f"{candidate} sha256={self._digest(candidate)}"))
        result.steps.append(self._zone_validation(zone, candidate))
        result.steps.append(self._config_validation())
        self._save_manifest(result, {"mode": "validate", "candidate": str(candidate)})
        self.audit.append(txid, zone.name, "validate", "PASS" if all(s.ok for s in result.steps) else "FAIL", candidate=str(candidate))
        return result

    def verify(self, zone_name: str) -> TransactionResult:
        zone = self.find_zone(zone_name)
        txid = self._new_id(zone.name)
        result = TransactionResult(txid, zone.name, committed=False)

        if not zone.file:
            result.steps.append(
                StepResult("zone-file", False, f"Strefa {zone.name} nie ma ustawionego parametru file")
            )
            return self._finish(result, "FAIL", mode="verify")

        candidate = zone.file.resolve()

        if not candidate.is_file():
            result.steps.append(
                StepResult("zone-file", False, f"Aktywny plik strefy nie istnieje: {candidate}")
            )
            return self._finish(
                result,
                "FAIL",
                mode="verify",
                candidate=str(candidate),
            )

        result.steps.append(
            StepResult(
                "zone-file",
                True,
                f"{candidate} sha256={self._digest(candidate)}",
            )
        )

        zone_check = self._zone_validation(zone, candidate)
        result.steps.append(zone_check)
        if not zone_check.ok:
            return self._finish(
                result,
                "FAIL",
                mode="verify",
                candidate=str(candidate),
            )

        conf_check = self._config_validation()
        result.steps.append(conf_check)
        if not conf_check.ok:
            return self._finish(
                result,
                "FAIL",
                mode="verify",
                candidate=str(candidate),
            )

        expected_serial = self._zone_serial(zone, candidate)
        if expected_serial is None:
            result.steps.append(
                StepResult(
                    "expected-serial",
                    False,
                    "Nie udało się odczytać seriala z aktywnego pliku strefy",
                )
            )
            return self._finish(
                result,
                "FAIL",
                mode="verify",
                candidate=str(candidate),
            )

        result.steps.append(
            StepResult(
                "expected-serial",
                True,
                f"serial oczekiwany={expected_serial}",
            )
        )

        verify_step, loaded_serial, served_serial = self._verify_loaded_zone(
            zone,
            expected_serial,
        )
        result.steps.append(verify_step)

        outcome = "VERIFY" if verify_step.ok else "FAIL"
        return self._finish(
            result,
            outcome,
            mode="verify",
            candidate=str(candidate),
            expected_serial=expected_serial,
            loaded_serial=loaded_serial,
            served_serial=served_serial,
        )

    def apply(
        self,
        zone_name: str,
        source: Path,
        commit: bool = False,
        metadata: dict[str, object] | None = None,
    ) -> TransactionResult:
        zone = self.find_zone(zone_name)
        if not zone.file:
            raise RuntimeError(f"Strefa {zone.name} nie ma ustawionego parametru file")
        source = source.resolve()
        target = zone.file.resolve()
        txid = self._new_id(zone.name)
        result = TransactionResult(
            txid,
            zone.name,
            committed=False,
            metadata=dict(metadata or {}),
        )
        if commit and self.read_only:
            result.steps.append(
                StepResult(
                    "read-only",
                    False,
                    "Tryb tylko do odczytu: COMMIT jest zablokowany",
                )
            )
            return self._finish(
                result,
                "READ-ONLY",
                source=str(source),
                target=str(target),
            )
        lock_path = self.lock_dir / f"{self._safe_zone_name(zone.name)}.lock"
        with ZoneLock(lock_path):
            self.audit.append(
                txid,
                zone.name,
                "transaction-start",
                "START",
                source=str(source),
                target=str(target),
                commit=commit,
                metadata=result.metadata,
            )
            if not source.is_file():
                result.steps.append(StepResult("source", False, f"Plik źródłowy nie istnieje: {source}"))
                return self._finish(result, "FAIL", source=str(source), target=str(target))
            if not target.is_file():
                result.steps.append(StepResult("target", False, f"Aktywny plik strefy nie istnieje: {target}"))
                return self._finish(result, "FAIL", source=str(source), target=str(target))
            if source == target:
                result.steps.append(StepResult("source", False, "Źródło i plik aktywny są tym samym plikiem"))
                return self._finish(result, "FAIL", source=str(source), target=str(target))

            result.steps.append(StepResult("source", True, f"{source} sha256={self._digest(source)}"))
            zone_check = self._zone_validation(zone, source)
            result.steps.append(zone_check)
            if not zone_check.ok:
                return self._finish(result, "FAIL", source=str(source), target=str(target))

            # named-checkconf checks the currently active configuration. The candidate
            # is independently checked above and is not exposed to named before commit.
            conf_check = self._config_validation()
            result.steps.append(conf_check)
            if not conf_check.ok:
                return self._finish(result, "FAIL", source=str(source), target=str(target))

            source_digest = self._digest(source)
            target_digest = self._digest(target)
            if source_digest == target_digest:
                result.steps.append(
                    StepResult(
                        "no-change",
                        True,
                        f"Plik źródłowy jest identyczny z aktywnym plikiem strefy; sha256={source_digest}",
                    )
                )
                return self._finish(
                    result,
                    "NO-CHANGE",
                    source=str(source),
                    target=str(target),
                    sha256=source_digest,
                )

            if not commit:
                result.steps.append(StepResult("dry-run", True, "Walidacja zakończona. Nie zmieniono pliku (brak --commit)."))
                return self._finish(result, "DRY-RUN", source=str(source), target=str(target))

            backup = self._backup(zone, target, txid)
            result.backup = str(backup)
            result.steps.append(StepResult("backup", True, str(backup)))
            expected_serial = self._zone_serial(zone, source)
            if expected_serial is None:
                result.steps.append(StepResult("expected-serial", False, "Nie udało się odczytać seriala z pliku źródłowego"))
                return self._finish(result, "FAILED", source=str(source), target=str(target))
            result.steps.append(StepResult("expected-serial", True, f"serial oczekiwany={expected_serial}"))
            old_serial = self._serial(zone.name)
            try:
                self._atomic_install(source, target)
                result.steps.append(StepResult("atomic-install", True, f"Zainstalowano {target}"))
                post_zone = self._zone_validation(zone, target)
                result.steps.append(post_zone)
                if not post_zone.ok:
                    raise RuntimeError("Walidacja aktywnego pliku po instalacji nie powiodła się")
                post_conf = self._config_validation()
                result.steps.append(post_conf)
                if not post_conf.ok:
                    raise RuntimeError("named-checkconf po instalacji nie powiódł się")
                reload_step = self._step_command("rndc-reload", ["rndc", "reload", zone.name])
                result.steps.append(reload_step)
                if not reload_step.ok:
                    raise RuntimeError("rndc reload nie powiódł się")
                verify_step, loaded_serial, new_serial = self._verify_loaded_zone(
                    zone,
                    expected_serial,
                )
                result.steps.append(verify_step)

                if loaded_serial is None:
                    raise RuntimeError("Nie udało się odczytać seriala z rndc zonestatus")

                if not verify_step.ok:
                    raise RuntimeError(
                        f"Załadowany serial ({loaded_serial}) różni się od oczekiwanego ({expected_serial})"
                    )
                result.committed = True
                return self._finish(result, "COMMIT", source=str(source), target=str(target), old_serial=old_serial, new_serial=new_serial)
            except Exception as exc:
                result.steps.append(StepResult("transaction", False, str(exc)))
                rollback = self._rollback(zone, target, backup)
                result.steps.append(rollback)
                result.rolled_back = rollback.ok
                return self._finish(result, "ROLLED-BACK" if rollback.ok else "ROLLBACK-FAILED", source=str(source), target=str(target))

    def rollback(self, zone_name: str, backup: Path, commit: bool = False) -> TransactionResult:
        zone = self.find_zone(zone_name)
        if not zone.file:
            raise RuntimeError(f"Strefa {zone.name} nie ma ustawionego parametru file")
        txid = self._new_id(zone.name)
        result = TransactionResult(txid, zone.name, committed=False)
        if commit and self.read_only:
            result.steps.append(
                StepResult(
                    "read-only",
                    False,
                    "Tryb tylko do odczytu: rollback z COMMIT jest zablokowany",
                )
            )
            return self._finish(
                result,
                "READ-ONLY",
                backup=str(backup),
            )
        if not backup.is_file():
            result.steps.append(StepResult("backup", False, f"Nie znaleziono backupu: {backup}"))
            return result
        check = self._zone_validation(zone, backup)
        result.steps.append(check)
        if not check.ok or not commit:
            if not commit:
                result.steps.append(StepResult("dry-run", True, "Backup poprawny. Użyj --commit, aby przywrócić."))
            return self._finish(result, "DRY-RUN" if not commit else "FAIL", backup=str(backup))
        current_backup = self._backup(zone, zone.file, txid + "-pre-rollback")
        result.backup = str(current_backup)
        result.steps.append(StepResult("backup-current", True, str(current_backup)))
        self._atomic_install(backup, zone.file)
        result.steps.append(StepResult("atomic-restore", True, str(zone.file)))
        reload_step = self._step_command("rndc-reload", ["rndc", "reload", zone.name])
        result.steps.append(reload_step)
        result.committed = reload_step.ok
        return self._finish(result, "ROLLBACK-COMMIT" if reload_step.ok else "FAIL", backup=str(backup))

    def backups(self, zone_name: str, limit: int = 20) -> list[Path]:
        safe = self._safe_zone_name(self.find_zone(zone_name).name)
        path = self.backup_dir / safe
        if not path.exists():
            return []
        return sorted((p for p in path.iterdir() if p.is_file() and not p.name.endswith(".json")), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]

    def history(
        self,
        zone_name: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        """Odczytaj ostatnie manifesty transakcji."""
        if not self.transaction_dir.exists():
            return []

        wanted = (
            zone_name.rstrip(".").casefold()
            if zone_name
            else None
        )
        records: list[dict[str, object]] = []
        paths = sorted(
            self.transaction_dir.glob("*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

        for path in paths:
            try:
                payload = json.loads(
                    path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                continue

            if not isinstance(payload, dict):
                continue
            record = cast(dict[str, object], payload)
            zone = str(record.get("zone", ""))

            if (
                wanted is not None
                and zone.rstrip(".").casefold() != wanted
            ):
                continue

            record.setdefault(
                "saved_at",
                datetime.fromtimestamp(
                    path.stat().st_mtime,
                    tz=timezone.utc,
                ).astimezone().isoformat(timespec="seconds"),
            )
            records.append(record)

            if len(records) >= max(1, limit):
                break

        return records

    def load_transaction(
        self,
        transaction_id: str,
    ) -> TransactionResult:
        """Odtwórz wynik transakcji z manifestu."""
        if (
            not transaction_id
            or Path(transaction_id).name != transaction_id
            or transaction_id in {".", ".."}
            or transaction_id
            != self._safe_zone_name(transaction_id)
        ):
            raise RuntimeError(
                "Nieprawidłowy identyfikator transakcji"
            )

        path = self.transaction_dir / f"{transaction_id}.json"

        if not path.is_file():
            raise RuntimeError(
                f"Nie znaleziono transakcji: {transaction_id}"
            )

        try:
            payload_raw = json.loads(
                path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Nie można odczytać manifestu transakcji: {path}"
            ) from exc

        if not isinstance(payload_raw, dict):
            raise RuntimeError(f"Nieprawidłowy manifest transakcji: {path}")
        payload = cast(dict[str, Any], payload_raw)
        try:
            steps = [
                StepResult(
                    name=str(step["name"]),
                    ok=bool(step["ok"]),
                    message=str(step["message"]),
                    command=step.get("command"),
                    stdout=str(step.get("stdout", "")),
                    stderr=str(step.get("stderr", "")),
                )
                for step in payload.get("steps", [])
            ]
            return TransactionResult(
                transaction_id=str(payload["transaction_id"]),
                zone=str(payload["zone"]),
                committed=bool(payload.get("committed", False)),
                status=str(
                    payload.get(
                        "status",
                        payload.get("outcome", "UNKNOWN"),
                    )
                ),
                rolled_back=bool(
                    payload.get("rolled_back", False)
                ),
                backup=payload.get("backup"),
                steps=steps,
                metadata=dict(payload.get("metadata", {})),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(
                f"Nieprawidłowy manifest transakcji: {path}"
            ) from exc

    def _new_id(self, zone: str) -> str:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{stamp}-{self._safe_zone_name(zone)}-{uuid.uuid4().hex[:8]}"

    def _backup(self, zone: Zone, target: Path, txid: str) -> Path:
        directory = self.backup_dir / self._safe_zone_name(zone.name)
        directory.mkdir(parents=True, exist_ok=True)
        backup = directory / f"{txid}-{target.name}"
        shutil.copy2(target, backup)
        metadata = {
            "transaction_id": txid,
            "zone": zone.name,
            "source": str(target),
            "backup": str(backup),
            "sha256": self._digest(backup),
            "stat": {
                "mode": stat.S_IMODE(target.stat().st_mode),
                "uid": target.stat().st_uid,
                "gid": target.stat().st_gid,
            },
        }
        backup.with_suffix(backup.suffix + ".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return backup

    @staticmethod
    def _atomic_install(source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target_stat = target.stat()
        fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.elkman-", dir=target.parent)
        temp = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as out, source.open("rb") as inp:
                shutil.copyfileobj(inp, out)
                out.flush()
                os.fsync(out.fileno())
            os.chmod(temp, stat.S_IMODE(target_stat.st_mode))
            try:
                chown = getattr(os, "chown", None)
                if chown is not None:
                    chown(temp, target_stat.st_uid, target_stat.st_gid)
            except PermissionError:
                pass
            os.replace(temp, target)
            directory_flag = int(getattr(os, "O_DIRECTORY", 0))
            dir_fd = os.open(target.parent, directory_flag)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        finally:
            try:
                temp.unlink()
            except FileNotFoundError:
                pass

    def _rollback(self, zone: Zone, target: Path, backup: Path) -> StepResult:
        try:
            self._atomic_install(backup, target)
            reload_result = run(["rndc", "reload", zone.name], self.timeout)
            if reload_result.returncode != 0:
                return StepResult("rollback", False, "Plik przywrócono, ale rndc reload nie powiódł się", ["rndc", "reload", zone.name], reload_result.stdout, reload_result.stderr)
            return StepResult("rollback", True, f"Przywrócono {backup}")
        except Exception as exc:
            return StepResult("rollback", False, str(exc))

    def _save_manifest(
        self,
        result: TransactionResult,
        extra: dict[str, object],
    ) -> None:
        self.transaction_dir.mkdir(parents=True, exist_ok=True)
        payload = asdict(result)
        payload.update(extra)
        payload["saved_at"] = (
            datetime.now(timezone.utc)
            .astimezone()
            .isoformat(timespec="seconds")
        )
        path = self.transaction_dir / f"{result.transaction_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _finish(
        self,
        result: TransactionResult,
        outcome: str,
        **extra: object,
    ) -> TransactionResult:
        result.status = outcome
        self._save_manifest(result, {"outcome": outcome, **extra})
        audit_details: dict[str, object] = {
            "backup": result.backup,
            "rolled_back": result.rolled_back,
        }
        audit_details.update(extra)
        self.audit.append(
            result.transaction_id,
            result.zone,
            "transaction-finish",
            outcome,
            **audit_details,
        )
        return result
