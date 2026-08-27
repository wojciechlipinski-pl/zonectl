from __future__ import annotations

import inspect

from zonectl.ui.curses_app import CursesApp


def test_acl_commit_uses_shared_wait_dialog() -> None:
    source = inspect.getsource(CursesApp._edit_acl)

    assert "self._run_with_wait_indicator" in source
    assert 'title=f"Transakcja ACL: {name}"' in source
    assert 'label="Walidacja, aktywacja i kontrola BIND"' in source
    assert "commit=True" in source
    assert "activate=True" in source
    assert "reason=reason" in source


def test_secondary_group_commit_uses_shared_wait_dialog() -> None:
    source = inspect.getsource(CursesApp._edit_secondary_group)

    assert "self._run_with_wait_indicator" in source
    assert 'title=f"Transakcja secondary: {name}"' in source
    assert 'label="Walidacja, aktywacja i kontrola BIND"' in source
    assert "commit=True" in source
    assert "activate=True" in source
    assert "reason=reason" in source


def test_zone_secondary_assignment_uses_shared_wait_dialog() -> None:
    source = inspect.getsource(CursesApp._zone_secondary_view)

    assert "self._run_with_wait_indicator" in source
    assert 'title=f"Przypisanie secondary: {zone.name}"' in source
    assert 'label="Walidacja, aktywacja i kontrola BIND"' in source
    assert "plan.transaction_plan()" in source
    assert "commit=True" in source
    assert "activate=True" in source
