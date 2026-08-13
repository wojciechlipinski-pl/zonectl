import inspect

from zonectl.ui.curses_app import CursesApp


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
    assert "transaction.apply(plan, commit=True, activate=True)" in commit
    assert "self.read_only" in commit


def test_onboarding_lists_are_refreshed_after_import_views() -> None:
    summary = inspect.getsource(CursesApp._onboarding_summary_view)
    refresh = inspect.getsource(CursesApp._refresh_onboarding_report)
    assert summary.count("self._refresh_onboarding_report") == 2
    assert "BindOnboardingReporter" in refresh
    assert "BindOnboardingView.build" in refresh
