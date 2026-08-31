from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from zonectl.core.zone_quarantine import ZoneQuarantineTransaction
from zonectl.core.zone_quarantine_restore import (
    QuarantineRestoreError,
    QuarantineRestoreStep,
    QuarantineRestoreTransaction,
)
from tests.test_zone_quarantine import setup as quarantine_setup
from tests.test_zone_quarantine_restore import setup as restore_setup


def _metadata(path: Path) -> tuple[int, int, int]:
    stat = path.stat()
    return stat.st_uid, stat.st_gid, stat.st_mode & 0o777


@pytest.mark.parametrize("failed_replace", (1, 2, 3))
def test_quarantine_package_write_failure_keeps_working_copies_and_no_package(
    tmp_path: Path,
    monkeypatch,
    failed_replace: int,
) -> None:
    zone, _active, archived, _index, plan = quarantine_setup(tmp_path)
    zone_content = zone.read_bytes()
    declaration_content = archived.read_bytes()
    real_replace = os.replace
    calls = 0

    def fail_once(source, destination):
        nonlocal calls
        calls += 1
        if calls == failed_replace:
            raise OSError(f"forced replace failure {failed_replace}")
        return real_replace(source, destination)

    monkeypatch.setattr(os, "replace", fail_once)
    result = ZoneQuarantineTransaction().apply(
        plan,
        commit=True,
        confirmation="example.invalid",
    )

    assert result.status == "ROLLED-BACK"
    assert zone.read_bytes() == zone_content
    assert archived.read_bytes() == declaration_content
    assert not Path(result.package_directory or "missing").exists()


def test_quarantine_manifest_records_original_metadata(tmp_path: Path) -> None:
    zone, _active, archived, _index, plan = quarantine_setup(tmp_path)
    zone.chmod(0o600)
    archived.chmod(0o644)
    expected = {
        "zone.db": _metadata(zone),
        "zone.conf": _metadata(archived),
    }

    result = ZoneQuarantineTransaction().apply(
        plan,
        commit=True,
        confirmation="example.invalid",
    )

    manifest = json.loads(
        (Path(result.package_directory or "") / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    for filename, (uid, gid, mode) in expected.items():
        assert manifest["metadata"][filename] == {
            "uid": uid,
            "gid": gid,
            "mode": mode,
        }


@pytest.mark.parametrize("failed_replace", (1, 2, 3))
def test_quarantine_restore_write_failure_keeps_package_and_disabled_state(
    tmp_path: Path,
    monkeypatch,
    failed_replace: int,
) -> None:
    package, zone, declaration, index, plan = restore_setup(tmp_path)
    original_index = index.read_bytes()
    real_replace = os.replace
    calls = 0

    def fail_once(source, destination):
        nonlocal calls
        calls += 1
        if calls == failed_replace:
            raise OSError(f"forced replace failure {failed_replace}")
        return real_replace(source, destination)

    monkeypatch.setattr(os, "replace", fail_once)
    engine = QuarantineRestoreTransaction(
        zone_validator=lambda _name, _path: QuarantineRestoreStep(
            "named-checkzone", True, "OK"
        ),
        config_validator=lambda _path: QuarantineRestoreStep(
            "named-checkconf", True, "OK"
        ),
        activator=lambda _name: QuarantineRestoreStep("rndc-reconfig", True, "OK"),
        loaded_verifier=lambda _name: QuarantineRestoreStep("loaded", True, "OK"),
    )
    result = engine.apply(plan, commit=True)

    assert result.status == "ROLLED-BACK"
    assert package.exists()
    assert not zone.exists()
    assert not declaration.exists()
    assert index.read_bytes() == original_index


def test_restore_uses_metadata_saved_by_quarantine(tmp_path: Path) -> None:
    zone, active, archived, index, quarantine_plan = quarantine_setup(tmp_path)
    zone.chmod(0o600)
    archived.chmod(0o644)
    expected_zone = _metadata(zone)
    expected_declaration = _metadata(archived)
    quarantined = ZoneQuarantineTransaction().apply(
        quarantine_plan,
        commit=True,
        confirmation="example.invalid",
    )
    package = Path(quarantined.package_directory or "")
    restore_plan = QuarantineRestoreTransaction.plan(
        "example.invalid",
        package_directory=package,
        zone_file=zone,
        active_declaration=active,
        managed_index=index,
    )
    engine = QuarantineRestoreTransaction(
        zone_validator=lambda _name, _path: QuarantineRestoreStep(
            "named-checkzone", True, "OK"
        ),
        config_validator=lambda _path: QuarantineRestoreStep(
            "named-checkconf", True, "OK"
        ),
        activator=lambda _name: QuarantineRestoreStep("rndc-reconfig", True, "OK"),
        loaded_verifier=lambda _name: QuarantineRestoreStep("loaded", True, "OK"),
    )

    result = engine.apply(restore_plan, commit=True)

    assert result.status == "RESTORED"
    assert _metadata(zone) == expected_zone
    assert _metadata(active) == expected_declaration


def test_invalid_quarantine_metadata_is_rejected(tmp_path: Path) -> None:
    package, zone, declaration, index, _plan = restore_setup(tmp_path)
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["metadata"] = {
        "zone.db": {"uid": 0, "gid": 0, "mode": "0640"},
        "zone.conf": {"uid": 0, "gid": 0, "mode": 0o640},
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(QuarantineRestoreError, match="metadane"):
        QuarantineRestoreTransaction.plan(
            "example.invalid",
            package_directory=package,
            zone_file=zone,
            active_declaration=declaration,
            managed_index=index,
        )


def test_restore_activation_failure_rolls_back_and_reconfigures(
    tmp_path: Path,
) -> None:
    package, zone, declaration, index, plan = restore_setup(tmp_path)
    original_index = index.read_bytes()
    calls = 0

    def activate(_name: str) -> QuarantineRestoreStep:
        nonlocal calls
        calls += 1
        return QuarantineRestoreStep("rndc-reconfig", calls == 2, f"call {calls}")

    engine = QuarantineRestoreTransaction(
        zone_validator=lambda _name, _path: QuarantineRestoreStep(
            "named-checkzone", True, "OK"
        ),
        config_validator=lambda _path: QuarantineRestoreStep(
            "named-checkconf", True, "OK"
        ),
        activator=activate,
        loaded_verifier=lambda _name: QuarantineRestoreStep("loaded", True, "OK"),
    )
    result = engine.apply(plan, commit=True)

    assert result.status == "ROLLED-BACK"
    assert calls == 2
    assert package.exists()
    assert not zone.exists()
    assert not declaration.exists()
    assert index.read_bytes() == original_index


def test_restore_failed_rollback_is_reported(tmp_path: Path) -> None:
    package, zone, declaration, _index, plan = restore_setup(tmp_path)
    engine = QuarantineRestoreTransaction(
        zone_validator=lambda _name, _path: QuarantineRestoreStep(
            "named-checkzone", True, "OK"
        ),
        config_validator=lambda _path: QuarantineRestoreStep(
            "named-checkconf", True, "OK"
        ),
        activator=lambda _name: QuarantineRestoreStep(
            "rndc-reconfig", False, "BIND unavailable"
        ),
        loaded_verifier=lambda _name: QuarantineRestoreStep("loaded", True, "OK"),
    )
    result = engine.apply(plan, commit=True)

    assert result.status == "ROLLBACK-FAILED"
    assert result.rolled_back is False
    assert package.exists()
    assert not zone.exists()
    assert not declaration.exists()
    assert any(step.name == "rollback" and not step.ok for step in result.steps)
