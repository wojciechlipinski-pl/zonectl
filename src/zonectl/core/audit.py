from __future__ import annotations

import json
import os
import pwd
import socket
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AuditEvent:
    timestamp: str
    transaction_id: str
    zone: str
    action: str
    outcome: str
    user: str
    uid: int
    host: str
    details: dict[str, Any]


class AuditLog:
    def __init__(self, path: Path):
        self.path = path

    @staticmethod
    def identity() -> tuple[str, int]:
        getuid = getattr(os, "getuid", None)
        uid = int(getuid()) if getuid is not None else 0
        try:
            getpwuid = getattr(pwd, "getpwuid", None)
            if getpwuid is None:
                raise KeyError(uid)
            user = str(getpwuid(uid).pw_name)
        except (KeyError, AttributeError):
            user = str(uid)
        sudo_user = os.environ.get("SUDO_USER")
        return (sudo_user or user, uid)

    def append(
        self, transaction_id: str, zone: str, action: str, outcome: str, **details: Any
    ) -> None:
        user, uid = self.identity()
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc)
            .astimezone()
            .isoformat(timespec="seconds"),
            transaction_id=transaction_id,
            zone=zone,
            action=action,
            outcome=outcome,
            user=user,
            uid=uid,
            host=socket.gethostname(),
            details=details,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o640)
        try:
            with os.fdopen(fd, "a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(asdict(event), ensure_ascii=False, sort_keys=True) + "\n"
                )
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            pass

    def read(self, zone: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
        events: list[dict[str, Any]] = []
        for line in reversed(lines):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if zone and event.get("zone") != zone:
                continue
            events.append(event)
            if len(events) >= limit:
                break
        return events
