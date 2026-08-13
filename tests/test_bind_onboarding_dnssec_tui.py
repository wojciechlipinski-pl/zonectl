import inspect

from zonectl.ui.curses_app import CursesApp


def test_onboarding_summary_routes_f5_to_dnssec_profile() -> None:
    summary = inspect.getsource(CursesApp._onboarding_summary_view)
    footer = inspect.getsource(CursesApp._onboarding_footer)
    view = inspect.getsource(CursesApp._onboarding_dnssec_view)
    assert "F5 DNSSEC" in footer
    assert "item.category == \"DNSSEC\"" in summary
    assert "F3 plan" in view
    assert "F4 dry-run" in view
    assert "F6 importuj" in view


def test_dnssec_profile_only_plans_and_dry_runs() -> None:
    plan = inspect.getsource(CursesApp._show_dnssec_onboarding_plan)
    dry_run = inspect.getsource(CursesApp._dry_run_dnssec_onboarding_import)
    assert "allow_dnssec=True" in plan
    assert "Klucze, dnssec-policy, KASP i DS nie zostaną zmienione" in plan
    assert "transaction.apply(plan)" in dry_run
    for forbidden in ("commit=True", "activate=True", "checkds", "confirm-ds"):
        assert forbidden not in plan + dry_run


def test_dnssec_commit_has_fresh_gates_and_transactional_rollback_path() -> None:
    gate = inspect.getsource(CursesApp._dnssec_import_gate)
    commit = inspect.getsource(CursesApp._commit_dnssec_onboarding_import)
    assert 'report.status != "PASS"' in gate
    assert 'delegation.status != "PASS"' in gate
    assert "report.parent_ds_matches" in gate
    assert "delegation.kasp_ready" in gate
    assert "Wpisz pełną nazwę strefy DNSSEC" in commit
    assert "loaded_verifier=verify_dnssec" in commit
    assert "after == before" in commit
    assert "transaction.apply(plan, commit=True, activate=True)" in commit


def test_dnssec_import_results_use_shared_transaction_layout() -> None:
    dry_run = inspect.getsource(CursesApp._dry_run_dnssec_onboarding_import)
    commit = inspect.getsource(CursesApp._commit_dnssec_onboarding_import)
    assert "_onboarding_result_view" in dry_run
    assert "_onboarding_result_view" in commit
    assert 'profile="DNSSEC"' in dry_run
    assert 'profile="DNSSEC"' in commit


def test_dnssec_candidate_list_uses_responsive_48_layout() -> None:
    listing = inspect.getsource(CursesApp._onboarding_dnssec_view)
    renderer = inspect.getsource(CursesApp._draw_dnssec_onboarding_48)
    assert "width >= 100 and height >= 24" in listing
    assert "self._draw_dnssec_onboarding_48" in listing
    assert "STAN OPERACYJNY" in renderer
    assert "KASP" in renderer
    assert "DS" in renderer
    assert "curses.ACS_HLINE" in renderer
    assert "curses.ACS_VLINE" in renderer
