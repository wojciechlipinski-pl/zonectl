import json
from pathlib import Path

from zonectl.core.bind_acl_plan import BindAclPlanner
from zonectl.core.bind_acl_transaction import (
    BindAclStep,
    BindAclTransaction,
)


def _plan(tmp_path: Path):
    root = tmp_path / "named.conf"
    root.write_text(
        'acl "trusted" {\n  198.51.100/24;\n  203.0.113.0/24;\n'
        '  203.0.113.0/24;\n};\noptions { allow-query { trusted; }; };\n',
        encoding="utf-8",
    )
    planner = BindAclPlanner(root)
    planner._validate_candidate = lambda source, candidate: (True, "kod 0")
    return planner.plan(
        "trusted", replacements={"198.51.100/24": "198.51.100.0/24"}
    ), root


def _ok(name: str):
    return lambda *_args: BindAclStep(name, True, "OK")


def test_dry_run_has_no_side_effects(tmp_path: Path) -> None:
    plan, root = _plan(tmp_path)
    before = root.read_bytes()
    result = BindAclTransaction(
        tmp_path / "backups", tmp_path / "manifests", root_config=root
    ).apply(plan)
    assert result.status == "DRY-RUN"
    assert root.read_bytes() == before
    assert not (tmp_path / "backups").exists()


def test_commit_preserves_metadata_and_writes_manifest(tmp_path: Path) -> None:
    plan, root = _plan(tmp_path)
    root.chmod(0o640)
    metadata_before = root.stat()
    result = BindAclTransaction(
        tmp_path / "backups", tmp_path / "manifests",
        root_config=root, config_validator=_ok("named-checkconf"),
        activator=_ok("rndc-reconfig"),
    ).apply(plan, commit=True, activate=True, reason="kontrolowana zmiana ACL")
    assert result.status == "COMMIT"
    assert root.read_text() == plan.candidate_text
    metadata_after = root.stat()
    assert metadata_after.st_mode & 0o777 == 0o640
    assert metadata_after.st_uid == metadata_before.st_uid
    assert metadata_after.st_gid == metadata_before.st_gid
    assert Path(result.backup).is_file()
    assert Path(result.manifest).is_file()
    manifest = json.loads(Path(result.manifest).read_text(encoding="utf-8"))
    assert manifest["operator"]
    assert manifest["reason"] == "kontrolowana zmiana ACL"
    assert manifest["risk"] == plan.impact.risk
    assert manifest["roles"] == list(plan.impact.roles)
    assert manifest["zones"] == list(plan.impact.zones)
    assert manifest["state_before"]["sha256"] != manifest["state_after"]["sha256"]
    assert manifest["state_before"]["entries"] == list(plan.impact.current_entries)
    assert manifest["state_after"]["entries"] == list(plan.impact.candidate_entries)
    for field in ("uid", "gid", "mode"):
        assert manifest["state_before"][field] == manifest["state_after"][field]
    assert manifest["state_after"]["mode"] == "0640"


def test_validation_failure_rolls_back(tmp_path: Path) -> None:
    plan, root = _plan(tmp_path)
    result = BindAclTransaction(
        tmp_path / "backups", tmp_path / "manifests",
        root_config=root,
        config_validator=lambda *_: BindAclStep("named-checkconf", False, "invalid"),
    ).apply(plan, commit=True)
    assert result.status == "ROLLED-BACK"
    assert result.rolled_back is True
    assert root.read_text() == plan.original_text


def test_activation_failure_rolls_back_and_records_final_manifest(
    tmp_path: Path,
) -> None:
    plan, root = _plan(tmp_path)
    calls = 0

    def activate() -> BindAclStep:
        nonlocal calls
        calls += 1
        return BindAclStep(
            "rndc-reconfig", calls > 1, "OK" if calls > 1 else "failure"
        )

    result = BindAclTransaction(
        tmp_path / "backups", tmp_path / "manifests",
        root_config=root, config_validator=_ok("named-checkconf"),
        activator=activate,
    ).apply(plan, commit=True, activate=True, reason="test awarii aktywacji")

    assert result.status == "ROLLED-BACK"
    assert calls == 2
    assert root.read_text() == plan.original_text
    manifest = json.loads(Path(result.manifest).read_text(encoding="utf-8"))
    assert manifest["status"] == "ROLLED-BACK"
    assert manifest["rolled_back"] is True
    assert manifest["state_before"] == manifest["state_after"]


