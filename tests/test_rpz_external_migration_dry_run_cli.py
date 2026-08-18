from zonectl import cli
from zonectl.core.rpz_external_migration_dry_run import (
    RpzMigrationDryRunResult,
    RpzMigrationDryRunStep,
)


class _EmptyConfig:
    def zones(self):
        return []


def test_migration_dry_run_cli_has_no_commit_path(monkeypatch, capsys) -> None:
    result = RpzMigrationDryRunResult(
        "cert-rpz.local", "DRY-RUN", False, False,
        {"updater": "a" * 64},
        [RpzMigrationDryRunStep("no-activation", True, "bez zmian")],
    )
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    monkeypatch.setattr(
        cli.RpzExternalMigrationPlanner, "plan", lambda self: object()
    )
    monkeypatch.setattr(
        cli.RpzExternalMigrationDryRun, "execute", lambda self, plan: result
    )
    code = cli.main(["bind", "rpz-external-migration-dry-run"])
    output = capsys.readouterr().out
    assert code == 0
    assert "Commit:          NIE" in output
    assert "Przełączenie:    NIE" in output
    assert "nie zatrzymano timera" in output
