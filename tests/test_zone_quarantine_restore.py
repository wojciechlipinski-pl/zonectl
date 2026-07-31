import hashlib
import json
from pathlib import Path

import pytest

from zonectl.core.zone_quarantine_restore import (
    QuarantineRestoreError,
    QuarantineRestoreStep,
    QuarantineRestoreTransaction,
)


def setup(tmp_path: Path):
    package = tmp_path / "quarantine/example.invalid/tx"
    package.mkdir(parents=True)
    (package / "zone.db").write_text("zone data\n")
    (package / "zone.conf").write_text("zone declaration\n")
    files = {
        name: hashlib.sha256((package / name).read_bytes()).hexdigest()
        for name in ("zone.db", "zone.conf")
    }
    (package / "manifest.json").write_text(json.dumps({
        "zone": "example.invalid", "status": "QUARANTINED", "files": files
    }))
    zone = tmp_path / "zones/example.invalid"
    declaration = tmp_path / "bind/zones.d/example.invalid.conf"
    index = tmp_path / "bind/zones.conf"
    zone.parent.mkdir(parents=True)
    declaration.parent.mkdir(parents=True)
    index.write_text("# empty\n")
    plan = QuarantineRestoreTransaction.plan(
        "example.invalid", package_directory=package, zone_file=zone,
        active_declaration=declaration, managed_index=index,
        root_config=tmp_path / "bind/named.conf",
    )
    return package, zone, declaration, index, plan


def ok(name: str) -> QuarantineRestoreStep:
    return QuarantineRestoreStep(name, True, "OK")


def engine(loaded=None):
    return QuarantineRestoreTransaction(
        zone_validator=lambda name, path: ok("named-checkzone"),
        config_validator=lambda path: ok("named-checkconf"),
        activator=lambda name: ok("rndc-reconfig"),
        loaded_verifier=loaded or (lambda name: ok("rndc-zonestatus")),
    )


def test_dry_run_preserves_package_and_has_no_side_effects(tmp_path: Path) -> None:
    package, zone, declaration, index, plan = setup(tmp_path)
    result = engine().apply(plan)
    assert result.status == "DRY-RUN"
    assert package.exists() and not zone.exists() and not declaration.exists()


def test_restore_keeps_package_and_activates_working_files(tmp_path: Path) -> None:
    package, zone, declaration, index, plan = setup(tmp_path)
    result = engine().apply(plan, commit=True)
    assert result.status == "RESTORED"
    assert zone.read_text() == "zone data\n"
    assert declaration.read_text() == "zone declaration\n"
    assert plan.include_line in index.read_text()
    assert package.is_dir()


def test_failed_activation_rolls_back_but_keeps_package(tmp_path: Path) -> None:
    package, zone, declaration, index, plan = setup(tmp_path)
    result = engine(loaded=lambda name: QuarantineRestoreStep("loaded", False, "no")).apply(plan, commit=True)
    assert result.status == "ROLLED-BACK"
    assert not zone.exists() and not declaration.exists()
    assert package.is_dir()


def test_modified_package_is_rejected(tmp_path: Path) -> None:
    package, zone, declaration, index, plan = setup(tmp_path)
    (package / "zone.db").write_text("tampered\n")
    with pytest.raises(QuarantineRestoreError, match="suma kontrolna"):
        QuarantineRestoreTransaction.plan(
            "example.invalid", package_directory=package, zone_file=zone,
            active_declaration=declaration, managed_index=index,
        )
