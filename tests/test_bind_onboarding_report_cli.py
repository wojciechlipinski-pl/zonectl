import json

from zonectl import cli
from zonectl.core.bind_onboarding_report import BindOnboardingReport, OnboardingClass


class _EmptyConfig:
    def zones(self):
        return []


def _report() -> BindOnboardingReport:
    return BindOnboardingReport(
        root_config="/etc/bind/named.conf",
        config_files=7,
        zones=23,
        dnssec_zones=14,
        classes=(OnboardingClass("LEGACY", 7, "kandydaci"),),
        acl_definitions=3,
        secondary_groups=4,
        rpz_integrations=1,
        rpz_modes=("EXTERNAL",),
        candidates=(),
        blockers=(),
        import_candidates=7,
        blocked=14,
        next_action="Utwórz plany.",
    )


def test_onboarding_report_cli_is_read_only(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    monkeypatch.setattr(cli.BindOnboardingReporter, "collect", lambda self: _report())
    assert cli.main(["bind", "onboarding-report"]) == 0
    output = capsys.readouterr().out
    assert "GOTOWOŚĆ ŚRODOWISKA BIND" in output
    assert "niczego nie zaimportowano" in output


def test_onboarding_report_cli_outputs_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    monkeypatch.setattr(cli.BindOnboardingReporter, "collect", lambda self: _report())
    assert cli.main(["bind", "onboarding-report", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["import_candidates"] == 7
