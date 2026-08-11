from datetime import date
from pathlib import Path

from zonectl.core.dnssec_finalize_serial import (
    DnssecFinalizeSerialStep,
    DnssecFinalizeSerialTransaction,
)


ZONE = """$TTL 3600
@ IN SOA ns1.example.pl. hostmaster.example.pl. (
    2026072701 ; serial
    3600 900 1209600 3600 )
@ IN NS ns1.example.pl.
"""


def transaction(tmp_path: Path, served: int = 2026072716):
    return DnssecFinalizeSerialTransaction(
        tmp_path / "backups",
        served_serial_reader=lambda _zone: served,
        validator=lambda _zone, _path: DnssecFinalizeSerialStep(
            "named-checkzone", True, "OK"
        ),
        today_provider=lambda: date(2026, 8, 11),
    )


def test_dry_run_plans_newer_serial_without_writes(tmp_path: Path) -> None:
    zone_file = tmp_path / "example.pl"
    zone_file.write_text(ZONE, encoding="utf-8")

    result = transaction(tmp_path).apply("example.pl", zone_file)

    assert result.status == "DRY-RUN"
    assert result.previous_serial == 2026072701
    assert result.served_serial == 2026072716
    assert result.new_serial == 2026081101
    assert zone_file.read_text(encoding="utf-8") == ZONE
    assert not (tmp_path / "backups").exists()


def test_commit_writes_atomically_and_preserves_backup(tmp_path: Path) -> None:
    zone_file = tmp_path / "example.pl"
    zone_file.write_text(ZONE, encoding="utf-8")

    result = transaction(tmp_path).apply("example.pl", zone_file, commit=True)

    assert result.status == "COMMIT"
    assert result.committed is True
    assert "2026081101 ; serial" in zone_file.read_text(encoding="utf-8")
    assert Path(result.backup).read_text(encoding="utf-8") == ZONE


def test_validation_failure_keeps_source_untouched(tmp_path: Path) -> None:
    zone_file = tmp_path / "example.pl"
    zone_file.write_text(ZONE, encoding="utf-8")
    operation = DnssecFinalizeSerialTransaction(
        tmp_path / "backups",
        served_serial_reader=lambda _zone: 2026072716,
        validator=lambda _zone, _path: DnssecFinalizeSerialStep(
            "named-checkzone", False, "invalid"
        ),
        today_provider=lambda: date(2026, 8, 11),
    )

    result = operation.apply("example.pl", zone_file, commit=True)

    assert result.status == "BLOCKED"
    assert zone_file.read_text(encoding="utf-8") == ZONE
    assert not (tmp_path / "backups").exists()


def test_missing_served_serial_is_blocked(tmp_path: Path) -> None:
    zone_file = tmp_path / "example.pl"
    zone_file.write_text(ZONE, encoding="utf-8")
    operation = DnssecFinalizeSerialTransaction(
        tmp_path / "backups", served_serial_reader=lambda _zone: None
    )

    result = operation.apply("example.pl", zone_file)

    assert result.status == "BLOCKED"
