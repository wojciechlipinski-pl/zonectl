from __future__ import annotations

import inspect

from zonectl.ui.curses_app import CursesApp


def test_enter_keeps_rpz_record_preview_path() -> None:
    activate = inspect.getsource(CursesApp._activate)
    domain = inspect.getsource(CursesApp._domain_view)

    assert "self._domain_view(win, row.zone)" in activate
    assert "self._rpz_status_view" not in activate
    assert "if key == curses.KEY_F3:" in domain
    assert "self._records_view(win, zone)" in domain


def test_main_f3_routes_rpz_to_framed_status_report() -> None:
    source = inspect.getsource(CursesApp._selected_zone_preview)

    assert 'zone.health_profile.casefold() != "rpz"' in source
    assert "self._rpz_status_view(win, zone)" in source


def test_rpz_report_uses_shared_wait_dialog() -> None:
    source = inspect.getsource(CursesApp._rpz_status_view)

    assert "self._run_with_wait_indicator" in source
    assert 'title=f"Status RPZ: {zone.name}"' in source
    assert "BindEnvironmentReporter(" in source
    assert 'refresh_keys=(curses.KEY_F3, ord("r"), ord("R"))' in source


def test_message_view_can_return_refresh_without_changing_default_callers() -> None:
    source = inspect.getsource(CursesApp._message_view)

    assert "refresh_keys: Sequence[int] = ()" in source
    assert "elif key in refresh_keys:" in source
    assert "return True" in source
    assert "return False" in source
