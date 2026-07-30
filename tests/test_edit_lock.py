from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from zonectl.core.edit_lock import (
    ZoneEditLock,
    ZoneEditLockedError,
)
from zonectl.core.models import Zone
from zonectl.core.zone_edit_session import ZoneEditSession


class FakeEngine:
    pass


def zone_file(tmp_path: Path) -> Path:
    path = tmp_path / "example.pl"
    path.write_text(
        "$TTL 3600\n"
        "@ IN SOA ns.example.pl. hostmaster.example.pl. "
        "1 3600 600 86400 300\n"
        "@ IN NS ns.example.pl.\n"
        "ns IN A 192.0.2.53\n",
        encoding="utf-8",
    )
    return path


def test_second_edit_lock_reports_owner(tmp_path: Path) -> None:
    lock_directory = tmp_path / "edit-locks"
    first = ZoneEditLock(lock_directory, "example.pl").acquire()
    second = ZoneEditLock(lock_directory, "example.pl")

    try:
        metadata = json.loads(first.path.read_text(encoding="utf-8"))
        assert stat.S_IMODE(first.path.parent.stat().st_mode) == 0o750

        with pytest.raises(
            ZoneEditLockedError,
            match="jest już edytowana",
        ) as raised:
            second.acquire()

        assert raised.value.owner["pid"] == metadata["pid"]
        assert raised.value.owner["user"] == metadata["user"]
        assert raised.value.owner["host"] == metadata["host"]
        assert raised.value.owner["started_at"] == metadata["started_at"]
    finally:
        first.release()


def test_lock_can_be_acquired_after_previous_session_closes(
    tmp_path: Path,
) -> None:
    first = ZoneEditLock(tmp_path, "example.pl").acquire()
    first.release()

    second = ZoneEditLock(tmp_path, "example.pl").acquire()
    try:
        assert second.acquired is True
        assert second.path.is_file()
    finally:
        second.release()

    assert second.path.exists() is False


def test_stale_lock_file_is_reused_safely(tmp_path: Path) -> None:
    stale = tmp_path / "example.pl.lock"
    stale.write_text(
        '{"pid": 999999, "user": "stary"}\n',
        encoding="utf-8",
    )

    lock = ZoneEditLock(tmp_path, "example.pl").acquire()
    try:
        metadata = json.loads(stale.read_text(encoding="utf-8"))
        assert metadata["pid"] != 999999
        assert metadata["user"] != "stary"
    finally:
        lock.release()


def test_edit_session_holds_lock_until_close(tmp_path: Path) -> None:
    zone = Zone(name="example.pl", file=zone_file(tmp_path))
    lock_directory = tmp_path / "edit-locks"
    first = ZoneEditSession(
        zone,
        FakeEngine(),
        edit_lock_directory=lock_directory,
    )

    try:
        with pytest.raises(ZoneEditLockedError):
            ZoneEditSession(
                zone,
                FakeEngine(),
                edit_lock_directory=lock_directory,
            )
    finally:
        first.close()

    second = ZoneEditSession(
        zone,
        FakeEngine(),
        edit_lock_directory=lock_directory,
    )
    second.close()


def test_read_only_sessions_do_not_create_edit_locks(
    tmp_path: Path,
) -> None:
    zone = Zone(name="example.pl", file=zone_file(tmp_path))
    lock_directory = tmp_path / "edit-locks"

    first = ZoneEditSession(
        zone,
        FakeEngine(),
        read_only=True,
        edit_lock_directory=lock_directory,
    )
    second = ZoneEditSession(
        zone,
        FakeEngine(),
        read_only=True,
        edit_lock_directory=lock_directory,
    )

    try:
        assert first.edit_lock is None
        assert second.edit_lock is None
        assert lock_directory.exists() is False
    finally:
        first.close()
        second.close()
