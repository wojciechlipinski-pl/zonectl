import inspect

from zonectl.ui.curses_app import CursesApp


def test_main_tui_routes_f3_to_contextual_preview() -> None:
    source = inspect.getsource(CursesApp._main)
    assert "key == curses.KEY_F3" in source
    assert "self._selected_zone_preview(stdscr)" in source


def test_rpz_preview_is_read_only_environment_report() -> None:
    preview = inspect.getsource(CursesApp._selected_zone_preview)
    status = inspect.getsource(CursesApp._rpz_status_view)
    assert 'zone.health_profile.casefold() != "rpz"' in preview
    assert "BindEnvironmentReporter" in status
    assert "RpzStatusView.build" in status
    assert "commit" not in status.casefold()
    assert "activate" not in status.casefold()
    assert "_message_view" in status


def test_main_footer_documents_mc_style_f3_preview() -> None:
    source = inspect.getsource(CursesApp._draw)
    assert "F3 podgląd" in source
