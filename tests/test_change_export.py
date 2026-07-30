from __future__ import annotations

import stat
from datetime import datetime
from pathlib import Path

import pytest

from zonectl.core.models import Zone
from zonectl.core.transaction import TransactionResult
from zonectl.core.zone_edit_session import (
    ZoneEditSession,
    ZoneEditSessionError,
)
from zonectl.core.zone_parser import DNSRecord


class UnusedEngine:
    def apply(
        self,
        zone_name: str,
        source: Path,
        commit: bool = False,
    ) -> TransactionResult:
        raise AssertionError("Eksport nie może uruchamiać transakcji")


def replacement(
    original: DNSRecord,
    address: str,
) -> DNSRecord:
    return DNSRecord(
        owner=original.owner,
        ttl=original.ttl,
        rrclass=original.rrclass,
        rtype=original.rtype,
        rdata=address,
        raw=original.raw,
    )


def make_session(
    tmp_path: Path,
) -> tuple[ZoneEditSession, Path]:
    source = tmp_path / "example.pl"
    source.write_text(
        "$TTL 3600\n"
        "www 300 IN A 192.0.2.10\n",
        encoding="utf-8",
    )
    return (
        ZoneEditSession(
            Zone(name="example.pl", file=source),
            UnusedEngine(),
        ),
        source,
    )


def test_export_diff_writes_protected_file_without_commit(
    tmp_path: Path,
) -> None:
    session, source = make_session(tmp_path)
    original = source.read_bytes()
    view = session.model.record_views[0]
    session.model.replace_by_identifier(
        view.identifier,
        replacement(view.record, "192.0.2.40"),
    )

    destination = session.export_diff(
        directory=tmp_path / "exports",
        timestamp=datetime(2026, 7, 30, 17, 5, 6),
    )

    assert destination.parent == (tmp_path / "exports").resolve()
    assert destination.name.startswith(
        "20260730-170506-example.pl-"
    )
    assert destination.suffix == ".diff"
    assert destination.read_text(encoding="utf-8") == (
        session.unified_diff()
    )
    assert "-www 300 IN A 192.0.2.10" in destination.read_text(
        encoding="utf-8"
    )
    assert "+www\t300\tIN\tA\t192.0.2.40" in destination.read_text(
        encoding="utf-8"
    )
    assert stat.S_IMODE(destination.stat().st_mode) == 0o640
    assert source.read_bytes() == original
    assert session.model.dirty is True


def test_export_diff_rejects_session_without_changes(
    tmp_path: Path,
) -> None:
    session, _ = make_session(tmp_path)

    with pytest.raises(
        ZoneEditSessionError,
        match="Brak zmian do wyeksportowania",
    ):
        session.export_diff(directory=tmp_path / "exports")

    assert not (tmp_path / "exports").exists()
