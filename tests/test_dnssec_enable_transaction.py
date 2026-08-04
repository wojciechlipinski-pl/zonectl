from __future__ import annotations

import os
from pathlib import Path

import pytest
import zonectl.core.dnssec_enable_transaction as transaction_module
from zonectl.core.discovery import ZoneConfig
from zonectl.core.dnssec_enable_plan import DnssecEnablePlanner
from zonectl.core.dnssec_enable_transaction import (
    DnssecEnableStep,
    DnssecEnableTransaction,
)
from zonectl.core.runner import CommandResult


def setup_plan(tmp_path: Path):
    source = tmp_path / "etc" / "example.pl"
    source.parent.mkdir(parents=True)
    source.write_text("$TTL 3600\n", encoding="utf-8")
    declaration = tmp_path / "named.conf.local"
    declaration.write_text(
        'zone "example.pl" {\n'
        "    type primary;\n"
        f'    file "{source}";\n'
        "};\n",
        encoding="utf-8",
    )
    target_dir = tmp_path / "var" / "Primary"
    target_dir.mkdir(parents=True)
    keys = tmp_path / "keys"
    zone = ZoneConfig(
        name="example.pl",
        zone_type="primary",
        source_file=source,
        config_file=declaration,
        source_exists=True,
        source_writable=True,
    )
    plan = DnssecEnablePlanner().plan(
        zone,
        key_directory=keys,
        zone_directory=target_dir,
    )
    return plan, declaration, source


def ok(name: str):
    return lambda *_args: DnssecEnableStep(name, True, "OK")


def engine(tmp_path: Path, **overrides):
    defaults = {
        "zone_validator": ok("named-checkzone"),
        "config_validator": ok("named-checkconf"),
        "activator": ok("rndc-reconfig"),
        "loaded_verifier": ok("rndc-zonestatus"),
        "dnssec_verifier": ok("dnssec-status"),
    }
    defaults.update(overrides)
    return DnssecEnableTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=tmp_path / "named.conf",
        **defaults,
    )


def test_dry_run_has_no_side_effects(tmp_path: Path) -> None:
    plan, declaration, source = setup_plan(tmp_path)
    before = declaration.read_bytes()

    result = engine(tmp_path).apply(plan)

    assert result.status == "DRY-RUN"
    assert declaration.read_bytes() == before
    assert source.exists()
    assert not plan.target_zone_file.exists()
    assert not (tmp_path / "backups").exists()


def test_commit_creates_backups_target_manifest_and_configuration(tmp_path: Path) -> None:
    plan, declaration, source = setup_plan(tmp_path)

    result = engine(tmp_path).apply(plan, commit=True, activate=True)

    assert result.status == "COMMIT"
    assert result.committed is True
    assert plan.target_zone_file.read_bytes() == source.read_bytes()
    assert "dnssec-policy default;" in declaration.read_text(encoding="utf-8")
    assert Path(result.manifest).is_file()
    backup = Path(result.backup_directory)
    assert (backup / "bind-declaration.conf").is_file()
    assert (backup / "zone-source.db").is_file()


def test_validation_failure_restores_configuration_and_removes_target(tmp_path: Path) -> None:
    plan, declaration, source = setup_plan(tmp_path)
    before = declaration.read_bytes()
    bad = lambda *_args: DnssecEnableStep("named-checkconf", False, "invalid")

    result = engine(tmp_path, config_validator=bad).apply(plan, commit=True)

    assert result.status == "ROLLED-BACK"
    assert result.rolled_back is True
    assert declaration.read_bytes() == before
    assert source.exists()
    assert not plan.target_zone_file.exists()


@pytest.mark.skipif(os.name == "nt", reason="Test metadanych POSIX")
def test_rollback_preserves_original_configuration_owner(
    tmp_path: Path,
) -> None:
    plan, declaration, _source = setup_plan(tmp_path)
    original = declaration.stat()
    test_gid = original.st_gid + 1000
    os.chown(declaration, original.st_uid, test_gid)
    bad = lambda *_args: DnssecEnableStep("named-checkconf", False, "invalid")

    result = engine(tmp_path, config_validator=bad).apply(plan, commit=True)

    assert result.status == "ROLLED-BACK"
    restored = declaration.stat()
    assert restored.st_uid == original.st_uid
    assert restored.st_gid == test_gid
    backup = Path(result.backup_directory) / "bind-declaration.conf"
    assert backup.stat().st_gid == test_gid


