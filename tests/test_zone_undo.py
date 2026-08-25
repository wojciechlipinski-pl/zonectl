from __future__ import annotations

from datetime import date
from pathlib import Path

from zonectl.core.models import Zone
from zonectl.core.transaction import TransactionResult
from zonectl.core.zone_edit_session import ZoneEditSession
from zonectl.core.zone_model import ChangeKind, ZoneModel
from zonectl.core.zone_parser import DNSRecord


class UnusedEngine:
    def apply(
        self,
        zone_name: str,
        source: Path,
        commit: bool = False,
        metadata: dict[str, object] | None = None,
    ) -> TransactionResult:
        raise AssertionError("Cofanie nie może uruchamiać transakcji")


def record(
    owner: str,
    address: str,
) -> DNSRecord:
    return DNSRecord(
        owner=owner,
        ttl=300,
        rrclass="IN",
        rtype="A",
        rdata=address,
        raw=f"{owner} 300 IN A {address}",
    )


def test_model_undoes_add_modify_and_delete_in_reverse_order() -> None:
    original = record("www", "192.0.2.10")
    model = ZoneModel("example.pl", [original])
    original_id = model.record_views[0].identifier

    model.add(record("mail", "192.0.2.20"))
    model.replace_by_identifier(
        original_id,
        record("www", "192.0.2.30"),
    )
    model.delete_by_identifier(original_id)

    assert model.pending_changes[0].kind is ChangeKind.DELETE
    assert model.can_undo is True

    assert model.undo() is True
    assert model.record_views[0].record.rdata == "192.0.2.30"
    assert model.pending_changes[0].kind is ChangeKind.MODIFY

    assert model.undo() is True
    assert model.record_views[0].record == original
    assert model.pending_changes[0].kind is ChangeKind.ADD

    assert model.undo() is True
    assert model.pending_changes == ()
    assert model.records == (original,)
    assert model.can_undo is False
    assert model.undo() is False


def test_replacing_record_with_itself_does_not_create_undo() -> None:
    original = record("www", "192.0.2.10")
    model = ZoneModel("example.pl", [original])
    identifier = model.record_views[0].identifier

    model.replace_by_identifier(identifier, original)

    assert model.dirty is False
    assert model.can_undo is False


def test_session_undo_last_change_restores_prepared_soa(
    tmp_path: Path,
) -> None:
    source = tmp_path / "example.pl"
    original = (
        "$TTL 3600\n"
        "@ IN SOA ns1.example.pl. hostmaster.example.pl. (\n"
        "    2026073001 ; serial\n"
        "    3600\n"
        "    900\n"
        "    1209600\n"
        "    3600 )\n"
        "www 300 IN A 192.0.2.10\n"
    )
    source.write_text(original, encoding="utf-8")
    session = ZoneEditSession(
        Zone(name="example.pl", file=source),
        UnusedEngine(),
        today_provider=lambda: date(2026, 7, 30),
    )
    view = next(
        item for item in session.model.record_views
        if item.record.rtype == "A"
    )
    session.model.replace_by_identifier(
        view.identifier,
        record("www", "192.0.2.40"),
    )

    assert "2026073002" in session.unified_diff()
    assert session.undo() is True

    assert session.model.dirty is False
    assert session.model.can_undo is False
    assert session.unified_diff() == ""
    assert session.render_candidate() == original
    assert source.read_text(encoding="utf-8") == original


def test_discard_clears_undo_history() -> None:
    original = record("www", "192.0.2.10")
    model = ZoneModel("example.pl", [original])
    model.add(record("mail", "192.0.2.20"))

    model.discard()

    assert model.can_undo is False
    assert model.undo() is False
