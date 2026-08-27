from __future__ import annotations

import inspect

from zonectl.ui.curses_app import CursesApp


def test_rpz_and_bind_onboarding_reports_use_wait_dialogs() -> None:
    rpz = inspect.getsource(CursesApp._rpz_status_view)
    onboarding = inspect.getsource(CursesApp._bind_onboarding_view)

    assert 'title=f"Status RPZ: {zone.name}"' in rpz
    assert "operation=lambda: BindEnvironmentReporter(" in rpz
    assert 'title="Rozpoznawanie BIND"' in onboarding
    assert "operation=lambda: BindOnboardingReporter(" in onboarding


def test_onboarding_refreshes_use_wait_dialogs() -> None:
    source = inspect.getsource(CursesApp._onboarding_summary_view)

    assert source.count('title="Odświeżanie onboardingu BIND"') == 2
    assert source.count("operation=lambda: self._refresh_onboarding_report(") == 2


def test_bulk_dnssec_audit_uses_wait_dialog() -> None:
    source = inspect.getsource(CursesApp._dnssec_onboarding_audit_view)

    assert 'title="Zbiorczy audyt DNSSEC"' in source
    assert "operation=lambda: DnssecOnboardingAuditor(" in source


def test_dnssec_import_pre_gate_uses_wait_dialog() -> None:
    source = inspect.getsource(CursesApp._commit_dnssec_onboarding_import)

    assert 'title=f"Bramka importu DNSSEC: {zone_name}"' in source
    assert "operation=lambda: self._dnssec_import_gate(zone_name)" in source
