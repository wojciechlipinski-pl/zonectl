from __future__ import annotations

from dataclasses import replace

from zonectl.core.models import Zone
from zonectl.core.zone_document import RecordNode, ZoneDocument
from zonectl.core.zone_parser import DNSRecord
from zonectl.core.zone_writer import ZoneWriter
from zonectl.ui.records.editor import RecordEditor


def record(
    *,
    owner: str = "www",
    rtype: str = "A",
    rdata: str = "192.0.2.10",
) -> DNSRecord:
    return DNSRecord(
        owner=owner,
        ttl=None,
        rrclass="IN",
        rtype=rtype,
        rdata=rdata,
        raw=f"{owner} IN {rtype} {rdata}",
    )


def test_unchanged_relative_owner_keeps_source_form() -> None:
    original = record(owner="www")
    zone = Zone(name="example.pl", file=None)

    assert RecordEditor._owner_from_form(
        "www",
        original,
        zone,
    ) == "www"


def test_changed_relative_owner_is_made_absolute() -> None:
    original = record(owner="www")
    zone = Zone(name="example.pl", file=None)

    assert RecordEditor._owner_from_form(
        "mail",
        original,
        zone,
    ) == "mail.example.pl."


def test_modified_record_keeps_inline_comment() -> None:
    original = record()
    node = RecordNode(
        record=replace(original, rdata="192.0.2.40"),
        raw="www     IN A    192.0.2.10       ; adres WWW",
        modified=True,
    )
    document = ZoneDocument(nodes=[node])

    assert ZoneWriter().render_document(document) == (
        "www\tIN\tA\t192.0.2.40       ; adres WWW\n"
    )


def test_semicolon_inside_quotes_is_not_inline_comment() -> None:
    original = record(
        owner="_note",
        rtype="TXT",
        rdata='"a;b"',
    )
    node = RecordNode(
        record=replace(original, rdata='"c;d"'),
        raw='_note IN TXT "a;b"',
        modified=True,
    )
    document = ZoneDocument(nodes=[node])

    assert ZoneWriter().render_document(document) == (
        '_note\tIN\tTXT\t"c;d"\n'
    )
