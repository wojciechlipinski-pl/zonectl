from pathlib import Path
import json

import pytest

from zonectl.core.zone_quarantine import (
    ZoneQuarantineError,
    ZoneQuarantineTransaction,
)


def setup(tmp_path: Path):
    zone = tmp_path / "zones/example.invalid"
    active = tmp_path / "bind/zones.d/example.invalid.conf"
    archived = tmp_path / "disabled/example.invalid/example.invalid.conf"
    index = tmp_path / "bind/zones.conf"
    zone.parent.mkdir(parents=True)
    active.parent.mkdir(parents=True)
    archived.parent.mkdir(parents=True)
    zone.write_text("zone data\n")
    archived.write_text("zone declaration\n")
    index.write_text("# empty\n")
    plan = ZoneQuarantineTransaction.plan(
        "example.invalid",
        zone_file=zone,
        archived_declaration=archived,
        active_declaration=active,
        managed_index=index,
        quarantine_root=tmp_path / "quarantine",
        reason="retired",
    )
    return zone, active, archived, index, plan


def test_dry_run_preserves_disabled_zone(tmp_path: Path) -> None:
    zone, active, archived, index, plan = setup(tmp_path)
    result = ZoneQuarantineTransaction().apply(plan)
    assert result.status == "DRY-RUN"
    assert zone.exists() and archived.exists()


def test_commit_requires_full_zone_confirmation(tmp_path: Path) -> None:
    zone, active, archived, index, plan = setup(tmp_path)
    result = ZoneQuarantineTransaction().apply(
        plan, commit=True, confirmation="wrong.invalid"
    )
    assert result.status == "CONFIRMATION-REQUIRED"
    assert zone.exists() and archived.exists()


def test_quarantine_creates_verified_recovery_package(tmp_path: Path) -> None:
    zone, active, archived, index, plan = setup(tmp_path)
    result = ZoneQuarantineTransaction().apply(
        plan, commit=True, confirmation="example.invalid"
    )
    assert result.status == "QUARANTINED"
    assert not zone.exists() and not archived.exists()
    package = Path(result.package_directory)
    manifest = json.loads((package / "manifest.json").read_text())
    assert manifest["zone"] == "example.invalid"
    assert set(manifest["files"]) == {"zone.db", "zone.conf"}
    assert (package / "zone.db").read_text() == "zone data\n"
    assert (package / "zone.conf").read_text() == "zone declaration\n"


def test_active_zone_cannot_be_quarantined(tmp_path: Path) -> None:
    zone, active, archived, index, plan = setup(tmp_path)
    active.write_text("active\n")
    with pytest.raises(ZoneQuarantineError, match="aktywną deklarację"):
        ZoneQuarantineTransaction.plan(
            "example.invalid",
            zone_file=zone,
            archived_declaration=archived,
            active_declaration=active,
            managed_index=index,
            reason="retired",
        )