def test_changed_file_is_rejected(tmp_path: Path) -> None:
    plan, root = _plan(tmp_path)
    root.write_text(plan.original_text + "# changed\n")
    result = BindAclTransaction(
        tmp_path / "backups", tmp_path / "manifests", root_config=root
    ).apply(plan, commit=True, activate=True)
    assert result.status == "CONFLICT"


def test_high_risk_commit_is_blocked_before_backup(tmp_path: Path) -> None:
    root = tmp_path / "named.conf"
    root.write_text(
        'acl "trusted" {\n  localhost;\n  192.0.2.0/24;\n};\n'
        'options { allow-recursion { trusted; }; };\n',
        encoding="utf-8",
    )
    planner = BindAclPlanner(root)
    planner._validate_candidate = lambda source, candidate: (True, "kod 0")
    plan = planner.plan("trusted", entries=["localhost"])
    before = root.read_bytes()

    dry_run = BindAclTransaction(
        tmp_path / "backups", tmp_path / "manifests", root_config=root
    ).apply(plan)
    blocked = BindAclTransaction(
        tmp_path / "backups", tmp_path / "manifests", root_config=root
    ).apply(plan, commit=True, activate=True)

    assert plan.impact is not None and plan.impact.risk == "HIGH"
    assert dry_run.status == "DRY-RUN"
    assert blocked.status == "BLOCKED"
    assert blocked.steps[0].name == "impact-gate"
    assert "przed backupem" in blocked.steps[0].message
    assert "recursion" in blocked.steps[0].message
    assert root.read_bytes() == before
    assert not (tmp_path / "backups").exists()


def test_active_transfer_acl_cannot_be_replaced_with_none(tmp_path: Path) -> None:
    root = tmp_path / "named.conf"
    root.write_text(
        'acl "zone-transfer" { 192.0.2.53; };\n'
        'zone "example.invalid" { type primary; file "/zone"; '
        'allow-transfer { zone-transfer; }; };\n',
        encoding="utf-8",
    )
    planner = BindAclPlanner(root)
    planner._validate_candidate = lambda source, candidate: (True, "kod 0")
    plan = planner.plan("zone-transfer", entries=["none"])
    before = root.read_bytes()

    result = BindAclTransaction(
        tmp_path / "backups", tmp_path / "manifests", root_config=root
    ).apply(
        plan, commit=True, activate=True,
        reason="próba opróżnienia aktywnego transferu",
    )

    assert plan.impact is not None and plan.impact.risk == "HIGH"
    assert result.status == "BLOCKED"
    assert "transfer" in result.steps[0].message
    assert root.read_bytes() == before
    assert not (tmp_path / "backups").exists()


def test_post_config_gate_failure_rolls_back_and_verifies_restored_state(
    tmp_path: Path,
) -> None:
    plan, root = _plan(tmp_path)
    root.chmod(0o640)
    metadata_before = root.stat()
    calls = 0

    def activate() -> BindAclStep:
        nonlocal calls
        calls += 1
        return BindAclStep("rndc-reconfig", True, "OK")

    result = BindAclTransaction(
        tmp_path / "backups", tmp_path / "manifests",
        root_config=root, config_validator=_ok("named-checkconf"),
        activator=activate,
        post_validator=lambda _plan: BindAclStep(
            "post-config-state", False, "stan ACL niezgodny"
        ),
    ).apply(plan, commit=True, activate=True)

    assert result.status == "ROLLED-BACK"
    assert result.rolled_back is True
    assert calls == 2
    assert root.read_text() == plan.original_text
    metadata_after = root.stat()
    assert metadata_after.st_mode & 0o777 == 0o640
    assert metadata_after.st_uid == metadata_before.st_uid
    assert metadata_after.st_gid == metadata_before.st_gid
    assert any(step.name == "post-rollback-state" and step.ok for step in result.steps)


def test_failed_rollback_activation_is_reported_as_rollback_failed(
    tmp_path: Path,
) -> None:
    plan, root = _plan(tmp_path)

    result = BindAclTransaction(
        tmp_path / "backups", tmp_path / "manifests",
        root_config=root, config_validator=_ok("named-checkconf"),
        activator=lambda: BindAclStep("rndc-reconfig", False, "failure"),
    ).apply(plan, commit=True, activate=True, reason="test rollbacku")

    assert result.status == "ROLLBACK-FAILED"
    assert result.rolled_back is False
    assert root.read_text() == plan.original_text
    assert any(
        step.name == "rndc-reconfig-rollback" and not step.ok
        for step in result.steps
    )