def test_activation_failure_removes_new_bind_artifacts(tmp_path: Path) -> None:
    plan, declaration, _source = setup_plan(tmp_path)
    before = declaration.read_bytes()

    calls = 0

    def fail_after_creating_artifacts(_zone: str) -> DnssecEnableStep:
        nonlocal calls
        calls += 1
        if calls == 1:
            plan.target_zone_file.with_suffix(".pl.signed").write_text("signed")
            plan.key_directory.mkdir(exist_ok=True)
            (plan.key_directory / "Kexample.pl.+013+12345.key").write_text("key")
            return DnssecEnableStep("rndc-reconfig", False, "failed")
        return DnssecEnableStep("rndc-reconfig", True, "restored")

    result = engine(tmp_path, activator=fail_after_creating_artifacts).apply(
        plan,
        commit=True,
        activate=True,
    )

    assert result.status == "ROLLED-BACK"
    assert declaration.read_bytes() == before
    assert not plan.target_zone_file.exists()
    assert not list(plan.target_zone_file.parent.glob("example.pl.*"))
    assert not list(plan.key_directory.glob("Kexample.pl.*"))


def test_existing_signing_artifact_is_rejected(tmp_path: Path) -> None:
    plan, _declaration, _source = setup_plan(tmp_path)
    plan.target_zone_file.with_suffix(".pl.jnl").write_text("old")

    result = engine(tmp_path).apply(plan, commit=True)

    assert result.status == "CONFLICT"
    assert not (tmp_path / "backups").exists()


def test_default_activation_uses_expected_rndc_sequence(
    monkeypatch, tmp_path: Path
) -> None:
    plan, _declaration, _source = setup_plan(tmp_path)
    commands: list[list[str]] = []

    def fake_run(command: list[str], _timeout: int) -> CommandResult:
        commands.append(command)
        if command[:3] == ["rndc", "dnssec", "-status"]:
            return CommandResult(0, "zone signing: yes\n", "")
        return CommandResult(0, "OK\n", "")

    monkeypatch.setattr(transaction_module, "run", fake_run)
    transaction = DnssecEnableTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=tmp_path / "named.conf",
    )

    result = transaction.apply(plan, commit=True, activate=True)

    assert result.status == "COMMIT"
    assert ["rndc", "reconfig"] in commands
    assert ["rndc", "zonestatus", "example.pl"] in commands
    assert ["rndc", "dnssec", "-status", "example.pl"] in commands


def test_failed_fake_dnssec_status_rolls_back(monkeypatch, tmp_path: Path) -> None:
    plan, declaration, _source = setup_plan(tmp_path)
    original = declaration.read_bytes()
    reconfig_calls = 0

    def fake_run(command: list[str], _timeout: int) -> CommandResult:
        nonlocal reconfig_calls
        if command == ["rndc", "reconfig"]:
            reconfig_calls += 1
            return CommandResult(0, "OK\n", "")
        if command[:3] == ["rndc", "dnssec", "-status"]:
            return CommandResult(1, "", "not ready")
        return CommandResult(0, "OK\n", "")

    monkeypatch.setattr(transaction_module, "run", fake_run)
    transaction = DnssecEnableTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=tmp_path / "named.conf",
    )

    result = transaction.apply(plan, commit=True, activate=True)

    assert result.status == "ROLLED-BACK"
    assert reconfig_calls == 2
    assert declaration.read_bytes() == original
    assert not plan.target_zone_file.exists()


def test_changed_declaration_is_rejected_before_writes(tmp_path: Path) -> None:
    plan, declaration, _source = setup_plan(tmp_path)
    declaration.write_text(declaration.read_text() + "// changed\n")

    result = engine(tmp_path).apply(plan, commit=True)

    assert result.status == "CONFLICT"
    assert not plan.target_zone_file.exists()
    assert not (tmp_path / "backups").exists()
