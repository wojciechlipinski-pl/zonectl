from pathlib import Path

from zonectl.core.models import Zone
from zonectl.core.zone_model import ChangeKind, ZoneModel
from zonectl.core.zone_parser import DNSRecord
from zonectl.ui.records.editor import RecordEditor


def test_add_record_creates_pending_add_change() -> None:
    model = ZoneModel("example.pl", [])

    record = DNSRecord(
        owner="www.example.pl.",
        ttl=300,
        rrclass="IN",
        rtype="A",
        rdata="192.0.2.10",
        raw="",
    )

    index = model.add(record)

    assert index == 0
    assert model.records == (record,)
    assert model.change_count == 1
    assert model.dirty is True

    change = model.pending_changes[0]

    assert change.kind is ChangeKind.ADD
    assert change.before is None
    assert change.after == record


def soa_record() -> DNSRecord:
    return DNSRecord(
        owner="example.pl.", ttl=3600, rrclass="IN", rtype="SOA",
        rdata=(
            "ns1.example.pl. hostmaster.example.pl. "
            "2026082101 3600 900 1209600 300"
        ),
        raw="",
    )


def test_build_soa_record_preserves_serial() -> None:
    updated, error = RecordEditor.build_soa_record(
        soa_record(),
        primary="ns2.example.pl.", administrator="dns.example.pl.",
        refresh="7200", retry="1200", expire="604800", minimum="600",
        ttl_text="",
    )

    assert error == ""
    assert updated is not None
    assert updated.ttl is None
    assert updated.rdata == (
        "ns2.example.pl. dns.example.pl. "
        "2026082101 7200 1200 604800 600"
    )


def test_build_soa_record_rejects_invalid_timer() -> None:
    updated, error = RecordEditor.build_soa_record(
        soa_record(),
        primary="ns1.example.pl.", administrator="hostmaster.example.pl.",
        refresh="not-a-number", retry="900", expire="1209600",
        minimum="300", ttl_text="3600",
    )

    assert updated is None
    assert "Refresh SOA" in error


def test_edit_record_routes_soa_to_dedicated_editor(monkeypatch) -> None:
    expected = soa_record()
    editor = RecordEditor()
    monkeypatch.setattr(
        editor, "edit_soa_dialog", lambda win, record, zone: expected,
    )

    result = editor.edit_record_dialog(
        object(), soa_record(),
        Zone(name="example.pl", file=Path("/tmp/example.pl")),
    )

    assert result is expected
