from __future__ import annotations

import json
from pathlib import Path

from zonectl import cli
from zonectl.core.dnssec_ds_check import (
    DnskeyAuthorityCheck,
    DnssecDsCheck,
    DsResolverCheck,
)
from zonectl.core.models import Zone


class FakeConfig:
    toolkit = {"local_server": "127.0.0.1", "dig_timeout": "3"}

    def zones(self):
        return [Zone("example.pl", Path("/zones/example.pl"))]


class FakeChecker:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def collect(self, zone, resolvers):
        assert zone == "example.pl"
        assert resolvers == ("r1", "r2")
        return DnssecDsCheck(
            zone=zone,
            status="PROPAGATING",
            kasp_ready=True,
            expected_ds=("12345 13 2 ABCD",),
            resolver_checks=(
                DsResolverCheck("r1", "MATCH", ("12345 13 2 ABCD",), "DS jest zgodny"),
                DsResolverCheck("r2", "MISSING", (), "DS nie jest widoczny"),
            ),
            authority_checks=(
                DnskeyAuthorityCheck(
                    "ns1.example.pl", "MATCH", True, ("key",), ("sig",), "OK"
                ),
            ),
            next_action="Poczekaj na propagację.",
            errors=(),
        )


def test_check_ds_cli_prints_progress(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: FakeConfig())
    monkeypatch.setattr(cli, "DnssecDsChecker", FakeChecker)

    code = cli.main(
        ["dnssec", "check-ds", "example.pl", "--resolver", "r1", "--resolver", "r2"]
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "KONTROLA DS — example.pl" in output
    assert "PROPAGATING" in output
    assert "r1" in output and "r2" in output
    assert "Poczekaj na propagację" in output


def test_check_ds_cli_outputs_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: FakeConfig())
    monkeypatch.setattr(cli, "DnssecDsChecker", FakeChecker)

    code = cli.main(
        [
            "dnssec",
            "check-ds",
            "example.pl",
            "--resolver",
            "r1",
            "--resolver",
            "r2",
            "--json",
        ]
    )

    assert code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PROPAGATING"


def test_check_ds_cli_rejects_unknown_zone(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: FakeConfig())

    code = cli.main(["dnssec", "check-ds", "missing.pl"])

    assert code == 2
    assert "Nie znaleziono strefy" in capsys.readouterr().err
