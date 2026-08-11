from pathlib import Path

from zonectl.core.managed_zone_migration import ManagedZoneMigrationPlanner
from zonectl.core.managed_zone_migration_transaction import (
    ManagedZoneMigrationStep,
    ManagedZoneMigrationTransaction,
)


def _plan(tmp_path: Path):
    bind = tmp_path / "bind"
    managed = bind / "zonectl-zones.d"
    managed.mkdir(parents=True)
    root = bind / "named.conf"
    local = bind / "named.conf.local"
    index = bind / "zonectl-zones.conf"
    root.write_text('include "named.conf.local";\n', encoding="utf-8")
    local.write_text(
        'include "zonectl-zones.conf";\n'
        'zone "example.pl" { type primary; file "/zones/example.pl"; };\n',
        encoding="utf-8",
    )
    index.write_text("# index\n", encoding="utf-8")
    planner = ManagedZoneMigrationPlanner(
        root_config=root,
        local_config=local,
        managed_config=index,
        managed_zone_directory=managed,
    )
    return planner.plan("example.pl"), root


def _ok(name: str):
    return lambda *_args: ManagedZoneMigrationStep(name, True, "OK")


def test_dry_run_has_no_side_effects(tmp_path: Path) -> None:
    plan, root = _plan(tmp_path)
    transaction = ManagedZoneMigrationTransaction(
        tmp_path / "backups", tmp_path / "manifests", root_config=root
    )

    result = transaction.apply(plan)

    assert result.status == "DRY-RUN"
    assert plan.source_config.read_text() == plan.source_original
    assert plan.managed_config.read_text() == plan.managed_original
    assert not plan.declaration_file.exists()
    assert not (tmp_path / "backups").exists()


def test_commit_migrates_and_preserves_zone_availability(tmp_path: Path) -> None:
    plan, root = _plan(tmp_path)
    transaction = ManagedZoneMigrationTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=root,
        config_validator=_ok("named-checkconf"),
        activator=_ok("rndc-reconfig"),
        loaded_verifier=_ok("rndc-zonestatus"),
    )

    result = transaction.apply(plan, commit=True, activate=True)

    assert result.status == "COMMIT"
    assert result.committed is True
    assert plan.source_config.read_text() == plan.source_candidate
    assert plan.managed_config.read_text() == plan.managed_candidate
    assert plan.declaration_file.read_text() == plan.declaration_text
    assert Path(result.backup_directory).is_dir()
    assert Path(result.manifest).is_file()


def test_validation_failure_rolls_back_all_files(tmp_path: Path) -> None:
    plan, root = _plan(tmp_path)
    transaction = ManagedZoneMigrationTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=root,
        config_validator=lambda *_: ManagedZoneMigrationStep(
            "named-checkconf", False, "invalid"
        ),
    )

    result = transaction.apply(plan, commit=True)

    assert result.status == "ROLLED-BACK"
    assert result.rolled_back is True
    assert plan.source_config.read_text() == plan.source_original
    assert plan.managed_config.read_text() == plan.managed_original
    assert not plan.declaration_file.exists()


def test_changed_source_is_rejected_before_writes(tmp_path: Path) -> None:
    plan, root = _plan(tmp_path)
    plan.source_config.write_text(plan.source_original + "# changed\n")
    transaction = ManagedZoneMigrationTransaction(
        tmp_path / "backups", tmp_path / "manifests", root_config=root
    )

    result = transaction.apply(plan, commit=True, activate=True)

    assert result.status == "CONFLICT"
    assert not plan.declaration_file.exists()
