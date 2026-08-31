from pathlib import Path

from zonectl import cli
from zonectl.core.rpz_external_migration_plan import (
    RpzExternalMigrationPlan,
    RpzMigrationArtifact,
)


class _EmptyConfig:
    def zones(self):
        return []


def test_external_migration_cli_is_read_only(monkeypatch, capsys) -> None:
    artifact = RpzMigrationArtifact(
        "updater",
        Path("/usr/local/sbin/update-cert-rpz.sh"),
        True,
        0,
        0,
        "-rwxr-x---",
        "a" * 64,
    )
    plan = RpzExternalMigrationPlan(
        "READY",
        "cert-rpz.local",
        "external.timer",
        "external.service",
        True,
        True,
        (artifact,),
        Path("/managed/updater"),
        Path("/managed/service"),
        Path("/managed/timer"),
        Path("/backup"),
        (),
        ("wykonaj backup",),
        "Można przygotować dry-run.",
    )
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    monkeypatch.setattr(cli.RpzExternalMigrationPlanner, "plan", lambda self: plan)
    code = cli.main(["bind", "rpz-external-migration-plan"])
    output = capsys.readouterr().out
    assert code == 0
    assert "TYLKO ODCZYT" in output
    assert "SHA-256" in output
    assert "nie zatrzymano timera" in output
