import inspect

from zonectl.ui.curses_app import CursesApp


def test_main_tui_opens_about_screen_with_f1() -> None:
    main = inspect.getsource(CursesApp._main)
    footer = inspect.getsource(CursesApp._draw_main_footer)
    about = inspect.getsource(CursesApp._about_view)
    assert "curses.KEY_F1" in main
    assert "self._about_view(stdscr)" in main
    assert '("F1", "O programie")' in footer
    assert "AboutView.build(__version__)" in about
    assert "_draw_about_identity" in about
    assert "_draw_about_history" in about
    assert "_draw_about_compact" in about
    assert "curses.ACS_VLINE" in about


def test_about_screen_uses_concept_sections() -> None:
    identity = inspect.getsource(CursesApp._draw_about_identity)
    history = inspect.getsource(CursesApp._draw_about_history)
    assert "AUTOR I WŁAŚCICIEL PROJEKTU" in identity
    assert "ROZWÓJ WSPOMAGANY PRZEZ AI" in identity
    assert "HISTORIA PROJEKTU" in history
    assert "github.com/wojciechlipinski-pl/zonectl" in history
