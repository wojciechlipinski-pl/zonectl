from dataclasses import dataclass
from pathlib import Path

import pytest

from zonectl.core.zone_serializer import (
    ZoneSerializationError,
    ZoneSerializer,
)


@dataclass
class FakeRecord:
    owner: str
    rtype: str
    rdata: str
    ttl: int | None = None
    rclass: str = "IN"
    deleted: bool = False


@dataclass
class FakeModel:
    records: list[FakeRecord]


def test_render_record_with_ttl() -> None:
    serializer = ZoneSerializer()

    record = FakeRecord(
        owner="www",
        ttl=3600,
        rtype="A",
        rdata="192.0.2.10",
    )

    assert serializer.render_record(record) == "www\t3600\tIN\tA\t192.0.2.10"


def test_render_record_without_ttl() -> None:
    serializer = ZoneSerializer()

    record = FakeRecord(
        owner="@",
        ttl=None,
        rtype="MX",
        rdata="10 mail.example.pl.",
    )

    assert serializer.render_record(record) == "@\tIN\tMX\t10 mail.example.pl."


def test_empty_owner_becomes_apex() -> None:
    serializer = ZoneSerializer()

    record = FakeRecord(
        owner="",
        rtype="TXT",
        rdata='"test"',
    )

    assert serializer.render_record(record) == '@\tIN\tTXT\t"test"'


def test_deleted_records_are_skipped() -> None:
    serializer = ZoneSerializer()

    model = FakeModel(
        records=[
            FakeRecord(
                owner="www",
                rtype="A",
                rdata="192.0.2.10",
            ),
            FakeRecord(
                owner="old",
                rtype="A",
                rdata="192.0.2.20",
                deleted=True,
            ),
        ]
    )

    assert serializer.render_model(model) == "www\tIN\tA\t192.0.2.10\n"


def test_multiple_records() -> None:
    serializer = ZoneSerializer()

    model = FakeModel(
        records=[
            FakeRecord(
                owner="@",
                ttl=3600,
                rtype="A",
                rdata="192.0.2.1",
            ),
            FakeRecord(
                owner="www",
                ttl=300,
                rtype="CNAME",
                rdata="@",
            ),
        ]
    )

    assert serializer.render_model(model) == (
        "@\t3600\tIN\tA\t192.0.2.1\nwww\t300\tIN\tCNAME\t@\n"
    )


def test_invalid_ttl_is_rejected() -> None:
    serializer = ZoneSerializer()

    record = FakeRecord(
        owner="www",
        ttl=-1,
        rtype="A",
        rdata="192.0.2.1",
    )

    with pytest.raises(
        ZoneSerializationError,
        match="TTL nie może być ujemny",
    ):
        serializer.render_record(record)


def test_missing_rdata_is_rejected() -> None:
    serializer = ZoneSerializer()

    record = FakeRecord(
        owner="www",
        rtype="A",
        rdata="",
    )

    with pytest.raises(
        ZoneSerializationError,
        match="RDATA",
    ):
        serializer.render_record(record)


def test_write_candidate_creates_secure_file(
    tmp_path: Path,
) -> None:
    serializer = ZoneSerializer()

    model = FakeModel(
        records=[
            FakeRecord(
                owner="www",
                ttl=300,
                rtype="A",
                rdata="192.0.2.10",
            )
        ]
    )

    path = serializer.write_candidate(
        model,
        directory=tmp_path,
    )

    assert path.is_file()
    assert path.read_text(encoding="utf-8") == "www\t300\tIN\tA\t192.0.2.10\n"

    mode = path.stat().st_mode & 0o777
    assert mode == 0o600
