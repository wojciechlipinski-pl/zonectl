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
from datetime import datetime
from pathlib import Path

from .audit import AuditLog
from .config import ToolkitConfig
from .models import Zone
from .runner import CommandResult, run


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
    rolled_back: bool = False
    backup: str | None = None
    steps: list[StepResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.steps) and all(step.ok for step in self.steps) and (self.committed or not self.rolled_back)


class ZoneLock:
    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+")
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.handle.close()
            raise RuntimeError(f"Strefa jest już objęta inną transakcją: {self.path.stem}") from exc
        self.handle.seek(0)
        self.handle.truncate()
        self.handle.write(f"pid={os.getpid()} time={int(time.time())}\n")
        self.handle.flush()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.handle:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
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
        self.state_dir = Path(t.get("state_dir", "/var/lib/elkman-dns-toolkit"))
        self.backup_dir = Path(t.get("transaction_backup_dir", str(self.state_dir / "backups")))
        self.transaction_dir = Path(t.get("transaction_dir", str(self.state_dir / "transactions")))
        self.lock_dir = Path(t.get("lock_dir", str(self.state_dir / "locks")))
        self.audit = AuditLog(Path(t.get("audit_log", "/var/log/elkman-dns-toolkit/audit.jsonl")))
        self.timeout = int(t.get("command_timeout", "20"))
        self.local_server = t.get("local_server", "127.0.0.1")

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

    def _serial(self, zone: str) -> str | None:
        result = run(["dig", f"@{self.local_server}", zone, "SOA", "+short", "+time=3", "+tries=1"], 6)
        if result.returncode != 0 or not result.stdout.strip():
            return None
        parts = result.stdout.splitlines()[0].split()
        return parts[2] if len(parts) >= 3 else None

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

    def apply(self, zone_name: str, source: Path, commit: bool = False) -> TransactionResult:
        zone = self.find_zone(zone_name)
        if not zone.file:
            raise RuntimeError(f"Strefa {zone.name} nie ma ustawionego parametru file")
        source = source.resolve()
        target = zone.file.resolve()
        txid = self._new_id(zone.name)
        result = TransactionResult(txid, zone.name, committed=False)
        lock_path = self.lock_dir / f"{self._safe_zone_name(zone.name)}.lock"
        with ZoneLock(lock_path):
            self.audit.append(txid, zone.name, "transaction-start", "START", source=str(source), target=str(target), commit=commit)
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

            if not commit:
                result.steps.append(StepResult("dry-run", True, "Walidacja zakończona. Nie zmieniono pliku (brak --commit)."))
                return self._finish(result, "DRY-RUN", source=str(source), target=str(target))

            backup = self._backup(zone, target, txid)
            result.backup = str(backup)
            result.steps.append(StepResult("backup", True, str(backup)))
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
                new_serial = self._serial(zone.name)
                serial_ok = new_serial is not None
                result.steps.append(StepResult("verify-soa", serial_ok, f"serial przed={old_serial or '-'} po={new_serial or '-'}"))
                if not serial_ok:
                    raise RuntimeError("Brak odpowiedzi SOA po reload")
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
                os.chown(temp, target_stat.st_uid, target_stat.st_gid)
            except PermissionError:
                pass
            os.replace(temp, target)
            dir_fd = os.open(target.parent, os.O_DIRECTORY)
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

    def _save_manifest(self, result: TransactionResult, extra: dict) -> None:
        self.transaction_dir.mkdir(parents=True, exist_ok=True)
        payload = asdict(result)
        payload.update(extra)
        path = self.transaction_dir / f"{result.transaction_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _finish(self, result: TransactionResult, outcome: str, **extra) -> TransactionResult:
        self._save_manifest(result, {"outcome": outcome, **extra})
        self.audit.append(result.transaction_id, result.zone, "transaction-finish", outcome, backup=result.backup, rolled_back=result.rolled_back, **extra)
        return result
