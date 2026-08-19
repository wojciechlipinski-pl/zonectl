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
    mode = root.stat().st_mode & 0o777
    result = BindAclTransaction(
        tmp_path / "backups", tmp_path / "manifests",
        root_config=root, config_validator=_ok("named-checkconf"),
        activator=_ok("rndc-reconfig"),
    ).apply(plan, commit=True, activate=True)
    assert result.status == "COMMIT"
    assert root.read_text() == plan.candidate_text
    assert root.stat().st_mode & 0o777 == mode
    assert Path(result.backup).is_file()
    assert Path(result.manifest).is_file()


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


def test_changed_file_is_rejected(tmp_path: Path) -> None:
    plan, root = _plan(tmp_path)
    root.write_text(plan.original_text + "# changed\n")
    result = BindAclTransaction(
        tmp_path / "backups", tmp_path / "manifests", root_config=root
    ).apply(plan, commit=True, activate=True)
    assert result.status == "CONFLICT"
