"""Isolated transaction drills using the real BIND configuration validator."""

from pathlib import Path
import shutil

import pytest

from zonectl.core.bind_acl_plan import BindAclPlanner
from zonectl.core.bind_acl_transaction import BindAclStep, BindAclTransaction
from zonectl.core.bind_secondary_plan import BindSecondaryPlanner
from zonectl.core.bind_secondary_transaction import (
    BindSecondaryStep,
    BindSecondaryTransaction,
)


pytestmark = pytest.mark.skipif(
    shutil.which("named-checkconf") is None,
    reason="Brak named-checkconf — izolowany drill wymaga BIND utils",
)


def test_acl_real_validation_and_forced_post_gate_rollback(tmp_path: Path) -> None:
    root = tmp_path / "named.conf"
    options = tmp_path / "named.conf.options"
    root.write_text(f'include "{options}";\n', encoding="utf-8")
    options.write_text(
        'acl "maintenance" { localhost; 192.0.2.0/24; };\n'
        'options { recursion no; allow-query { maintenance; }; };\n',
        encoding="utf-8",
    )
    before = options.read_bytes()
    plan = BindAclPlanner(root).plan(
        "maintenance", entries=["localhost", "198.51.100.0/24"]
    )
    calls = 0

    def simulated_reconfig() -> BindAclStep:
        nonlocal calls
        calls += 1
        return BindAclStep("rndc-reconfig", True, "symulacja izolowana")

    result = BindAclTransaction(
        tmp_path / "backups", tmp_path / "manifests",
        root_config=root, activator=simulated_reconfig,
        post_validator=lambda _plan: BindAclStep(
            "post-config-state", False, "wymuszona awaria drillu"
        ),
    ).apply(
        plan, commit=True, activate=True,
        reason="izolowany drill ACL",
    )

    assert plan.validation_ok is True
    assert result.status == "ROLLED-BACK"
    assert result.rolled_back is True
    assert calls == 2
    assert options.read_bytes() == before
    assert Path(result.backup).is_file()
    assert Path(result.manifest).is_file()


def test_secondary_real_validation_and_forced_operational_rollback(
    tmp_path: Path,
) -> None:
    root = tmp_path / "named.conf"
    root.write_text(
        'primaries lab-notify { 192.0.2.53; };\n'
        'zone "integration.example" { type primary; file "integration.db"; '
        'also-notify { lab-notify; }; };\n',
        encoding="utf-8",
    )
    before = root.read_bytes()
    plan = BindSecondaryPlanner(root).plan("lab-notify", ["198.51.100.53"])
    calls = 0

    def simulated_reconfig() -> BindSecondaryStep:
        nonlocal calls
        calls += 1
        return BindSecondaryStep("rndc-reconfig", True, "symulacja izolowana")

    result = BindSecondaryTransaction(
        tmp_path / "backups", tmp_path / "manifests",
        root_config=root, activator=simulated_reconfig,
        post_validator=lambda _plan: BindSecondaryStep(
            "post-config-state", True, "stan kandydata poprawny"
        ),
        operational_validator=lambda _plan: BindSecondaryStep(
            "secondary-operational", False, "wymuszona awaria drillu"
        ),
    ).apply(
        plan, commit=True, activate=True,
        reason="izolowany drill secondary",
    )

    assert plan.validation_ok is True
    assert result.status == "ROLLED-BACK"
    assert result.rolled_back is True
    assert calls == 2
    assert root.read_bytes() == before
    assert Path(result.backup).is_file()
    assert Path(result.manifest).is_file()
