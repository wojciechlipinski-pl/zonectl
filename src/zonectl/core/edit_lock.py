from __future__ import annotations

import fcntl
import getpass
import json
import os
import re
import socket
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Callable, TextIO, cast


_flock = cast(Callable[[int, int], None], getattr(fcntl, "flock"))
_LOCK_EX = cast(int, getattr(fcntl, "LOCK_EX"))
_LOCK_NB = cast(int, getattr(fcntl, "LOCK_NB"))
_LOCK_UN = cast(int, getattr(fcntl, "LOCK_UN"))


class ZoneEditLockedError(RuntimeError):
    """Strefa jest już otwarta w innej sesji edycyjnej."""

    def __init__(self, zone_name: str, owner: dict[str, object]):
        self.zone_name = zone_name
        self.owner = owner

        user = owner.get("user", "nieznany użytkownik")
        host = owner.get("host", "nieznany host")
        pid = owner.get("pid", "?")
        started_at = owner.get("started_at", "nieznany czas")

        super().__init__(
            f"Strefa {zone_name} jest już edytowana przez "
            f"{user}@{host} (PID {pid}, od {started_at})"
        )


class ZoneEditLock:
    """Międzyprocesowa blokada wyłącznej sesji edycji strefy."""

    def __init__(self, directory: Path, zone_name: str):
        self.directory = Path(directory)
        self.zone_name = zone_name.rstrip(".")
        safe_name = re.sub(
            r"[^A-Za-z0-9_.-]+",
            "_",
            self.zone_name,
        ).strip("._") or "zone"
        self.path = self.directory / f"{safe_name}.lock"
        self.handle: TextIO | None = None
        self.token = uuid.uuid4().hex

    @property
    def acquired(self) -> bool:
        return self.handle is not None

    def _metadata(self) -> dict[str, object]:
        return {
            "zone": self.zone_name,
            "pid": os.getpid(),
            "user": getpass.getuser(),
            "host": socket.gethostname(),
            "started_at": (
                datetime.now(timezone.utc)
                .astimezone()
                .isoformat(timespec="seconds")
            ),
            "token": self.token,
        }

    @staticmethod
    def _read_owner(handle: TextIO) -> dict[str, object]:
        try:
            handle.seek(0)
            payload = json.load(handle)
        except (OSError, ValueError, TypeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def acquire(self) -> "ZoneEditLock":
        if self.handle is not None:
            return self

        self.directory.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o750,
        )
        handle = self.path.open("a+", encoding="utf-8")

        try:
            _flock(
                handle.fileno(),
                _LOCK_EX | _LOCK_NB,
            )
        except BlockingIOError as exc:
            owner = self._read_owner(handle)
            handle.close()
            raise ZoneEditLockedError(
                self.zone_name,
                owner,
            ) from exc

        try:
            handle.seek(0)
            handle.truncate()
            json.dump(
                self._metadata(),
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            os.chmod(self.path, 0o640)
        except Exception:
            _flock(handle.fileno(), _LOCK_UN)
            handle.close()
            raise

        self.handle = handle
        return self

    def release(self) -> None:
        handle = self.handle
        if handle is None:
            return

        self.handle = None
        try:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
        finally:
            _flock(handle.fileno(), _LOCK_UN)
            handle.close()

    def __enter__(self) -> "ZoneEditLock":
        return self.acquire()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()
