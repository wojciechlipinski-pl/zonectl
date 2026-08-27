import inspect
from types import SimpleNamespace

from zonectl.ui.curses_app import CursesApp


class _SummaryWindow:
    def timeout(self, _value):
        pass

    def erase(self):
        pass

    def getmaxyx(self):
        return 30, 120

    def addnstr(self, *_args):
        pass

    def refresh(self):
        pass


def test_onboarding_summary_computes_wide_layout_before_visible_rows(
    monkeypatch,
) -> None:
    app = CursesApp.__new__(CursesApp)
    report = SimpleNamespace(candidates=(), blockers=())
    view = SimpleNamespace(title="Środowisko", lines=("Status: PASS",))
    monkeypatch.setattr(app, "_get_key", lambda _win: ord("q"))
    monkeypatch.setattr(app, "_draw_onboarding_summary_48", lambda *_args: None)

    app._onboarding_summary_view(_SummaryWindow(), view, report)


def test_main_tui_opens_environment_report_with_f2() -> None:
    main = inspect.getsource(CursesApp._main)
    footer = inspect.getsource(CursesApp._draw_main_footer)
    assert "curses.KEY_F2" in main
    assert "self._bind_onboarding_view(stdscr)" in main
    assert '("F2", "Środowisko")' in footer


def test_environment_view_has_no_write_workflow() -> None:
    source = inspect.getsource(CursesApp._bind_onboarding_view)
    assert "BindOnboardingReporter" in source
    assert "BindOnboardingView" in source
    for forbidden in ("--commit", "--activate", ".apply(", ".write_"):
        assert forbidden not in source


def test_environment_summary_uses_responsive_48_layout() -> None:
    summary = inspect.getsource(CursesApp._onboarding_summary_view)
    renderer = inspect.getsource(CursesApp._draw_onboarding_summary_48)
    assert "width >= 100 and height >= 24" in summary
    assert "WYKRYTE ŚRODOWISKO" in renderer
    assert "KLASYFIKACJA" in renderer
    assert "STAN OPERACYJNY" in renderer
    assert "KONFIGURACJA WSPÓŁDZIELONA" in renderer
    assert "NASTĘPNY KROK" in renderer
    assert "curses.ACS_HLINE" in renderer
    assert "curses.ACS_VLINE" in renderer
    assert "win.erase()" in renderer


def test_environment_summary_keeps_compact_fallback_and_read_only_actions() -> None:
    summary = inspect.getsource(CursesApp._onboarding_summary_view)
    footer = inspect.getsource(CursesApp._onboarding_footer)
    assert "self._wrap_message_lines" in summary
    assert "Enter LEGACY" in footer
    assert "F5 DNSSEC" in footer
    assert "self._draw_onboarding_summary_48" in summary


def test_environment_footer_hides_unavailable_legacy_action() -> None:
    dnssec = SimpleNamespace(category="DNSSEC")
    report = SimpleNamespace(candidates=(), blockers=(dnssec,))
    footer = CursesApp._onboarding_footer(report)
    assert "Enter LEGACY" not in footer
    assert "F5 DNSSEC" in footer


def test_environment_footer_hides_all_empty_profile_actions() -> None:
    report = SimpleNamespace(candidates=(), blockers=())
    footer = CursesApp._onboarding_footer(report)
    assert "Enter LEGACY" not in footer
    assert "F5 DNSSEC" not in footer
    assert "F10 Powrót" in footer


def test_legacy_candidates_offer_plan_and_dry_run_only() -> None:
    candidates = inspect.getsource(CursesApp._onboarding_candidates_view)
    plan = inspect.getsource(CursesApp._show_bind_onboarding_plan)
    dry_run = inspect.getsource(CursesApp._dry_run_bind_onboarding_import)
    assert "F3 plan" in candidates
    assert "F4 dry-run" in candidates
    assert "planner.plan(zone_name)" in plan
    assert "Plan tylko do odczytu" in plan
    assert "ManagedZoneMigrationTransaction" in dry_run
    assert "transaction.apply(plan)" in dry_run
    assert "nie przeładowano BIND" in dry_run
    for forbidden in ("commit=True", "activate=True"):
        assert forbidden not in candidates + plan + dry_run


def test_guarded_import_requires_dry_run_name_and_confirmation() -> None:
    candidates = inspect.getsource(CursesApp._onboarding_candidates_view)
    commit = inspect.getsource(CursesApp._commit_bind_onboarding_import)
    assert "F6 importuj" in candidates
    assert "transaction.apply(plan)" in commit
    assert "Wpisz pełną nazwę strefy" in commit
    assert "CursesDialogs.confirm" in commit
    assert "self._run_with_wait_indicator" in commit
    assert "commit=True, activate=True" in commit
    assert "self.read_only" in commit


def test_onboarding_lists_are_refreshed_after_import_views() -> None:
    summary = inspect.getsource(CursesApp._onboarding_summary_view)
    refresh = inspect.getsource(CursesApp._refresh_onboarding_report)
    assert summary.count("self._refresh_onboarding_report") == 2
    assert "BindOnboardingReporter" in refresh
    assert "BindOnboardingView.build" in refresh


def test_import_results_use_responsive_48_transaction_layout() -> None:
    renderer = inspect.getsource(CursesApp._onboarding_result_view)
    dry_run = inspect.getsource(CursesApp._dry_run_bind_onboarding_import)
    commit = inspect.getsource(CursesApp._commit_bind_onboarding_import)
    assert "width >= 100 and height >= 20" in renderer
    assert "TRANSAKCJA" in renderer
    assert "ETAPY" in renderer
    assert "STAN OPERACYJNY" in renderer
    assert "curses.ACS_VLINE" in renderer
    assert "OPERACJA ZAKOŃCZONA" in renderer
    assert "KONTROLA BEZ ZMIAN" in renderer
    assert "_onboarding_result_view" in dry_run
    assert "_onboarding_result_view" in commit
