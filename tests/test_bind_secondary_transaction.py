import json
from dataclasses import replace
from pathlib import Path

from zonectl.core.bind_secondary_plan import BindSecondaryPlanner
from zonectl.core.bind_secondary_transaction import (
    BindSecondaryStep,
    BindSecondaryTransaction,
)


def _plan(tmp_path: Path):
    root = tmp_path / "named.conf"
    root.write_text(
        'primaries dns2-notify { 192.0.2.53; };\n'
        'zone "a" { type primary; file "/a"; '
        'also-notify { dns2-notify; }; };\n', encoding="utf-8"
    )
    planner = BindSecondaryPlanner(root)
    planner._validate_candidate = lambda source, candidate: (True, "kod 0")
    return planner.plan("dns2-notify", ["192.0.2.60"]), root


def _ok(name: str):
    return lambda *_args: BindSecondaryStep(name, True, "OK")


def test_dry_run_has_no_side_effects(tmp_path: Path) -> None:
    plan, root = _plan(tmp_path)
    before = root.read_bytes()
    result = BindSecondaryTransaction(
        tmp_path / "backups", tmp_path / "manifests", root_config=root
    ).apply(plan)
    assert result.status == "DRY-RUN"
    assert result.zones == ("a",)
    assert root.read_bytes() == before


def test_commit_writes_backup_manifest_and_audit_context(tmp_path: Path) -> None:
    plan, root = _plan(tmp_path)
    result = BindSecondaryTransaction(
        tmp_path / "backups", tmp_path / "manifests", root_config=root,
        config_validator=_ok("named-checkconf"), activator=_ok("rndc-reconfig"),
        operational_validator=_ok("secondary-operational"),
    ).apply(
        plan, commit=True, activate=True,
        reason="planowana zmiana adresu secondary",
    )
    assert result.status == "COMMIT"
    assert result.old_addresses == ("192.0.2.53",)
    assert result.new_addresses == ("192.0.2.60",)
    assert root.read_text() == plan.candidate_text
    assert Path(result.backup).is_file()
    assert Path(result.manifest).is_file()
    manifest = json.loads(Path(result.manifest).read_text(encoding="utf-8"))
    assert manifest["roles"] == ["notify"]
    assert manifest["old_addresses"] == ["192.0.2.53"]
    assert manifest["new_addresses"] == ["192.0.2.60"]
    assert manifest["zones"] == ["a"]
    assert manifest["operator"]
    assert manifest["reason"] == "planowana zmiana adresu secondary"
    assert manifest["risk"] == plan.impact.risk
    assert manifest["state_before"]["sha256"] != manifest["state_after"]["sha256"]
    assert manifest["state_before"]["entries"] == ["192.0.2.53"]
    assert manifest["state_after"]["entries"] == ["192.0.2.60"]


def test_validation_failure_rolls_back(tmp_path: Path) -> None:
    plan, root = _plan(tmp_path)
    result = BindSecondaryTransaction(
        tmp_path / "backups", tmp_path / "manifests", root_config=root,
        config_validator=lambda *_: BindSecondaryStep("named-checkconf", False, "invalid"),
    ).apply(plan, commit=True)
    assert result.status == "ROLLED-BACK"
    assert result.rolled_back is True
    assert root.read_text() == plan.original_text


def test_activation_failure_restores_configuration_and_reconfigures(
    tmp_path: Path,
) -> None:
    plan, root = _plan(tmp_path)
    calls = 0

    def activator() -> BindSecondaryStep:
        nonlocal calls
        calls += 1
        return BindSecondaryStep(
            "rndc-reconfig", calls > 1, "OK" if calls > 1 else "failure"
        )

    result = BindSecondaryTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=root,
        config_validator=_ok("named-checkconf"),
        activator=activator,
    ).apply(plan, commit=True, activate=True)

    assert result.status == "ROLLED-BACK"
    assert calls == 2
    assert root.read_text() == plan.original_text


