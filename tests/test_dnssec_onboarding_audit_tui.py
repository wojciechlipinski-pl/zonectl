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
