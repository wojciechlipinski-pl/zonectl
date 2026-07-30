from __future__ import annotations

import pytest

from zonectl.core.bulk_operations import (
    BulkAction,
    BulkOperation,
    BulkOperationError,
)
from zonectl.core.zone_model import ZoneModel, ZoneModelReadOnlyError
from zonectl.core.zone_parser import DNSRecord


def record(owner: str, rtype: str, ttl: int | None, value: str) -> DNSRecord:
    return DNSRecord(owner, ttl, "IN", rtype, value, "")


def model(*, read_only: bool = False) -> ZoneModel:
    return ZoneModel(
        "example.pl",
        [
            record("www.example.pl.", "A", 300, "192.0.2.10"),
            record("mail.example.pl.", "A", 300, "192.0.2.20"),
            record("example.pl.", "MX", 3600, "10 mail.example.pl."),
            record("text.example.pl.", "TXT", None, '"old value"'),
        ],
        read_only=read_only,
    )


def test_parse_set_ttl() -> None:
    operation = BulkOperation.parse(
        "SELECT type:A ttl:300 SET ttl=7200"
    )
    assert operation.action is BulkAction.SET
    assert operation.query == "type:A ttl:300"
    assert operation.field == "ttl"
    assert operation.value == "7200"


def test_parse_quoted_value() -> None:
    operation = BulkOperation.parse(
        'SELECT type:TXT SET value="new text"'
    )
    assert operation.field == "value"
    assert operation.value == "new text"


def test_parse_delete() -> None:
    operation = BulkOperation.parse("SELECT type:TXT DELETE")
    assert operation.action is BulkAction.DELETE


@pytest.mark.parametrize(
    "command",
    [
        "type:A SET ttl=1",
        "SELECT type:A SET owner=www",
        "SELECT type:A SET ttl=abc",
        "SELECT type:A SET value=",
        "SELECT ttl:abc DELETE",
    ],
)
def test_invalid_command_is_rejected(command: str) -> None:
    with pytest.raises(BulkOperationError):
        BulkOperation.parse(command)


def test_set_ttl_changes_all_matches_as_one_undo_step() -> None:
    zone = model()
    operation = BulkOperation.parse(
        "SELECT type:A SET ttl=7200"
    )

    assert operation.apply(zone) == 2
    assert [item.ttl for item in zone.records[:2]] == [7200, 7200]
    assert zone.change_count == 2

    assert zone.undo() is True
    assert [item.ttl for item in zone.records[:2]] == [300, 300]
    assert zone.change_count == 0
    assert zone.undo() is False


def test_delete_changes_all_matches_as_one_undo_step() -> None:
    zone = model()
    operation = BulkOperation.parse(
        "SELECT type:A DELETE"
    )

    assert operation.apply(zone) == 2
    assert [item.rtype for item in zone.records] == ["MX", "TXT"]

    assert zone.undo() is True
    assert len(zone.records) == 4


def test_set_missing_ttl_to_explicit_value() -> None:
    zone = model()
    operation = BulkOperation.parse(
        "SELECT ttl:- SET ttl=600"
    )

    assert operation.apply(zone) == 1
    assert zone.records[-1].ttl == 600


def test_set_ttl_to_inherited_value() -> None:
    zone = model()
    operation = BulkOperation.parse(
        "SELECT type:MX SET ttl=-"
    )

    assert operation.apply(zone) == 1
    assert zone.records[2].ttl is None


def test_invalid_type_specific_value_is_rejected() -> None:
    zone = model()
    operation = BulkOperation.parse(
        "SELECT type:A SET value=999.999.999.999"
    )

    with pytest.raises(BulkOperationError, match="IPv4"):
        operation.matches(zone)

    assert zone.change_count == 0


def test_read_only_model_rejects_bulk_change() -> None:
    zone = model(read_only=True)
    operation = BulkOperation.parse(
        "SELECT type:A DELETE"
    )

    with pytest.raises(ZoneModelReadOnlyError):
        operation.apply(zone)


def test_bulk_operation_metadata_is_removed_by_single_undo() -> None:
    zone = model()
    operation = BulkOperation.parse(
        "SELECT type:A SET ttl=7200"
    )

    assert operation.apply(zone) == 2
    assert zone.transaction_metadata["bulk_operation_count"] == 1
    assert zone.transaction_metadata["bulk_operations"] == [
        {
            "query": "type:A",
            "action": "SET",
            "field": "ttl",
            "value": "7200",
            "matched_count": 2,
        }
    ]

    assert zone.undo() is True
    assert zone.transaction_metadata["bulk_operation_count"] == 0
