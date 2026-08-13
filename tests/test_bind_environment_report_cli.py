import json
from pathlib import Path

from zonectl import cli
from zonectl.core.bind_environment_report import (
    BindEnvironmentReport,
    RpzEnvironment,
)


class _EmptyConfig:
    def zones(self):
        return []


def _report() -> BindEnvironmentReport:
    return BindEnvironmentReport(
        root_config="/etc/bind/named.conf",
        config_files=("/etc/bind/named.conf",),
        zone_count=3,
        primary_count=2,
        secondary_count=1,
        dnssec_count=1,
        rpz=(
            RpzEnvironment(
                zone="cert-rpz.local",
                source_file="/etc/bind/domains_rpz.db",
                mode="EXTERNAL",
                health="ACTIVE",
                age_seconds=180,
                max_age_seconds=600,
                serial="123",
                nodes=278112,
                loaded=True,
                timer_unit="update-cert-rpz.timer",
                timer_enabled=True,
                timer_active=True,
                service_unit="update-cert-rpz.service",
                service_result="success",
                updater_path="/usr/local/sbin/update-cert-rpz.sh",
                findings=(),
            ),
        ),
        findings=(),
    )


def test_environment_report_cli_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    monkeypatch.setattr(cli.BindEnvironmentReporter, "collect", lambda self: _report())
    code = cli.main(["bind", "environment-report", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["rpz"][0]["mode"] == "EXTERNAL"
    assert payload["rpz"][0]["age_seconds"] == 180


def test_environment_report_cli_text(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    monkeypatch.setattr(cli.BindEnvironmentReporter, "collect", lambda self: _report())
    code = cli.main(["bind", "environment-report"])
    output = capsys.readouterr().out
    assert code == 0
    assert "RAPORT ŚRODOWISKA BIND — TYLKO ODCZYT" in output
    assert "[ACTIVE] cert-rpz.local" in output
    assert "Tryb zarządzania: EXTERNAL" in output
    assert "Wiek:             180 s" in output
