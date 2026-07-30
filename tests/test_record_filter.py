from __future__ import annotations

import pytest

from zonectl.core.record_filter import RecordFilter, RecordFilterError
from zonectl.core.zone_model import ChangeKind, ZoneRecordView
from zonectl.core.zone_parser import DNSRecord


def view(
    identifier: int,
    owner: str,
    rtype: str,
    ttl: int | None,
    value: str,
    change: ChangeKind | None = None,
) -> ZoneRecordView:
    return ZoneRecordView(
        identifier=identifier,
        record=DNSRecord(
            owner=owner,
            ttl=ttl,
            rrclass="IN",
            rtype=rtype,
            rdata=value,
            raw="",
        ),
        change_kind=change,
    )


@pytest.fixture
def records() -> list[ZoneRecordView]:
    return [
        view(
            1,
            "www.example.pl.",
            "A",
            3600,
            "192.0.2.10",
        ),
        view(
            2,
            "mail.example.pl.",
            "AAAA",
            300,
            "2001:db8::10",
            ChangeKind.MODIFY,
        ),
        view(
            3,
            "_verify.example.pl.",
            "TXT",
            None,
            '"some verification text"',
            ChangeKind.ADD,
        ),
        view(
            4,
            "old.example.pl.",
            "CNAME",
            3600,
            "www.example.pl.",
            ChangeKind.DELETE,
        ),
    ]


def identifiers(
    query: str,
    records: list[ZoneRecordView],
) -> list[int]:
    return [
        item.identifier
        for item in RecordFilter(query).apply(records, "example.pl")
    ]


def test_plain_text_keeps_legacy_search(
    records: list[ZoneRecordView],
) -> None:
    assert identifiers("www", records) == [1, 4]


def test_field_filters_are_case_insensitive(
    records: list[ZoneRecordView],
) -> None:
    assert identifiers("type:a", records) == [1]
    assert identifiers("name:MAIL", records) == [2]


def test_multiple_terms_use_and(
    records: list[ZoneRecordView],
) -> None:
    assert identifiers("ttl>=300 ttl<3600 type:AAAA", records) == [2]


def test_negated_term_excludes_matches(
    records: list[ZoneRecordView],
) -> None:
    assert identifiers("-type:AAAA ttl:3600", records) == [1, 4]


def test_regex_and_quoted_value(
    records: list[ZoneRecordView],
) -> None:
    query = 'name~^_ value:"some verification"'
    assert identifiers(query, records) == [3]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("status:modified", [2]),
        ("status:dodano", [3]),
        ("status:deleted", [4]),
        ("status:unchanged", [1]),
    ],
)
def test_change_status_filter(
    query: str,
    expected: list[int],
    records: list[ZoneRecordView],
) -> None:
    assert identifiers(query, records) == expected


def test_missing_ttl_uses_dash(
    records: list[ZoneRecordView],
) -> None:
    assert identifiers("ttl:-", records) == [3]
    assert identifiers("ttl!=-", records) == [1, 2, 4]


@pytest.mark.parametrize(
    "query",
    [
        'name:"unterminated',
        "name~[",
        "ttl:abc",
        "status:unknown",
        "ttl~3600",
    ],
)
def test_invalid_filter_is_rejected(query: str) -> None:
    with pytest.raises(RecordFilterError):
        RecordFilter(query)
