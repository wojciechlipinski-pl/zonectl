from zonectl.core.models import Health
from zonectl.ui.semantic_status import (
    kasp_health,
    parse_kasp_line,
    state_health,
    text_health,
)


def test_common_states_have_consistent_semantics() -> None:
    assert state_health("PASS") is Health.PASS
    assert state_health("dry_run") is Health.WARN
    assert state_health("BLOCKED_DNSSEC") is Health.FAIL
    assert state_health("MANAGED_LEGACY_PATH") is Health.WARN
    assert state_health("DS_PROPAGATING") is Health.WARN
    assert state_health("HIGH") is Health.FAIL
    assert state_health("NONE") is Health.PASS
    assert state_health("DISABLED") is Health.WARN
    assert state_health("SKIP") is Health.UNKNOWN
    assert state_health("ordinary text") is None


def test_status_is_extracted_without_coloring_arbitrary_prose() -> None:
    assert text_health("Status: COMMIT") is Health.PASS
    assert text_health("[PENDING] secondary serial is lower") is Health.WARN
    assert text_health("[NOT-AUTH] no AA flag") is Health.FAIL
    assert text_health("Monitoruj stan integracji") is None


def test_kasp_transition_is_warning_not_failure() -> None:
    assert kasp_health("omnipresent", goal="omnipresent") is Health.PASS
    assert kasp_health("rumoured", goal="omnipresent") is Health.WARN
    assert kasp_health("unretentive", goal="hidden") is Health.WARN
    assert kasp_health("hidden", goal="hidden") is Health.PASS
    assert kasp_health("hidden", goal="omnipresent") is Health.WARN


def test_kasp_line_parser_accepts_rndc_presentation() -> None:
    assert parse_kasp_line("- zone rrsig:     omnipresent") == (
        "zone rrsig", "omnipresent"
    )
    assert parse_kasp_line("STAN KASP") is None
