import inspect

from zonectl.ui.curses_app import CursesApp


def test_main_draw_enables_details_only_on_wide_terminals() -> None:
    source = inspect.getsource(CursesApp._draw)
    assert "panel_enabled = width >= 118 and height >= 28" in source
    assert "_draw_zone_details_panel" in source
    assert "details_height" in source
    assert "if not panel_enabled" in source
    assert "SOA / wiek" in source
    assert "curses.ACS_HLINE" in source
    assert "curses.color_pair(5)" in source


def test_details_panel_uses_presentation_model_and_current_status() -> None:
    source = inspect.getsource(CursesApp._draw_zone_details_panel)
    assert "ZoneDetailsView.build(zone, status)" in source
    assert "self.statuses.get" in source
    assert "Wybierz strefę z listy" in source
    assert "commit" not in source.casefold()
    assert "activate" not in source.casefold()
    assert "curses.ACS_HLINE" in source
    assert "summary_lines" in source


def test_main_footer_matches_published_mc_key_model() -> None:
    source = inspect.getsource(CursesApp._draw_main_footer)
    for key in ("F3", "F4", "Insert", "r", "F9", "F10"):
        assert f'("{key}",' in source
    assert '("r", "Odśwież")' in source
    assert '("F8",' not in source
    assert "curses.color_pair(6)" in source
    assert "curses.color_pair(6) | curses.A_BOLD" not in source


def test_mc_footer_uses_xterm_teal_with_dim_cyan_fallback() -> None:
    source = inspect.getsource(CursesApp._init_colors)
    assert "footer_key_color = curses.COLOR_CYAN" in source
    assert "curses.COLORS >= 256" in source
    assert "footer_key_color = 30" in source
    assert "curses.can_change_color()" in source
    assert "curses.init_color(footer_key_color, 0, 430, 470)" in source
    assert "curses.init_pair(6, footer_key_color, curses.COLOR_WHITE)" in source
    footer = inspect.getsource(CursesApp._draw_main_footer)
    assert "curses.color_pair(6) | curses.A_DIM" in footer


def test_f4_opens_zone_editor_but_keeps_rpz_read_only() -> None:
    main = inspect.getsource(CursesApp._main)
    edit = inspect.getsource(CursesApp._selected_zone_edit)
    assert "key == curses.KEY_F4" in main
    assert "self._selected_zone_edit(stdscr)" in main
    assert "self._domain_view(win, zone)" in edit
    assert 'zone.health_profile.casefold() == "rpz"' in edit
    assert "tylko odczyt" in edit
