from pathlib import Path

from zonectl.core.bind_environment_report import BindEnvironmentReport, RpzEnvironment
from zonectl.core.rpz_managed_plan import CERT_POLSKA_RPZ_URL, RpzManagedPlanner


def _report(*rpz: RpzEnvironment) -> BindEnvironmentReport:
    return BindEnvironmentReport("/etc/bind/named.conf", (), 0, 0, 0, 0, rpz, ())


def _external() -> RpzEnvironment:
    return RpzEnvironment(
        "cert-rpz.local",
        "/etc/bind/domains_rpz.db",
        "EXTERNAL",
        "ACTIVE",
        20,
        600,
        "123",
        42,
        True,
        "update-cert-rpz.timer",
        True,
        True,
        "update-cert-rpz.service",
        "success",
        "now",
        "later",
        "/usr/local/sbin/update-cert-rpz.sh",
        (),
    )


def test_plan_blocks_silent_takeover_of_external_integration(monkeypatch) -> None:
    monkeypatch.setattr(
        "zonectl.core.rpz_managed_plan.BindEnvironmentReporter.collect",
        lambda self: _report(_external()),
    )
    plan = RpzManagedPlanner().plan()
    assert plan.status == "BLOCKED_EXTERNAL"
    assert "EXTERNAL" in plan.conflicts[0]
    assert "nie przejmuj" in plan.next_action
    assert plan.source_url == CERT_POLSKA_RPZ_URL


def test_clean_environment_produces_read_only_ready_plan(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "zonectl.core.rpz_managed_plan.BindEnvironmentReporter.collect",
        lambda self: _report(),
    )
    targets = [
        tmp_path / name for name in ("zone", "decl", "updater", "service", "timer")
    ]
    plan = RpzManagedPlanner(
        tmp_path / "named.conf",
        zone_file=targets[0],
        declaration_file=targets[1],
        updater_file=targets[2],
        service_file=targets[3],
        timer_file=targets[4],
        backup_root=tmp_path / "backup",
    ).plan()
    assert plan.status == "READY"
    assert plan.conflicts == ()
    assert len(plan.steps) == 8
    assert not any(path.exists() for path in targets)


def test_existing_target_blocks_plan(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "zonectl.core.rpz_managed_plan.BindEnvironmentReporter.collect",
        lambda self: _report(),
    )
    target = tmp_path / "updater"
    target.write_text("external", encoding="utf-8")
    plan = RpzManagedPlanner(
        tmp_path / "named.conf",
        zone_file=tmp_path / "zone",
        declaration_file=tmp_path / "declaration",
        updater_file=target,
        service_file=tmp_path / "service",
        timer_file=tmp_path / "timer",
        backup_root=tmp_path / "backup",
    ).plan()
    assert plan.status == "BLOCKED_CONFLICT"
    assert str(target) in plan.conflicts[0]


def test_plan_identifies_single_options_file(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "named.conf"
    options = tmp_path / "named.conf.options"
    root.write_text(f'include "{options}";\n', encoding="utf-8")
    options.write_text("options { recursion no; };\n", encoding="utf-8")
    report = BindEnvironmentReport(
        str(root), (str(root), str(options)), 0, 0, 0, 0, (), ()
    )
    monkeypatch.setattr(
        "zonectl.core.rpz_managed_plan.BindEnvironmentReporter.collect",
        lambda self: report,
    )
    plan = RpzManagedPlanner(
        root,
        zone_file=tmp_path / "zone",
        declaration_file=tmp_path / "rpz.conf",
        updater_file=tmp_path / "updater",
        service_file=tmp_path / "service",
        timer_file=tmp_path / "timer",
    ).plan()
    assert plan.status == "READY"
    assert plan.options_file == options


def test_plan_blocks_ambiguous_options_files(monkeypatch, tmp_path: Path) -> None:
    first = tmp_path / "first.conf"
    second = tmp_path / "second.conf"
    first.write_text("options { recursion no; };\n", encoding="utf-8")
    second.write_text("options { recursion yes; };\n", encoding="utf-8")
    report = BindEnvironmentReport(
        str(first), (str(first), str(second)), 0, 0, 0, 0, (), ()
    )
    monkeypatch.setattr(
        "zonectl.core.rpz_managed_plan.BindEnvironmentReporter.collect",
        lambda self: report,
    )
    plan = RpzManagedPlanner(
        first,
        zone_file=tmp_path / "zone",
        declaration_file=tmp_path / "rpz.conf",
        updater_file=tmp_path / "updater",
        service_file=tmp_path / "service",
        timer_file=tmp_path / "timer",
    ).plan()
    assert plan.status == "BLOCKED_CONFLICT"
    assert any("bloku options" in item for item in plan.conflicts)
