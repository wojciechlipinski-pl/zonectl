from pathlib import Path

from zonectl.core.bind_environment_report import BindEnvironmentReporter
from zonectl.core.runner import CommandResult


def _config(tmp_path: Path) -> tuple[Path, Path]:
    zone = tmp_path / "domains_rpz.db"
    zone.write_text("$ORIGIN cert-rpz.local.\n", encoding="utf-8")
    root = tmp_path / "named.conf"
    root.write_text(
        'options { response-policy { zone "cert-rpz.local"; }; };\n'
        'zone "example.pl" { type primary; file "example.pl"; };\n'
        'zone "secondary.pl" { type secondary; file "secondary.pl"; };\n'
        'zone "cert-rpz.local" { type primary; file "domains_rpz.db"; };\n',
        encoding="utf-8",
    )
    return root, zone


def test_detects_external_healthy_rpz_without_writes(tmp_path: Path) -> None:
    root, zone_file = _config(tmp_path)
    zone_file.touch()

    def runner(command: list[str], timeout: int) -> CommandResult:
        if "--property=FragmentPath" in command:
            return CommandResult(1, "", "")
        if command[:2] == ["systemctl", "is-enabled"]:
            return CommandResult(0, "enabled\n", "")
        if command[:2] == ["systemctl", "is-active"]:
            return CommandResult(0, "active\n", "")
        if "--property=Result" in command:
            return CommandResult(0, "success\n", "")
        if "--property=LastTriggerUSec" in command:
            return CommandResult(0, "Tue 2026-08-18 10:35:24 CEST\n", "")
        if "--property=NextElapseUSecRealtime" in command:
            return CommandResult(0, "Tue 2026-08-18 10:40:02 CEST\n", "")
        if "--property=ExecStart" in command:
            return CommandResult(
                0, "{ path=/usr/local/sbin/update-cert-rpz.sh ; }\n", ""
            )
        if command[:2] == ["rndc", "zonestatus"]:
            return CommandResult(0, "serial: 123\nnodes: 278112\n", "")
        raise AssertionError(command)

    now = zone_file.stat().st_mtime + 180
    report = BindEnvironmentReporter(
        root, command_runner=runner, clock=lambda: now
    ).collect()

    assert report.zone_count == 3
    assert report.primary_count == 2
    assert report.secondary_count == 1
    assert len(report.rpz) == 1
    rpz = report.rpz[0]
    assert rpz.mode == "EXTERNAL"
    assert rpz.health == "ACTIVE"
    assert rpz.age_seconds == 180
    assert rpz.serial == "123"
    assert rpz.nodes == 278112
    assert rpz.updater_path == "/usr/local/sbin/update-cert-rpz.sh"
    assert rpz.timer_last_trigger == "Tue 2026-08-18 10:35:24 CEST"
    assert rpz.timer_next_elapse == "Tue 2026-08-18 10:40:02 CEST"


def test_reports_stale_rpz_and_inactive_timer(tmp_path: Path) -> None:
    root, zone_file = _config(tmp_path)

    def runner(command: list[str], timeout: int) -> CommandResult:
        if "--property=FragmentPath" in command:
            return CommandResult(1, "", "")
        if command[:2] in (["systemctl", "is-enabled"], ["systemctl", "is-active"]):
            return CommandResult(1, "disabled\n", "")
        if "--property=Result" in command:
            return CommandResult(0, "success\n", "")
        if "--property=LastTriggerUSec" in command:
            return CommandResult(0, "n/a\n", "")
        if "--property=NextElapseUSecRealtime" in command:
            return CommandResult(0, "n/a\n", "")
        if "--property=ExecStart" in command:
            return CommandResult(1, "", "")
        if command[:2] == ["rndc", "zonestatus"]:
            return CommandResult(0, "serial: 123\n", "")
        raise AssertionError(command)

    now = zone_file.stat().st_mtime + 1300
    rpz = (
        BindEnvironmentReporter(
            root, command_runner=runner, clock=lambda: now, rpz_max_age=600
        )
        .collect()
        .rpz[0]
    )

    assert rpz.mode == "OFF"
    assert rpz.health == "DISABLED"
    assert "Timer aktualizacji RPZ" in rpz.findings[0]


