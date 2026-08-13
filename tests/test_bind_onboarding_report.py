from pathlib import Path

from zonectl.core.bind_onboarding_report import BindOnboardingReporter


def test_state_normalisation_is_conservative() -> None:
    normalise = BindOnboardingReporter._normalise_state
    assert normalise("MANAGED") == "MANAGED"
    assert normalise("LEGACY_PRIMARY") == "LEGACY"
    assert normalise("EXTERNAL_INCLUDE") == "EXTERNAL"
    assert normalise("BLOCKED_DNSSEC") == "BLOCKED"
    assert normalise("UNKNOWN") == "BLOCKED"
