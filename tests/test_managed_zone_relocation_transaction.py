from pathlib import Path

from zonectl.core.managed_zone_migration_transaction import ManagedZoneMigrationStep
from zonectl.core.managed_zone_relocation_transaction import ManagedZoneRelocationTransaction
from test_managed_zone_relocation import _planner


def _ok(name):
    return lambda *_args: ManagedZoneMigrationStep(name, True, "OK")


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    planner, source, target, declaration = _planner(tmp_path)
    plan = planner.plan("example.pl")
    original = declaration.read_text()
    tx = ManagedZoneRelocationTransaction(
        tmp_path / "backups", tmp_path / "manifests",
        root_config=planner.root_config, zone_validator=_ok("named-checkzone"),
    )

    result = tx.apply(plan)

    assert result.status == "DRY-RUN"
    assert source.exists() and not target.exists()
    assert declaration.read_text() == original


def test_commit_relocates_source_and_updates_declaration(tmp_path: Path) -> None:
    planner, source, target, declaration = _planner(tmp_path)
    plan = planner.plan("example.pl")
    content = source.read_bytes()
    tx = ManagedZoneRelocationTransaction(
        tmp_path / "backups", tmp_path / "manifests",
        root_config=planner.root_config,
        zone_validator=_ok("named-checkzone"),
        config_validator=_ok("named-checkconf"),
        activator=_ok("rndc-reconfig"),
        loaded_verifier=_ok("rndc-zonestatus"),
    )

    result = tx.apply(plan, commit=True, activate=True)

    assert result.status == "COMMIT"
    assert not source.exists()
    assert target.read_bytes() == content
    assert str(target) in declaration.read_text()
    assert Path(result.backup_directory).is_dir()
    assert Path(result.manifest).is_file()


def test_failed_activation_restores_source_and_declaration(tmp_path: Path) -> None:
    planner, source, target, declaration = _planner(tmp_path)
    plan = planner.plan("example.pl")
    original = declaration.read_text()
    tx = ManagedZoneRelocationTransaction(
        tmp_path / "backups", tmp_path / "manifests",
        root_config=planner.root_config,
        zone_validator=_ok("named-checkzone"),
        config_validator=_ok("named-checkconf"),
        activator=lambda *_: ManagedZoneMigrationStep("rndc-reconfig", False, "failed"),
    )

    result = tx.apply(plan, commit=True, activate=True)

    assert result.status == "ROLLBACK-FAILED"
    assert source.exists() and not target.exists()
    assert declaration.read_text() == original
