from pathlib import Path

from zonectl.core.rpz_external_migration_dry_run import RpzExternalMigrationDryRun
from zonectl.core.rpz_external_migration_plan import (
    RpzExternalMigrationPlan,
    RpzMigrationArtifact,
)
from zonectl.core.runner import CommandResult


def _plan(tmp_path: Path, status: str = "READY") -> RpzExternalMigrationPlan:
    contents = {
        "zone-file": "$ORIGIN cert-rpz.local.\n",
        "updater": "#!/bin/bash\nexit 0\n",
        "service-unit": "[Service]\nExecStart=UPDATER_PATH\n",
        "timer-unit": "[Timer]\nOnCalendar=*:0/5\n",
    }
    artifacts = []
    for role, content in contents.items():
        path = tmp_path / role
        path.write_text(
            content.replace("UPDATER_PATH", str(tmp_path / "updater")),
            encoding="utf-8",
        )
        artifacts.append(RpzMigrationArtifact(role, path, True, 0, 0, "-rw-r--r--", "old"))
    return RpzExternalMigrationPlan(
        status, "cert-rpz.local", "external.timer", "external.service", True,
        True, tuple(artifacts), Path("/managed/updater"),
        Path("/managed/service"), Path("/managed/timer"), tmp_path / "backup",
        () if status == "READY" else ("blokada",), (), "dalej",
    )


def test_dry_run_validates_candidates_and_keeps_sources_unchanged(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    before = {item.role: item.path.read_bytes() for item in plan.artifacts}
    commands: list[list[str]] = []

    def runner(command: list[str], timeout: int) -> CommandResult:
        commands.append(command)
        return CommandResult(0, "OK\n", "")

    result = RpzExternalMigrationDryRun(
        root_config=tmp_path / "named.conf", command_runner=runner
    ).execute(plan)
    assert result.status == "DRY-RUN"
    assert not result.committed and not result.timer_switched
    assert {command[0] for command in commands} == {"bash", "named-checkzone", "named-checkconf"}
    assert before == {item.role: item.path.read_bytes() for item in plan.artifacts}
    assert all(result.candidate_hashes.values())


def test_dry_run_refuses_blocked_plan_without_commands(tmp_path: Path) -> None:
    plan = _plan(tmp_path, "BLOCKED")
    result = RpzExternalMigrationDryRun(
        command_runner=lambda command, timeout: (_ for _ in ()).throw(AssertionError())
    ).execute(plan)
    assert result.status == "BLOCKED"
    assert result.steps[0].name == "preflight"
