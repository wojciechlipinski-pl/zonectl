from pathlib import Path

from zonectl.core.zone_document import (
    BlankLine,
    Comment,
    Directive,
    RawLine,
    RecordNode,
)
from zonectl.core.zone_file_parser import ZoneFileParser


def test_preserves_blank_lines_and_comments() -> None:
    document = ZoneFileParser.parse_text(
        "\n; komentarz administratora\n   ; komentarz z wcięciem\n"
    )

    assert isinstance(document.nodes[0], BlankLine)
    assert document.nodes[0].raw == ""

    assert isinstance(document.nodes[1], Comment)
    assert document.nodes[1].raw == "; komentarz administratora"
    assert document.nodes[1].text == "komentarz administratora"

    assert isinstance(document.nodes[2], Comment)
    assert document.nodes[2].raw == "   ; komentarz z wcięciem"


def test_parses_directives() -> None:
    document = ZoneFileParser.parse_text(
        '$TTL 3600\n$ORIGIN example.pl.\n$INCLUDE "/etc/bind/local.inc"\n'
    )

    ttl = document.nodes[0]
    origin = document.nodes[1]
    include = document.nodes[2]

    assert isinstance(ttl, Directive)
    assert ttl.keyword == "$TTL"
    assert ttl.value == "3600"
    assert ttl.raw == "$TTL 3600"

    assert isinstance(origin, Directive)
    assert origin.keyword == "$ORIGIN"
    assert origin.value == "example.pl."

    assert isinstance(include, Directive)
    assert include.keyword == "$INCLUDE"
    assert include.value == '"/etc/bind/local.inc"'


def test_parses_basic_record() -> None:
    document = ZoneFileParser.parse_text("www 300 IN A 192.0.2.10\n")

    node = document.nodes[0]

    assert isinstance(node, RecordNode)
    assert node.raw == "www 300 IN A 192.0.2.10"
    assert node.record.owner == "www"
    assert node.record.ttl == 300
    assert node.record.rrclass == "IN"
    assert node.record.rtype == "A"
    assert node.record.rdata == "192.0.2.10"


def test_parses_record_without_ttl() -> None:
    document = ZoneFileParser.parse_text("@ IN MX 10 mail.example.pl.\n")

    node = document.nodes[0]

    assert isinstance(node, RecordNode)
    assert node.record.owner == "@"
    assert node.record.ttl is None
    assert node.record.rrclass == "IN"
    assert node.record.rtype == "MX"
    assert node.record.rdata == "10 mail.example.pl."


def test_parses_ttl_before_or_after_class() -> None:
    document = ZoneFileParser.parse_text(
        "one 300 IN A 192.0.2.1\ntwo IN 600 A 192.0.2.2\n"
    )

    first = document.nodes[0]
    second = document.nodes[1]

    assert isinstance(first, RecordNode)
    assert isinstance(second, RecordNode)

    assert first.record.ttl == 300
    assert second.record.ttl == 600


def test_uses_previous_owner_when_owner_is_omitted() -> None:
    document = ZoneFileParser.parse_text(
        "www 300 IN A 192.0.2.10\n    300 IN AAAA 2001:db8::10\n"
    )

    first = document.nodes[0]
    second = document.nodes[1]

    assert isinstance(first, RecordNode)
    assert isinstance(second, RecordNode)

    assert first.record.owner == "www"
    assert second.record.owner == "www"
    assert second.record.rtype == "AAAA"


def test_semicolon_inside_txt_is_not_a_comment() -> None:
    document = ZoneFileParser.parse_text(
        'txt IN TXT "wartosc;nie-komentarz" ; komentarz\n'
    )

    node = document.nodes[0]

    assert isinstance(node, RecordNode)
    assert node.record.rdata == '"wartosc;nie-komentarz"'
    assert node.raw.endswith("; komentarz")


def test_unknown_line_becomes_raw_line() -> None:
    document = ZoneFileParser.parse_text("to nie jest rekord DNS\n")

    assert isinstance(document.nodes[0], RawLine)
    assert document.nodes[0].raw == "to nie jest rekord DNS"


def test_multiline_soa_is_parsed_and_preserved_as_one_record() -> None:
    text = (
        "@ IN SOA ns1.example.pl. hostmaster.example.pl. (\n"
        "    2026072901\n"
        "    3600\n"
        "    900\n"
        "    1209600\n"
        "    3600 )\n"
    )

    document = ZoneFileParser.parse_text(text)

    assert len(document.nodes) == 1
    node = document.nodes[0]
    assert isinstance(node, RecordNode)
    assert node.record.owner == "@"
    assert node.record.rtype == "SOA"
    assert node.record.rdata == (
        "ns1.example.pl. hostmaster.example.pl. 2026072901 3600 900 1209600 3600"
    )
    assert node.raw == text.rstrip("\n")


def test_preserves_trailing_newline_information() -> None:
    with_newline = ZoneFileParser.parse_text("www IN A 192.0.2.1\n")
    without_newline = ZoneFileParser.parse_text("www IN A 192.0.2.1")

    assert with_newline.trailing_newline is True
    assert without_newline.trailing_newline is False


def test_parse_file_sets_source_path(
    tmp_path: Path,
) -> None:
    path = tmp_path / "example.pl"
    path.write_text(
        "$TTL 3600\nwww IN A 192.0.2.1\n",
        encoding="utf-8",
    )

    document = ZoneFileParser.parse_file(path)

    assert document.source_path == path.resolve()
    assert len(document.records) == 1


def test_rfc3597_unknown_type_is_supported() -> None:
    document = ZoneFileParser.parse_text("test 300 IN TYPE65280 \\# 4 DEADBEEF\n")

    node = document.nodes[0]

    assert isinstance(node, RecordNode)
    assert node.record.rtype == "TYPE65280"
    assert node.record.rdata == "\\# 4 DEADBEEF"