def test_classifies_delayed_stale_and_failed_rpz(tmp_path: Path) -> None:
    root, zone_file = _config(tmp_path)

    def collect(age: int, *, service_result: str = "success", loaded: bool = True):
        def runner(command: list[str], timeout: int) -> CommandResult:
            if "--property=FragmentPath" in command:
                return CommandResult(1, "", "")
            if command[:2] in (
                ["systemctl", "is-enabled"],
                ["systemctl", "is-active"],
            ):
                return CommandResult(0, "active\n", "")
            if "--property=Result" in command:
                return CommandResult(0, f"{service_result}\n", "")
            if "--property=LastTriggerUSec" in command:
                return CommandResult(0, "Tue 2026-08-18 10:35:24 CEST\n", "")
            if "--property=NextElapseUSecRealtime" in command:
                return CommandResult(0, "Tue 2026-08-18 10:40:02 CEST\n", "")
            if "--property=ExecStart" in command:
                return CommandResult(
                    0, "{ path=/usr/local/sbin/update-cert-rpz.sh ; }\n", ""
                )
            if command[:2] == ["rndc", "zonestatus"]:
                return CommandResult(
                    0 if loaded else 1,
                    "serial: 123\nnodes: 42\n" if loaded else "",
                    "",
                )
            raise AssertionError(command)

        return (
            BindEnvironmentReporter(
                root,
                command_runner=runner,
                clock=lambda: zone_file.stat().st_mtime + age,
                rpz_max_age=600,
            )
            .collect()
            .rpz[0]
        )

    assert collect(601).health == "DELAYED"
    assert collect(1201).health == "STALE"
    assert collect(60, service_result="exit-code").health == "FAILED"
    assert collect(60, loaded=False).health == "FAILED"


def test_prefers_installed_managed_units_over_external_defaults(tmp_path: Path) -> None:
    root, zone_file = _config(tmp_path)

    def runner(command: list[str], timeout: int) -> CommandResult:
        if "--property=FragmentPath" in command:
            unit = command[2]
            return CommandResult(0, f"/etc/systemd/system/{unit}\n", "")
        if command[:2] in (["systemctl", "is-enabled"], ["systemctl", "is-active"]):
            assert command[2] == "zonectl-cert-rpz.timer"
            return CommandResult(0, "active\n", "")
        if "--property=Result" in command:
            assert command[2] == "zonectl-cert-rpz.service"
            return CommandResult(0, "success\n", "")
        if "--property=LastTriggerUSec" in command:
            return CommandResult(0, "now\n", "")
        if "--property=NextElapseUSecRealtime" in command:
            return CommandResult(0, "later\n", "")
        if "--property=ExecStart" in command:
            return CommandResult(0, "{ path=/usr/lib/zonectl/update-cert-rpz ; }\n", "")
        if command[:2] == ["rndc", "zonestatus"]:
            return CommandResult(0, "serial: 123\nnodes: 42\n", "")
        raise AssertionError(command)

    rpz = (
        BindEnvironmentReporter(
            root,
            command_runner=runner,
            clock=lambda: zone_file.stat().st_mtime + 10,
        )
        .collect()
        .rpz[0]
    )
    assert rpz.mode == "MANAGED"
    assert rpz.timer_unit == "zonectl-cert-rpz.timer"
    assert rpz.service_unit == "zonectl-cert-rpz.service"
    assert rpz.updater_path == "/usr/lib/zonectl/update-cert-rpz"


def test_reports_environment_without_response_policy(tmp_path: Path) -> None:
    root = tmp_path / "named.conf"
    root.write_text(
        'zone "example.pl" { type primary; file "example.pl"; };\n',
        encoding="utf-8",
    )
    report = BindEnvironmentReporter(root).collect()
    assert report.rpz == ()
    assert "Nie wykryto aktywnej dyrektywy response-policy" in report.findings
