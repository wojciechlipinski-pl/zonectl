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


def test_legacy_candidates_only_offer_read_only_plan() -> None:
    candidates = inspect.getsource(CursesApp._onboarding_candidates_view)
    plan = inspect.getsource(CursesApp._show_bind_onboarding_plan)
    assert "F3 plan migracji" in candidates
    assert "planner.plan(zone_name)" in plan
    assert "Plan tylko do odczytu" in plan
    for forbidden in ("ManagedZoneMigrationTransaction", "commit=True", "activate=True"):
        assert forbidden not in candidates + plan
