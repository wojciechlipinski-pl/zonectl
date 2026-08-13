import inspect

from zonectl.ui.curses_app import CursesApp


def test_main_draw_enables_details_only_on_wide_terminals() -> None:
    source = inspect.getsource(CursesApp._draw)
    assert "panel_enabled = width >= 118" in source
    assert "_draw_zone_details_panel" in source
    assert "list_width" in source
    assert "if not panel_enabled" in source


def test_details_panel_uses_presentation_model_and_current_status() -> None:
    source = inspect.getsource(CursesApp._draw_zone_details_panel)
    assert "ZoneDetailsView.build(zone, status)" in source
    assert "self.statuses.get" in source
    assert "Wybierz strefę z listy" in source
    assert "commit" not in source.casefold()
    assert "activate" not in source.casefold()