def test_changed_file_is_rejected_before_backup(tmp_path: Path) -> None:
    plan, root = _plan(tmp_path)
    root.write_text(plan.original_text + "# changed\n")
    result = BindSecondaryTransaction(
        tmp_path / "backups", tmp_path / "manifests", root_config=root
    ).apply(plan, commit=True, activate=True)
    assert result.status == "CONFLICT"
    assert not (tmp_path / "backups").exists()


def test_high_risk_secondary_commit_is_blocked_before_backup(
    tmp_path: Path,
) -> None:
    plan, root = _plan(tmp_path)
    assert plan.impact is not None
    high = replace(plan, impact=replace(plan.impact, risk="HIGH"))
    before = root.read_bytes()

    dry_run = BindSecondaryTransaction(
        tmp_path / "backups", tmp_path / "manifests", root_config=root
    ).apply(high)
    blocked = BindSecondaryTransaction(
        tmp_path / "backups", tmp_path / "manifests", root_config=root
    ).apply(high, commit=True, activate=True)

    assert dry_run.status == "DRY-RUN"
    assert blocked.status == "BLOCKED"
    assert blocked.steps[0].name == "impact-gate"
    assert root.read_bytes() == before
    assert not (tmp_path / "backups").exists()


def test_post_config_gate_failure_rolls_back_secondary_and_rechecks_state(
    tmp_path: Path,
) -> None:
    plan, root = _plan(tmp_path)
    calls = 0

    def activate() -> BindSecondaryStep:
        nonlocal calls
        calls += 1
        return BindSecondaryStep("rndc-reconfig", True, "OK")

    result = BindSecondaryTransaction(
        tmp_path / "backups", tmp_path / "manifests",
        root_config=root, config_validator=_ok("named-checkconf"),
        activator=activate,
        post_validator=lambda _plan: BindSecondaryStep(
            "post-config-state", False, "stan secondary niezgodny"
        ),
    ).apply(plan, commit=True, activate=True)

    assert result.status == "ROLLED-BACK"
    assert result.rolled_back is True
    assert calls == 2
    assert root.read_text() == plan.original_text
    assert any(step.name == "post-rollback-state" and step.ok for step in result.steps)


def test_operational_gate_failure_rolls_back_and_records_final_manifest(
    tmp_path: Path,
) -> None:
    plan, root = _plan(tmp_path)
    calls = 0

    def activate() -> BindSecondaryStep:
        nonlocal calls
        calls += 1
        return BindSecondaryStep("rndc-reconfig", True, "OK")

    result = BindSecondaryTransaction(
        tmp_path / "backups", tmp_path / "manifests",
        root_config=root, config_validator=_ok("named-checkconf"),
        activator=activate, post_validator=_ok("post-config-state"),
        operational_validator=lambda _plan: BindSecondaryStep(
            "secondary-operational", False, "brak AA"
        ),
    ).apply(
        plan, commit=True, activate=True,
        reason="test awarii bramki operacyjnej",
    )

    assert result.status == "ROLLED-BACK"
    assert calls == 2
    assert root.read_text() == plan.original_text
    manifest = json.loads(Path(result.manifest).read_text(encoding="utf-8"))
    assert manifest["status"] == "ROLLED-BACK"
    assert manifest["rolled_back"] is True
    assert manifest["state_before"] == manifest["state_after"]
    assert any(
        step["name"] == "secondary-operational" and not step["ok"]
        for step in manifest["steps"]
    )


def test_failed_secondary_rollback_activation_is_reported(
    tmp_path: Path,
) -> None:
    plan, root = _plan(tmp_path)

    result = BindSecondaryTransaction(
        tmp_path / "backups", tmp_path / "manifests",
        root_config=root, config_validator=_ok("named-checkconf"),
        activator=lambda: BindSecondaryStep("rndc-reconfig", False, "failure"),
    ).apply(
        plan, commit=True, activate=True,
        reason="test nieudanego rollbacku",
    )

    assert result.status == "ROLLBACK-FAILED"
    assert result.rolled_back is False
    assert root.read_text() == plan.original_text
    assert any(
        step.name == "rndc-reconfig-rollback" and not step.ok
        for step in result.steps
    )
