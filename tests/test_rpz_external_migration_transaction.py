import hashlib
from pathlib import Path

from zonectl.core.rpz_external_migration_plan import (
    RpzExternalMigrationPlan,
    RpzMigrationArtifact,
)
from zonectl.core.rpz_external_migration_transaction import (
    RpzExternalMigrationTransaction,
)
from zonectl.core.runner import CommandResult


def _plan(tmp_path: Path) -> RpzExternalMigrationPlan:
    external = tmp_path / "external"
    external.mkdir()
    files = {
        "zone-file": "$ORIGIN cert-rpz.local.\n",
        "updater": "#!/bin/bash\nexit 0\n",
        "service-unit": "[Service]\nExecStart=UPDATER\n",
        "timer-unit": "[Timer]\nOnCalendar=*:0/5\n",
    }
    updater = external / "updater"
    artifacts = []
    for role, content in files.items():
        path = external / role
        path.write_text(content.replace("UPDATER", str(updater)), encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        artifacts.append(
            RpzMigrationArtifact(
                role,
                path,
                True,
                path.stat().st_uid,
                path.stat().st_gid,
                "-rw-r--r--",
                digest,
            )
        )
    managed = tmp_path / "managed"
    return RpzExternalMigrationPlan(
        "READY",
        "cert-rpz.local",
        "external.timer",
        "external.service",
        True,
        True,
        tuple(artifacts),
        managed / "updater",
        managed / "managed.service",
        managed / "managed.timer",
        tmp_path / "backups",
        (),
        (),
        "dalej",
    )


def test_transaction_requires_both_flags_and_exact_confirmation(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    tx = RpzExternalMigrationTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=tmp_path / "named.conf",
        command_runner=lambda command, timeout: (_ for _ in ()).throw(AssertionError()),
    )
    assert tx.apply(plan, commit=True).status == "REJECTED"
    assert tx.apply(plan, activate=True).status == "REJECTED"
    assert (
        tx.apply(plan, commit=True, activate=True, confirm="wrong").status == "REJECTED"
    )


def test_changed_source_hash_blocks_before_dry_run(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    plan.artifacts[1].path.write_text("changed", encoding="utf-8")
    result = RpzExternalMigrationTransaction(
        command_runner=lambda command, timeout: (_ for _ in ()).throw(AssertionError())
    ).apply(plan)
    assert result.status == "BLOCKED"
    assert "SHA-256" in result.steps[0].message


def test_forced_activation_failure_restores_external_timer(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    before = {item.role: item.path.read_bytes() for item in plan.artifacts}
    commands: list[list[str]] = []

    def runner(command: list[str], timeout: int) -> CommandResult:
        commands.append(command)
        if command[:2] == ["rndc", "zonestatus"]:
            return CommandResult(0, "serial: 123\n", "")
        if command[:3] == ["systemctl", "start", plan.managed_service.name]:
            return CommandResult(1, "", "forced failure")
        return CommandResult(0, "OK\n", "")

    result = RpzExternalMigrationTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=tmp_path / "named.conf",
        command_runner=runner,
    ).apply(plan, commit=True, activate=True, confirm=plan.zone)

    assert result.status == "ROLLED-BACK"
    assert result.rolled_back and not result.committed
    assert not plan.managed_updater.exists()
    assert not plan.managed_service.exists()
    assert not plan.managed_timer.exists()
    assert before == {item.role: item.path.read_bytes() for item in plan.artifacts}
    assert ["systemctl", "enable", "--now", "external.timer"] in commands
    assert result.manifest and Path(result.manifest).is_file()


def test_successful_transaction_keeps_external_files_as_recovery_source(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    before = {item.role: item.path.read_bytes() for item in plan.artifacts}

    def runner(command: list[str], timeout: int) -> CommandResult:
        if command[:2] == ["rndc", "zonestatus"]:
            return CommandResult(0, "serial: 124\n", "")
        if command == ["systemctl", "is-active", "external.timer"]:
            return CommandResult(3, "inactive\n", "")
        if "--property=Result" in command:
            return CommandResult(0, "success\n", "")
        return CommandResult(0, "active\n", "")

    result = RpzExternalMigrationTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=tmp_path / "named.conf",
        command_runner=runner,
    ).apply(plan, commit=True, activate=True, confirm=plan.zone)
    assert result.status == "COMMIT"
    assert result.committed and result.activated
    assert plan.managed_updater.is_file()
    assert plan.managed_service.is_file()
    assert plan.managed_timer.is_file()
    assert before == {item.role: item.path.read_bytes() for item in plan.artifacts}


def test_post_gate_failure_rolls_back_when_managed_service_result_fails(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)

    def runner(command: list[str], timeout: int) -> CommandResult:
        if command[:2] == ["rndc", "zonestatus"]:
            return CommandResult(0, "serial: 123\n", "")
        if command == ["systemctl", "is-active", "external.timer"]:
            return CommandResult(3, "inactive\n", "")
        if "--property=Result" in command:
            return CommandResult(0, "exit-code\n", "")
        return CommandResult(0, "active\n", "")

    result = RpzExternalMigrationTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=tmp_path / "named.conf",
        command_runner=runner,
    ).apply(plan, commit=True, activate=True, confirm=plan.zone)
    assert result.status == "ROLLED-BACK"
    assert any(
        step.name == "managed-service-result" and not step.ok for step in result.steps
    )


def test_stale_zone_after_cutover_forces_rollback(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    zone_file = next(item.path for item in plan.artifacts if item.role == "zone-file")

    def runner(command: list[str], timeout: int) -> CommandResult:
        if command[:2] == ["rndc", "zonestatus"]:
            return CommandResult(0, "serial: 123\n", "")
        if command == ["systemctl", "is-active", "external.timer"]:
            return CommandResult(3, "inactive\n", "")
        if "--property=Result" in command:
            return CommandResult(0, "success\n", "")
        return CommandResult(0, "active\n", "")

    result = RpzExternalMigrationTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=tmp_path / "named.conf",
        command_runner=runner,
        clock=lambda: zone_file.stat().st_mtime + 601,
    ).apply(plan, commit=True, activate=True, confirm=plan.zone)
    assert result.status == "ROLLED-BACK"
    assert any(step.name == "freshness" and not step.ok for step in result.steps)
