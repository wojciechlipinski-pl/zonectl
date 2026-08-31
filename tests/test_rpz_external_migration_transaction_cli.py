from zonectl import cli
from zonectl.core.rpz_external_migration_transaction import (
    RpzMigrationTransactionResult,
    RpzMigrationTransactionStep,
)


class _EmptyConfig:
    def zones(self):
        return []


def test_apply_cli_defaults_to_dry_run(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    monkeypatch.setattr(cli.RpzExternalMigrationPlanner, "plan", lambda self: object())

    def apply(self, plan, *, commit=False, activate=False, confirm=None):
        assert not commit and not activate and confirm is None
        return RpzMigrationTransactionResult(
            "tx",
            "cert-rpz.local",
            "DRY-RUN",
            steps=[RpzMigrationTransactionStep("dry-run", True, "bez zmian")],
        )

    monkeypatch.setattr(cli.RpzExternalMigrationTransaction, "apply", apply)
    code = cli.main(["bind", "rpz-external-migration-apply"])
    output = capsys.readouterr().out
    assert code == 0
    assert "Status:      DRY-RUN" in output
    assert "Commit:      NIE" in output


def test_single_write_flag_is_rejected_by_cli_result(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    monkeypatch.setattr(cli.RpzExternalMigrationPlanner, "plan", lambda self: object())
    monkeypatch.setattr(
        cli.RpzExternalMigrationTransaction,
        "apply",
        lambda self, plan, **kwargs: RpzMigrationTransactionResult(
            "tx",
            "cert-rpz.local",
            "REJECTED",
            steps=[RpzMigrationTransactionStep("guard", False, "obie flagi")],
        ),
    )
    assert cli.main(["bind", "rpz-external-migration-apply", "--commit"]) == 2
    assert "REJECTED" in capsys.readouterr().out
