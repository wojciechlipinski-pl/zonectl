from __future__ import annotations

import os
from pathlib import Path

import pytest

from zonectl.core.managed_zone_migration_transaction import (
    ManagedZoneMigrationStep,
    ManagedZoneMigrationTransaction,
)
from zonectl.core.managed_zone_relocation_transaction import (
    ManagedZoneRelocationTransaction,
)
from tests.test_managed_zone_migration_transaction import _plan as migration_plan
from tests.test_managed_zone_relocation import _planner as relocation_planner


def _ok(name: str):
    return lambda *_args: ManagedZoneMigrationStep(name, True, "OK")


def _metadata(path: Path) -> tuple[int, int, int]:
    stat = path.stat()
    return stat.st_uid, stat.st_gid, stat.st_mode & 0o777


@pytest.mark.parametrize("failed_replace", (1, 2, 3))
def test_migration_write_failures_restore_all_configuration(
    tmp_path: Path,
    monkeypatch,
    failed_replace: int,
) -> None:
    plan, root = migration_plan(tmp_path)
    source = plan.source_config.read_bytes()
    index = plan.managed_config.read_bytes()
    real_replace = os.replace
    calls = 0

    def fail_once(source_path, destination):
        nonlocal calls
        calls += 1
        if calls == failed_replace:
            raise OSError(f"forced replace failure {failed_replace}")
        return real_replace(source_path, destination)

    monkeypatch.setattr(os, "replace", fail_once)
    result = ManagedZoneMigrationTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=root,
        config_validator=_ok("named-checkconf"),
    ).apply(plan, commit=True)

    assert result.status == "ROLLED-BACK"
    assert plan.source_config.read_bytes() == source
    assert plan.managed_config.read_bytes() == index
    assert not plan.declaration_file.exists()


def test_migration_preserves_source_and_index_metadata(tmp_path: Path) -> None:
    plan, root = migration_plan(tmp_path)
    plan.source_config.chmod(0o600)
    plan.managed_config.chmod(0o644)
    expected_source = _metadata(plan.source_config)
    expected_index = _metadata(plan.managed_config)
    result = ManagedZoneMigrationTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=root,
        config_validator=_ok("named-checkconf"),
    ).apply(plan, commit=True)

    assert result.status == "COMMIT"
    assert _metadata(plan.source_config) == expected_source
    assert _metadata(plan.managed_config) == expected_index


def test_migration_activation_failure_rolls_back_and_reconfigures(
    tmp_path: Path,
) -> None:
    plan, root = migration_plan(tmp_path)
    calls = 0

    def activate(_zone: str) -> ManagedZoneMigrationStep:
        nonlocal calls
        calls += 1
        return ManagedZoneMigrationStep(
            "rndc-reconfig", calls == 2, f"call {calls}"
        )

    result = ManagedZoneMigrationTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=root,
        config_validator=_ok("named-checkconf"),
        activator=activate,
        loaded_verifier=_ok("rndc-zonestatus"),
    ).apply(plan, commit=True, activate=True)

    assert result.status == "ROLLED-BACK"
    assert result.rolled_back is True
    assert calls == 2
    assert not plan.declaration_file.exists()


def test_migration_failed_rollback_is_reported(tmp_path: Path) -> None:
    plan, root = migration_plan(tmp_path)
    result = ManagedZoneMigrationTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=root,
        config_validator=_ok("named-checkconf"),
        activator=lambda _zone: ManagedZoneMigrationStep(
            "rndc-reconfig", False, "BIND unavailable"
        ),
        loaded_verifier=_ok("rndc-zonestatus"),
    ).apply(plan, commit=True, activate=True)

    assert result.status == "ROLLBACK-FAILED"
    assert result.rolled_back is False
    assert not plan.declaration_file.exists()


@pytest.mark.parametrize("failed_replace", (1, 2))
def test_relocation_write_failures_restore_source_and_declaration(
    tmp_path: Path,
    monkeypatch,
    failed_replace: int,
) -> None:
    planner, source, target, declaration = relocation_planner(tmp_path)
    plan = planner.plan("example.pl")
    source_content = source.read_bytes()
    declaration_content = declaration.read_bytes()
    real_replace = os.replace
    calls = 0

    def fail_once(source_path, destination):
        nonlocal calls
        calls += 1
        if calls == failed_replace:
            raise OSError(f"forced replace failure {failed_replace}")
        return real_replace(source_path, destination)

    monkeypatch.setattr(os, "replace", fail_once)
    result = ManagedZoneRelocationTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=planner.root_config,
        zone_validator=_ok("named-checkzone"),
        config_validator=_ok("named-checkconf"),
    ).apply(plan, commit=True)

    assert result.status == "ROLLED-BACK"
    assert source.read_bytes() == source_content
    assert declaration.read_bytes() == declaration_content
    assert not target.exists()


def test_relocation_preserves_zone_and_declaration_metadata(tmp_path: Path) -> None:
    planner, source, target, declaration = relocation_planner(tmp_path)
    source.chmod(0o600)
    declaration.chmod(0o644)
    plan = planner.plan("example.pl")
    source_metadata = _metadata(source)
    declaration_metadata = _metadata(declaration)
    result = ManagedZoneRelocationTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=planner.root_config,
        zone_validator=_ok("named-checkzone"),
        config_validator=_ok("named-checkconf"),
    ).apply(plan, commit=True)

    assert result.status == "COMMIT"
    assert _metadata(target) == source_metadata
    assert _metadata(declaration) == declaration_metadata


def test_relocation_loaded_failure_rolls_back_and_reconfigures(
    tmp_path: Path,
) -> None:
    planner, source, target, declaration = relocation_planner(tmp_path)
    plan = planner.plan("example.pl")
    declaration_content = declaration.read_bytes()
    calls = 0

    def activate(_zone: str) -> ManagedZoneMigrationStep:
        nonlocal calls
        calls += 1
        return ManagedZoneMigrationStep("rndc-reconfig", True, "OK")

    result = ManagedZoneRelocationTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=planner.root_config,
        zone_validator=_ok("named-checkzone"),
        config_validator=_ok("named-checkconf"),
        activator=activate,
        loaded_verifier=lambda *_args: ManagedZoneMigrationStep(
            "rndc-zonestatus", False, "wrong path"
        ),
    ).apply(plan, commit=True, activate=True)

    assert result.status == "ROLLED-BACK"
    assert calls == 2
    assert source.exists() and not target.exists()
    assert declaration.read_bytes() == declaration_content


def test_relocation_failed_rollback_is_reported(tmp_path: Path) -> None:
    planner, source, target, declaration = relocation_planner(tmp_path)
    plan = planner.plan("example.pl")
    result = ManagedZoneRelocationTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=planner.root_config,
        zone_validator=_ok("named-checkzone"),
        config_validator=_ok("named-checkconf"),
        activator=lambda _zone: ManagedZoneMigrationStep(
            "rndc-reconfig", False, "BIND unavailable"
        ),
        loaded_verifier=_ok("rndc-zonestatus"),
    ).apply(plan, commit=True, activate=True)

    assert result.status == "ROLLBACK-FAILED"
    assert result.rolled_back is False
    assert source.exists() and not target.exists()
    assert declaration.read_text(encoding="utf-8") == plan.declaration_original
