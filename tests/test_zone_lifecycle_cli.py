from __future__ import annotations

import json

from zonectl import cli


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
