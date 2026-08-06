from __future__ import annotations

import hashlib
import json
from pathlib import Path

from zonectl.core.discovery import ZoneConfig
from zonectl.core.dnssec_disable_plan import DnssecDisablePlanner
from zonectl.core.dnssec_withdrawal_backup import DnssecWithdrawalBackup


def plan(tmp_path: Path):
    zone_file = tmp_path / "example.pl"
    zone_file.write_text("zone data\n")
    (tmp_path / "example.pl.signed").write_text("signed data\n")
    keys = tmp_path / "keys"
    keys.mkdir()
    for suffix, content in (
        ("key", "public"),
        ("private", "private"),
        ("state", "state"),
    ):
        (keys / f"Kexample.pl.+013+12345.{suffix}").write_text(content)
    declaration = tmp_path / "zones.conf"
    declaration.write_text(
        'zone "example.pl" {\n'
        ' type primary;\n'
        f' file "{zone_file}";\n'
        ' dnssec-policy default;\n'
        ' inline-signing yes;\n'
        f' key-directory "{keys}";\n'
        '};\n'
    )
    zone = ZoneConfig(
        "example.pl",
        "primary",
        zone_file,
        declaration,
        dnssec_policy="default",
        inline_signing=True,
        key_directory=keys,
        source_exists=True,
    )
    return DnssecDisablePlanner().plan(zone)


def test_dry_run_has_no_side_effects(tmp_path: Path) -> None:
    current = plan(tmp_path)
    backup_root = tmp_path / "backups"

    result = DnssecWithdrawalBackup(backup_root).create(current)

    assert result.status == "DRY-RUN"
    assert not backup_root.exists()
    assert current.declaration_file.read_text() == current.original_text


def test_commit_creates_verified_complete_package(tmp_path: Path) -> None:
    current = plan(tmp_path)
    result = DnssecWithdrawalBackup(tmp_path / "backups").create(
        current,
        commit=True,
        dnssec_report={"status": "PASS"},
        ds_check={"status": "PASS"},
    )

    assert result.status == "BACKUP-CREATED"
    assert result.committed is True
    package = Path(result.package)
    payload = json.loads((package / "manifest.json").read_text())
    assert payload["dnssec_report"]["status"] == "PASS"
    assert payload["ds_check"]["status"] == "PASS"
    assert len(payload["files"]) == 6
    for record in payload["files"]:
        stored = package / record["stored_as"]
        assert stored.is_file()
        assert hashlib.sha256(stored.read_bytes()).hexdigest() == record["sha256"]
    assert current.declaration_file.read_text() == current.original_text


def test_changed_configuration_is_rejected(tmp_path: Path) -> None:
    current = plan(tmp_path)
    current.declaration_file.write_text("changed\n")

    result = DnssecWithdrawalBackup(tmp_path / "backups").create(
        current, commit=True
    )

    assert result.status == "CONFLICT"
    assert not (tmp_path / "backups").exists()


def test_missing_key_is_rejected_without_partial_package(tmp_path: Path) -> None:
    current = plan(tmp_path)
    current.key_files[0].unlink()

    result = DnssecWithdrawalBackup(tmp_path / "backups").create(
        current, commit=True
    )

    assert result.status == "CONFLICT"
    assert not (tmp_path / "backups").exists()
