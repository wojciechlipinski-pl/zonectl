from __future__ import annotations

import json
from pathlib import Path

from zonectl import cli
from zonectl.core.zone_create_transaction import (
    ZoneCreateResult,
    ZoneCreateStep,
)


class FakeConfig:
    def zones(self):
        return []


def test_create_plan_cli_outputs_json(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        cli.ToolkitConfig,
        "load",
        lambda self: FakeConfig(),
    )

    code = cli.main(
        [
            "zone",
            "create-plan",
            "example.pl",
            "--primary-ns",
            "ns1.elkman.pl.",
            "--admin",
            "hostmaster.elkman.pl.",
            "--ns",
            "ns1.elkman.pl.",
            "--json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["zone_name"] == "example.pl"
    assert payload["zone_file"].endswith("/example.pl")


def test_create_plan_cli_reports_validation_error(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        cli.ToolkitConfig,
        "load",
        lambda self: FakeConfig(),
    )

    code = cli.main(
        [
            "zone",
            "create-plan",
            "bad_name.pl",
            "--primary-ns",
            "ns1.elkman.pl.",
            "--admin",
            "hostmaster.elkman.pl.",
            "--ns",
            "ns1.elkman.pl.",
        ]
    )

    assert code == 2
    assert "BŁĄD:" in capsys.readouterr().err


def test_create_cli_defaults_to_dry_run(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        cli.ToolkitConfig,
        "load",
        lambda self: FakeConfig(),
    )
    calls = []

    def apply(self, plan, *, commit=False, activate=False):
        calls.append((commit, activate, plan.zone_name))
        return ZoneCreateResult(
            "tx-1",
            plan.zone_name,
            "DRY-RUN",
            steps=[ZoneCreateStep("dry-run", True, "bez zmian")],
        )

    monkeypatch.setattr(cli.ZoneCreateTransaction, "apply", apply)
    code = cli.main(
        [
            "zone",
            "create",
            "example.pl",
            "--primary-ns",
            "ns1.elkman.pl.",
            "--admin",
            "hostmaster.elkman.pl.",
            "--ns",
            "ns1.elkman.pl.",
            "--zone-directory",
            str(tmp_path / "zones"),
            "--managed-config",
            str(tmp_path / "zones.conf"),
            "--managed-zone-directory",
            str(tmp_path / "zones.d"),
        ]
    )
    assert code == 0
    assert calls == [(False, False, "example.pl")]
    assert "Status:     DRY-RUN" in capsys.readouterr().out


def test_create_cli_commit_requests_activation(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        cli.ToolkitConfig,
        "load",
        lambda self: FakeConfig(),
    )
    calls = []

    def apply(self, plan, *, commit=False, activate=False):
        calls.append((commit, activate))
        return ZoneCreateResult(
            "tx-2",
            plan.zone_name,
            "COMMIT",
            committed=True,
            steps=[ZoneCreateStep("rndc-zonestatus", True, "loaded")],
        )

    monkeypatch.setattr(cli.ZoneCreateTransaction, "apply", apply)
    code = cli.main(
        [
            "zone",
            "create",
            "example.pl",
            "--primary-ns",
            "ns1.elkman.pl.",
            "--admin",
            "hostmaster.elkman.pl.",
            "--ns",
            "ns1.elkman.pl.",
            "--commit",
        ]
    )
    assert code == 0
    assert calls == [(True, True)]
    assert "Status:     COMMIT" in capsys.readouterr().out
