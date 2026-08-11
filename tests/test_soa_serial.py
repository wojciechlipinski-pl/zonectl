from datetime import date

import pytest

from zonectl.core.soa_serial import (
    SoaSerialError,
    bump_document_soa_serial,
    next_soa_serial,
)
from zonectl.core.zone_file_parser import ZoneFileParser
from zonectl.core.zone_writer import ZoneWriter


def test_old_serial_becomes_today_sequence_01() -> None:
    assert next_soa_serial(
        2026072701,
        today=date(2026, 7, 29),
    ) == 2026072901


def test_today_serial_is_incremented() -> None:
    assert next_soa_serial(
        2026072901,
        today=date(2026, 7, 29),
    ) == 2026072902


def test_future_or_higher_serial_remains_monotonic() -> None:
    assert next_soa_serial(
        2026073005,
        today=date(2026, 7, 29),
    ) == 2026073006


def test_bump_can_exceed_an_external_minimum_serial() -> None:
    document = ZoneFileParser.parse_text(
        "@ IN SOA ns1.example.pl. hostmaster.example.pl. "
        "2026072701 3600 900 1209600 3600\n"
    )

    change = bump_document_soa_serial(
        document,
        today=date(2026, 8, 11),
        minimum_current=2026072716,
    )

    assert change.previous == 2026072701
    assert change.current == 2026081101


def test_multiline_soa_serial_is_bumped_without_format_loss() -> None:
    original = (
        "$ORIGIN example.pl.\n"
        "$TTL 3600\n"
        "@       IN SOA  ns1.example.pl. hostmaster.example.pl. (\n"
        "                2026072701     ; serial: RRRRMMDDNN\n"
        "                3600           ; refresh\n"
        "                900            ; retry\n"
        "                1209600        ; expire\n"
        "                3600           ; negative TTL\n"
        "                )\n"
        "@       IN A    192.0.2.10\n"
    )

    document = ZoneFileParser.parse_text(original)

    change = bump_document_soa_serial(
        document,
        today=date(2026, 7, 29),
    )

    rendered = ZoneWriter().render_document(document)

    assert change.previous == 2026072701
    assert change.current == 2026072901
    assert (
        "                2026072901     "
        "; serial: RRRRMMDDNN\n"
    ) in rendered
    assert (
        "@       IN SOA  ns1.example.pl. "
        "hostmaster.example.pl. (\n"
    ) in rendered
    assert "@       IN A    192.0.2.10\n" in rendered


def test_single_line_soa_serial_is_bumped() -> None:
    original = (
        "@ IN SOA ns1.example.pl. hostmaster.example.pl. "
        "2026072901 3600 900 1209600 3600\n"
    )

    document = ZoneFileParser.parse_text(original)

    change = bump_document_soa_serial(
        document,
        today=date(2026, 7, 29),
    )

    rendered = ZoneWriter().render_document(document)

    assert change.current == 2026072902
    assert "2026072902" in rendered


def test_missing_soa_is_rejected() -> None:
    document = ZoneFileParser.parse_text(
        "www IN A 192.0.2.10\n"
    )

    with pytest.raises(
        SoaSerialError,
        match="Nie znaleziono",
    ):
        bump_document_soa_serial(
            document,
            today=date(2026, 7, 29),
        )
