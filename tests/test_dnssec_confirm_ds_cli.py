from __future__ import annotations

import json
from pathlib import Path

from zonectl import cli
from zonectl.core.dnssec_confirm_ds import DnssecConfirmResult, DnssecConfirmStep
from zonectl.core.models import Zone


class FakeConfig:
    toolkit = {"local_server": "127.0.0.1", "dig_timeout": "3"}

    def zones(self):
        return [Zone("example.pl", Path("/zones/example.pl"))]


class FakeChecker:
    def __init__(self, **kwargs):
        pass

    def collect(self, zone, resolvers):
        raise AssertionError(
            "checker is passed through, not called by fake transaction"
        )


class FakeTransaction:
    calls = []

    def __init__(self, manifest_directory, *, checker):
        self.calls.append((manifest_directory, checker))

    def apply(self, zone, resolvers, *, commit, acknowledge_published):
        self.calls.append((zone, resolvers, commit, acknowledge_published))
        return DnssecConfirmResult(
            "tx-test",
            zone,
            "CONFIRMED" if commit else "DRY-RUN",
            committed=commit,
            steps=[DnssecConfirmStep("check-ds", True, "PASS")],
        )


def configure(monkeypatch) -> None:
    FakeTransaction.calls = []
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: FakeConfig())
    monkeypatch.setattr(cli, "DnssecDsChecker", FakeChecker)
    monkeypatch.setattr(cli, "DnssecConfirmDsTransaction", FakeTransaction)


def test_confirm_ds_defaults_to_dry_run(monkeypatch, capsys) -> None:
    configure(monkeypatch)

    code = cli.main(["dnssec", "confirm-ds", "example.pl", "--json"])

    assert code == 0
    assert FakeTransaction.calls[-1][2:] == (False, False)
    assert json.loads(capsys.readouterr().out)["status"] == "DRY-RUN"


def test_confirm_ds_requires_both_confirmation_flags(monkeypatch, capsys) -> None:
    configure(monkeypatch)

    assert cli.main(["dnssec", "confirm-ds", "example.pl", "--commit"]) == 2
    assert (
        cli.main(["dnssec", "confirm-ds", "example.pl", "--acknowledge-published"]) == 2
    )

    assert "--commit i --acknowledge-published" in capsys.readouterr().err
    assert FakeTransaction.calls == []


def test_confirm_ds_passes_resolvers_and_commit(monkeypatch) -> None:
    configure(monkeypatch)

    code = cli.main(
        [
            "dnssec",
            "confirm-ds",
            "example.pl",
            "--resolver",
            "r1",
            "--resolver",
            "r2",
            "--commit",
            "--acknowledge-published",
        ]
    )

    assert code == 0
    assert FakeTransaction.calls[-1] == (
        "example.pl",
        ("r1", "r2"),
        True,
        True,
    )
