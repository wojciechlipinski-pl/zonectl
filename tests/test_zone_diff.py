from __future__ import annotations

from pathlib import Path

from zonectl.core.models import Zone
from zonectl.core.transaction import TransactionResult
from zonectl.core.zone_edit_session import ZoneEditSession
from zonectl.core.zone_parser import DNSRecord


class UnusedEngine:
    def apply(
        self,
        zone_name: str,
        source: Path,
        commit: bool = False,
        metadata: dict[str, object] | None = None,
    ) -> TransactionResult:
        raise AssertionError("Podgląd diff nie może uruchamiać transakcji")


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
    session = ZoneEditSession(
        Zone(name="example.pl", file=source),
        UnusedEngine(),
    )
    return session, source


def test_unified_diff_is_empty_without_changes(
    tmp_path: Path,
) -> None:
    session, source = make_session(tmp_path)
    original = source.read_bytes()

    assert session.unified_diff() == ""
    assert source.read_bytes() == original


def test_unified_diff_shows_record_change_without_writing(
    tmp_path: Path,
) -> None:
    session, source = make_session(tmp_path)
    original = source.read_bytes()
    view = session.model.record_views[0]

    session.model.replace_by_identifier(
        view.identifier,
        replacement(view.record, "192.0.2.40"),
    )

    diff = session.unified_diff()

    assert f"--- {source.resolve()}" in diff
    assert f"+++ {source.resolve()} (kandydat)" in diff
    assert "-www 300 IN A 192.0.2.10" in diff
    assert "+www\t300\tIN\tA\t192.0.2.40" in diff
    assert source.read_bytes() == original
    assert session.model.dirty is True


def test_unified_diff_context_cannot_be_negative(
    tmp_path: Path,
) -> None:
    session, _ = make_session(tmp_path)
    view = session.model.record_views[0]
    session.model.replace_by_identifier(
        view.identifier,
        replacement(view.record, "192.0.2.50"),
    )

    diff = session.unified_diff(context=-10)

    assert "@@ -2 +2 @@" in diff
