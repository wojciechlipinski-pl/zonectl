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
    assert "_show_bind_access_item" in source
    assert "_edit_secondary_group" in source


def test_secondary_edit_requires_plan_dry_run_and_exact_name() -> None:
    source = inspect.getsource(CursesApp._edit_secondary_group)

    assert "planner.plan(name, addresses)" in source
    assert "dry_run = transaction.apply(plan)" in source
    assert "Wpisz pełną nazwę grupy" in source
    assert "transaction.apply(plan, commit=True, activate=True)" in source


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

    assert 'kind != "secondary"' in source
    assert "Pełna edycja ACL będzie dodana" in source
