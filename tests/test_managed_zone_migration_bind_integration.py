from dataclasses import replace
from pathlib import Path
import shutil

import pytest

from zonectl.core.managed_zone_migration import ManagedZoneMigrationPlanner
from zonectl.core.managed_zone_migration_transaction import (
    ManagedZoneMigrationStep,
    ManagedZoneMigrationTransaction,
)


pytestmark = pytest.mark.skipif(
    shutil.which("named-checkconf") is None,
    reason="Brak named-checkconf",
)


def _isolated(tmp_path: Path):
    bind = tmp_path / "bind"
    declarations = bind / "zonectl-zones.d"
    declarations.mkdir(parents=True)
    root = bind / "named.conf"
    local = bind / "named.conf.local"
    index = bind / "zonectl-zones.conf"
    root.write_text(f'include "{local}";\n', encoding="utf-8")
    local.write_text(
        f'include "{index}";\n'
        'zone "migration.invalid" {\n'
        "    type primary;\n"
        f'    file "{tmp_path / "migration.invalid"}";\n'
        "};\n",
        encoding="utf-8",
    )
    index.write_text("# managed zones\n", encoding="utf-8")
    planner = ManagedZoneMigrationPlanner(
        root_config=root,
        local_config=local,
        managed_config=index,
        managed_zone_directory=declarations,
    )
    transaction = ManagedZoneMigrationTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=root,
        activator=lambda _zone: ManagedZoneMigrationStep(
            "rndc-reconfig", True, "izolacja"
        ),
        loaded_verifier=lambda _zone: ManagedZoneMigrationStep(
            "rndc-zonestatus", True, "izolacja"
        ),
    )
    return planner.plan("migration.invalid"), transaction


def test_real_named_checkconf_accepts_migrated_declaration(tmp_path: Path) -> None:
    plan, transaction = _isolated(tmp_path)

    result = transaction.apply(plan, commit=True, activate=True)

    assert result.status == "COMMIT"
    assert plan.declaration_file.is_file()
    assert any(step.name == "named-checkconf" and step.ok for step in result.steps)


def test_real_named_checkconf_failure_restores_every_file(tmp_path: Path) -> None:
    plan, transaction = _isolated(tmp_path)
    broken = replace(
        plan,
        declaration_text=plan.declaration_text.replace("type primary;", "type ;"),
    )

    result = transaction.apply(broken, commit=True)

    assert result.status == "ROLLED-BACK"
    assert plan.source_config.read_text() == plan.source_original
    assert plan.managed_config.read_text() == plan.managed_original
    assert not plan.declaration_file.exists()
