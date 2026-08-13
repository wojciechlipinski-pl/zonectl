import inspect

from zonectl.ui.curses_app import CursesApp


def test_dnssec_list_offers_read_only_bulk_audit() -> None:
    listing = inspect.getsource(CursesApp._onboarding_dnssec_view)
    audit = inspect.getsource(CursesApp._dnssec_onboarding_audit_view)
    assert "F7 audyt" in listing
    assert "DnssecOnboardingAuditor" in audit
    assert "TYLKO ODCZYT" in audit
    for forbidden in ("commit=True", "activate=True", "transaction.apply"):
        assert forbidden not in audit


def test_dnssec_bulk_audit_uses_responsive_48_layout() -> None:
    audit = inspect.getsource(CursesApp._dnssec_onboarding_audit_view)
    renderer = inspect.getsource(CursesApp._dnssec_onboarding_audit_result_view)
    assert "_dnssec_onboarding_audit_result_view" in audit
    assert "width >= 100 and height >= 20" in renderer
    assert "STAN OPERACYJNY" in renderer
    assert "BEZPIECZEŃSTWO" in renderer
    assert "Klucze bez zmian" in renderer
    assert "KASP bez zmian" in renderer
    assert "DS bez zmian" in renderer
