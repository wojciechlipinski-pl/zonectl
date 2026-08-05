from __future__ import annotations

import json
from pathlib import Path

from zonectl import cli
from zonectl.core.dnssec_report import DnssecReport
from zonectl.core.models import Zone


class FakeConfig:
    toolkit = {
        "local_server": "127.0.0.1",
        "dig_timeout": "3",
        "dnssec_key_directory": "/var/lib/bind/keys",
    }

    def zones(self):
        return [
            Zone(
                "example.pl",
                Path("/zones/example.pl"),
                dnssec_policy="default",
                inline_signing=True,
            )
        ]


def test_dnssec_report_cli_outputs_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: FakeConfig())
    monkeypatch.setattr(
        cli.DnssecReporter,
        "collect",
        lambda self, zone, key_directory: DnssecReport(
            zone=zone.name,
            status="PASS",
            configured=True,
            dnssec_policy="default",
            inline_signing=True,
            loaded=True,
            signing=True,
            rndc_status=("zone signing: yes",),
            key_directory=str(key_directory),
            key_files=(),
            dnskey_records=("257 3 13 YWJjZA==",),
            rrsig_records=("DNSKEY 13 2 signature",),
            calculated_ds=("27944 13 2 ABCD",),
            parent_ds_records=("27944 13 2 ABCD",),
            parent_ds_matches=True,
            warnings=(),
            errors=(),
        ),
    )

    code = cli.main(["dnssec", "report", "example.pl", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["zone"] == "example.pl"
    assert payload["status"] == "PASS"
    assert payload["parent_ds_matches"] is True


def test_dnssec_report_cli_rejects_unknown_zone(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: FakeConfig())

    code = cli.main(["dnssec", "report", "missing.pl"])

    assert code == 2
    assert "Nie znaleziono strefy" in capsys.readouterr().err


def test_dnssec_report_cli_shows_operator_guidance(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: FakeConfig())
    monkeypatch.setattr(
        cli.DnssecReporter,
        "collect",
        lambda self, zone, key_directory: DnssecReport(
            zone=zone.name,
            status="WARN",
            configured=True,
            dnssec_policy="default",
            inline_signing=True,
            loaded=True,
            signing=True,
            rndc_status=(
                "- dnskey: omnipresent",
                "- ds: hidden",
                "- zone rrsig: rumoured",
                "- key rrsig: omnipresent",
            ),
            key_directory=str(key_directory),
            key_files=(),
            dnskey_records=("257 3 13 YWJjZA==",),
            rrsig_records=("DNSKEY 13 2 signature",),
            calculated_ds=("27944 13 2 ABCD",),
            parent_ds_records=(),
            parent_ds_matches=False,
            warnings=("Brak DS",),
            errors=(),
            next_key_event="Wed, 05 Aug 2026 07:41:35 GMT",
        ),
    )

    code = cli.main(["dnssec", "report", "example.pl"])
    output = capsys.readouterr().out

    assert code == 0
    assert "WSKAZÓWKI OPERATORA" in output
    assert "PROPAGATING" in output
    assert "2/3 warunków propagacji gotowych" in output
    assert "JESZCZE ZABLOKOWANA" in output
