from zonectl import cli
from zonectl.core.rpz_managed_install import (
    RpzManagedInstallResult,
    RpzManagedInstallStep,
)


class _EmptyConfig:
    def zones(self):
        return []


def test_managed_install_cli_is_dry_run_by_design(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    monkeypatch.setattr(cli.RpzManagedPlanner, "plan", lambda self: object())
    monkeypatch.setattr(
        cli.RpzManagedInstallDryRun,
        "execute",
        lambda self, plan: RpzManagedInstallResult(
            "cert-rpz.local",
            "DRY-RUN",
            steps=[RpzManagedInstallStep("no-system-write", True, "bez zmian")],
        ),
    )
    code = cli.main(["bind", "rpz-managed-dry-run"])
    output = capsys.readouterr().out
    assert code == 0
    assert "DRY-RUN ŚWIEŻEJ INSTALACJI" in output
    assert "Commit:       NIE" in output
    assert "nie zmieniono BIND" in output


def test_managed_install_cli_returns_failure_for_blocked_plan(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    monkeypatch.setattr(cli.RpzManagedPlanner, "plan", lambda self: object())
    monkeypatch.setattr(
        cli.RpzManagedInstallDryRun,
        "execute",
        lambda self, plan: RpzManagedInstallResult(
            "cert-rpz.local",
            "BLOCKED",
            steps=[RpzManagedInstallStep("preflight", False, "konflikt")],
        ),
    )
    assert cli.main(["bind", "rpz-managed-dry-run"]) == 1
    assert "konflikt" in capsys.readouterr().out


def test_managed_apply_rejects_single_write_flag(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    monkeypatch.setattr(cli.RpzManagedPlanner, "plan", lambda self: object())
    monkeypatch.setattr(
        cli.RpzManagedInstallTransaction,
        "apply",
        lambda self, plan, **kwargs: RpzManagedInstallResult(
            "cert-rpz.local", "REJECTED",
            transaction_id="tx",
            steps=[RpzManagedInstallStep("guard", False, "wymagane dwie flagi")],
        ),
    )
    code = cli.main(["bind", "rpz-managed-apply", "--commit"])
    assert code == 2
    assert "wymagane dwie flagi" in capsys.readouterr().out


def test_managed_apply_reports_commit_and_manifest(monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    monkeypatch.setattr(cli.RpzManagedPlanner, "plan", lambda self: object())
    monkeypatch.setattr(
        cli.RpzManagedInstallTransaction,
        "apply",
        lambda self, plan, **kwargs: RpzManagedInstallResult(
            "cert-rpz.local", "COMMIT", committed=True, activated=True,
            transaction_id="tx", manifest="/backup/tx.json",
        ),
    )
    code = cli.main([
        "bind", "rpz-managed-apply", "--commit", "--activate",
        "--confirm", "cert-rpz.local",
        "--manifest-directory", str(tmp_path),
    ])
    output = capsys.readouterr().out
    assert code == 0
    assert "Status:     COMMIT" in output
    assert "Manifest:   /backup/tx.json" in output
