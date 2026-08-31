from pathlib import Path

from zonectl.core.bind_environment_report import BindEnvironmentReport, RpzEnvironment
from zonectl.core.rpz_external_migration_plan import RpzExternalMigrationPlanner
from zonectl.core.runner import CommandResult


def _external(zone_file: Path, updater: Path) -> RpzEnvironment:
    return RpzEnvironment(
        "cert-rpz.local",
        str(zone_file),
        "EXTERNAL",
        "ACTIVE",
        10,
        600,
        "123",
        42,
        True,
        "external.timer",
        True,
        True,
        "external.service",
        "success",
        "now",
        "later",
        str(updater),
        (),
    )


def test_ready_plan_inventories_external_files_without_exposing_content(
    monkeypatch, tmp_path: Path
) -> None:
    paths = {name: tmp_path / name for name in ("zone", "updater", "service", "timer")}
    for name, path in paths.items():
        path.write_text(f"secret-{name}", encoding="utf-8")
    environment = BindEnvironmentReport(
        "/etc/bind/named.conf",
        (),
        1,
        1,
        0,
        0,
        (_external(paths["zone"], paths["updater"]),),
        (),
    )
    monkeypatch.setattr(
        "zonectl.core.rpz_external_migration_plan.BindEnvironmentReporter.collect",
        lambda self: environment,
    )

    def runner(command: list[str], timeout: int) -> CommandResult:
        if "--property=FragmentPath" in command:
            path = paths["timer"] if "external.timer" in command else paths["service"]
            return CommandResult(0, f"{path}\n", "")
        raise AssertionError(command)

    plan = RpzExternalMigrationPlanner(
        command_runner=runner,
        managed_updater=tmp_path / "managed-updater",
        managed_service=tmp_path / "managed-service",
        managed_timer=tmp_path / "managed-timer",
    ).plan()
    assert plan.status == "READY"
    assert all(item.exists and item.sha256 for item in plan.artifacts)
    assert "secret" not in str(plan.to_dict())
    assert plan.current_enabled and plan.current_active


def test_missing_external_artifact_blocks_migration(
    monkeypatch, tmp_path: Path
) -> None:
    zone = tmp_path / "zone"
    updater = tmp_path / "updater"
    zone.write_text("zone", encoding="utf-8")
    updater.write_text("updater", encoding="utf-8")
    environment = BindEnvironmentReport(
        "/etc/bind/named.conf",
        (),
        1,
        1,
        0,
        0,
        (_external(zone, updater),),
        (),
    )
    monkeypatch.setattr(
        "zonectl.core.rpz_external_migration_plan.BindEnvironmentReporter.collect",
        lambda self: environment,
    )

    def runner(command: list[str], timeout: float) -> CommandResult:
        return CommandResult(1, "", "")

    plan = RpzExternalMigrationPlanner(command_runner=runner).plan()
    assert plan.status == "BLOCKED"
    assert "Nie ustalono ścieżki: service-unit" in plan.blockers
    assert "niczego nie przełączaj" in plan.next_action
