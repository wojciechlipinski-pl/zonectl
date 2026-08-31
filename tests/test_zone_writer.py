from pathlib import Path

import pytest

from zonectl.core.zone_document import (
    RecordNode,
    ZoneDocument,
)
from zonectl.core.zone_file_parser import ZoneFileParser
from zonectl.core.zone_parser import DNSRecord
from zonectl.core.zone_writer import (
    ZoneWriteError,
    ZoneWriter,
)


def test_unmodified_document_is_preserved() -> None:
    original = (
        "; komentarz administratora\n"
        "\n"
        "$TTL 3600\n"
        "$ORIGIN example.pl.\n"
        "\n"
        "www     300 IN A     192.0.2.10 ; serwer WWW\n"
        "mail        IN MX    10 mail.example.pl.\n"
    )

    document = ZoneFileParser.parse_text(original)

    assert ZoneWriter().render_document(document) == original


def test_document_without_final_newline_is_preserved() -> None:
    original = "$TTL 3600\nwww IN A 192.0.2.10"

    document = ZoneFileParser.parse_text(original)

    assert document.trailing_newline is False
    assert ZoneWriter().render_document(document) == original


def test_modified_record_is_rendered_again() -> None:
    original = (
        "$TTL 3600\n"
        "\n"
        "www     300 IN A     192.0.2.10 ; stary adres\n"
        "\n"
        "; komentarz końcowy\n"
    )

    document = ZoneFileParser.parse_text(original)

    node = next(document.iter_record_nodes())

    node.record = DNSRecord(
        owner=node.record.owner,
        ttl=node.record.ttl,
        rrclass=node.record.rrclass,
        rtype=node.record.rtype,
        rdata="192.0.2.20",
        raw=node.record.raw,
    )
    node.modified = True

    result = ZoneWriter().render_document(document)

    assert result == (
        "$TTL 3600\n"
        "\n"
        "www\t300\tIN\tA\t192.0.2.20 ; stary adres\n"
        "\n"
        "; komentarz końcowy\n"
    )


def test_unmodified_record_keeps_inline_comment() -> None:
    original = "www 300 IN A 192.0.2.10 ; ważny komentarz\n"

    document = ZoneFileParser.parse_text(original)

    result = ZoneWriter().render_document(document)

    assert result == original


def test_deleted_record_is_omitted() -> None:
    original = (
        "$TTL 3600\nwww IN A 192.0.2.10\nold IN A 192.0.2.20\nmail IN A 192.0.2.30\n"
    )

    document = ZoneFileParser.parse_text(original)
    nodes = list(document.iter_record_nodes())

    nodes[1].deleted = True

    result = ZoneWriter().render_document(document)

    assert result == ("$TTL 3600\nwww IN A 192.0.2.10\nmail IN A 192.0.2.30\n")


def test_multiline_soa_record_is_preserved_when_unmodified() -> None:
    original = (
        "@ IN SOA ns1.example.pl. hostmaster.example.pl. (\n"
        "    2026072901\n"
        "    3600\n"
        "    900\n"
        "    1209600\n"
        "    3600 )\n"
    )

    document = ZoneFileParser.parse_text(original)

    assert len(document.nodes) == 1
    assert isinstance(document.nodes[0], RecordNode)

    assert ZoneWriter().render_document(document) == original


def test_modified_multiline_soa_preserves_layout_and_comments() -> None:
    original = (
        "@ 3600 IN SOA ns1.example.pl. hostmaster.example.pl. (\n"
        "    2026072901 ; serial\n"
        "    3600       ; refresh\n"
        "    900        ; retry\n"
        "    1209600    ; expire\n"
        "    3600 )     ; minimum\n"
    )
    document = ZoneFileParser.parse_text(original)
    node = next(document.iter_record_nodes())
    node.record = DNSRecord(
        owner=node.record.owner,
        ttl=None,
        rrclass=node.record.rrclass,
        rtype="SOA",
        rdata=("ns2.example.pl. dns.example.pl. 2026082101 7200 1200 604800 600"),
        raw=node.record.raw,
    )
    node.modified = True

    result = ZoneWriter().render_document(document)

    assert result == (
        "@ IN SOA ns2.example.pl. dns.example.pl. (\n"
        "    2026082101 ; serial\n"
        "    7200       ; refresh\n"
        "    1200        ; retry\n"
        "    604800    ; expire\n"
        "    600 )     ; minimum\n"
    )


def test_render_record_with_ttl() -> None:
    record = DNSRecord(
        owner="www",
        ttl=300,
        rrclass="IN",
        rtype="A",
        rdata="192.0.2.10",
        raw="",
    )

    assert ZoneWriter().render_record(record) == "www\t300\tIN\tA\t192.0.2.10"


def test_render_record_without_ttl() -> None:
    record = DNSRecord(
        owner="@",
        ttl=None,
        rrclass="IN",
        rtype="MX",
        rdata="10 mail.example.pl.",
        raw="",
    )

    assert ZoneWriter().render_record(record) == "@\tIN\tMX\t10 mail.example.pl."


def test_empty_owner_becomes_apex() -> None:
    record = DNSRecord(
        owner="",
        ttl=None,
        rrclass="IN",
        rtype="TXT",
        rdata='"test"',
        raw="",
    )

    assert ZoneWriter().render_record(record) == '@\tIN\tTXT\t"test"'


def test_negative_ttl_is_rejected() -> None:
    record = DNSRecord(
        owner="www",
        ttl=-1,
        rrclass="IN",
        rtype="A",
        rdata="192.0.2.10",
        raw="",
    )

    with pytest.raises(
        ZoneWriteError,
        match="TTL nie może być ujemny",
    ):
        ZoneWriter().render_record(record)


def test_empty_rdata_is_rejected() -> None:
    record = DNSRecord(
        owner="www",
        ttl=300,
        rrclass="IN",
        rtype="A",
        rdata="",
        raw="",
    )

    with pytest.raises(
        ZoneWriteError,
        match="RDATA",
    ):
        ZoneWriter().render_record(record)


def test_write_candidate_creates_secure_file(
    tmp_path: Path,
) -> None:
    document = ZoneFileParser.parse_text("$TTL 3600\nwww IN A 192.0.2.10\n")

    path = ZoneWriter().write_candidate(
        document,
        directory=tmp_path,
    )

    assert path.is_file()
    assert path.read_text(encoding="utf-8") == ("$TTL 3600\nwww IN A 192.0.2.10\n")

    assert path.stat().st_mode & 0o777 == 0o600


def test_unknown_node_type_is_rejected() -> None:
    document = ZoneDocument()
    document.nodes.append(object())  # type: ignore[arg-type]

    with pytest.raises(
        ZoneWriteError,
        match="Nieobsługiwany typ węzła",
    ):
        ZoneWriter().render_document(document)
