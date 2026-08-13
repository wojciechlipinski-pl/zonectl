from zonectl.core.bind_onboarding_report import BindOnboardingReport, OnboardingClass
from zonectl.ui.bind_onboarding_view import BindOnboardingView


def test_view_explains_read_only_import_readiness() -> None:
    report = BindOnboardingReport(
        root_config="/etc/bind/named.conf",
        config_files=7,
        zones=23,
        dnssec_zones=14,
        classes=(
            OnboardingClass("MANAGED", 1, "już zarządzane"),
            OnboardingClass("LEGACY", 7, "kandydaci"),
            OnboardingClass("EXTERNAL", 1, "zewnętrzne"),
            OnboardingClass("BLOCKED", 14, "zablokowane"),
        ),
        acl_definitions=3,
        secondary_groups=4,
        rpz_integrations=1,
        rpz_modes=("EXTERNAL",),
        candidates=(),
        import_candidates=7,
        blocked=14,
        next_action="Utwórz plany.",
    )
    view = BindOnboardingView.build(report)
    text = "\n".join(view.lines)
    assert "Strefy                23" in text
    assert "[LEGACY  ]   7" in text
    assert "Tryby RPZ             EXTERNAL" in text
    assert "Raport tylko do odczytu" in text
