import curses
import inspect

from zonectl.ui.curses_app import CursesApp


def test_f9_opens_bind_access_browser() -> None:
    source = inspect.getsource(CursesApp._main)

    assert "curses.KEY_F9" in source
    assert "self._bind_access_view(stdscr)" in source


def test_bind_access_browser_uses_midnight_commander_keys() -> None:
    source = inspect.getsource(CursesApp._bind_access_view)

    assert "curses.KEY_F3" in source
    assert "curses.KEY_F4" in source
    assert "curses.KEY_F5" in source
    assert "_show_bind_access_item" in source
    assert "_show_secondary_health" in source
    assert "_edit_secondary_group" in source


def test_secondary_edit_requires_plan_dry_run_and_exact_name() -> None:
    source = inspect.getsource(CursesApp._edit_secondary_group)

    assert "planner.plan(name, addresses)" in source
    assert "dry_run = self._run_with_wait_indicator" in source
    assert "transaction.apply(plan)" in source
    assert "Wpisz pełną nazwę grupy" in source
    assert "commit=True, activate=True" in source
    assert "Powód zmiany secondary" in source
    assert ").strip()" in source
    assert "reason=reason" in source


def test_secondary_address_editor_uses_mc_keybindings() -> None:
    source = inspect.getsource(CursesApp._secondary_address_editor)

    assert "curses.KEY_IC" in source
    assert "curses.KEY_F4" in source
    assert "curses.KEY_F8" in source
    assert "curses.KEY_DC" in source
    assert "curses.KEY_F2" in source
    assert "Brak zmian do zaplanowania" in source


def test_acl_write_is_not_mixed_with_secondary_transaction() -> None:
    source = inspect.getsource(CursesApp._bind_access_view)

    assert 'kind == "acl"' in source
    assert "self._edit_acl" in source


def test_acl_editor_uses_mc_keys_and_guarded_transaction() -> None:
    editor = inspect.getsource(CursesApp._acl_entry_editor)
    workflow = inspect.getsource(CursesApp._edit_acl)

    for key in ("KEY_IC", "KEY_F4", "KEY_F8", "KEY_DC", "KEY_F2"):
        assert key in editor
    assert "entries=entries" in workflow
    assert "dry_run = self._run_with_wait_indicator" in workflow
    assert "transaction.apply(plan)" in workflow
    assert "Wpisz pełną nazwę ACL" in workflow
    assert "commit=True, activate=True" in workflow
    assert "Powód zmiany ACL" in workflow
    assert ").strip()" in workflow
    assert "reason=reason" in workflow


def test_bind_access_tui_presents_impact_risk_and_operational_health() -> None:
    impact = inspect.getsource(CursesApp._impact_lines)
    health = inspect.getsource(CursesApp._show_secondary_health)

    assert "Ryzyko" in impact
    assert "Dodawane" in impact
    assert "Usuwane" in impact
    assert "BLOKADY" in impact
    assert "BindSecondaryHealthGate" in health
    assert "TYLKO ODCZYT" in health


def test_zone_details_open_secondary_assignment_with_f5() -> None:
    details = inspect.getsource(CursesApp._domain_view)
    workflow = inspect.getsource(CursesApp._zone_secondary_view)
    assert "curses.KEY_F5" in details
    assert "_zone_secondary_view" in details
    assert "planner.plan(zone.name" in workflow
    assert "operation=lambda: transaction.apply(" in workflow
    assert "plan.transaction_plan()" in workflow
    assert "commit=True, activate=True" in workflow
