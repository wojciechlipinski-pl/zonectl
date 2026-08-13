import inspect

from zonectl.ui.curses_app import CursesApp


def test_domain_view_uses_published_responsive_layout() -> None:
    source = inspect.getsource(CursesApp._draw_domain_view_48)
    assert "width >= 100 and height >= 22" in source
    assert "Szczegóły strefy" in source
    assert "Stan operacyjny" in source
    assert "curses.ACS_HLINE" in source
    assert "curses.ACS_VLINE" in source
    assert "curses.color_pair(4)" in source
    assert "curses.color_pair(6)" in source


def test_domain_view_keeps_all_operational_actions() -> None:
    source = inspect.getsource(CursesApp._draw_domain_view_48)
    for key, label in (
        ("F3", "Rekordy"),
        ("F5", "Secondary"),
        ("F6", "Migracja"),
        ("d", "DNSSEC"),
        ("r", "Odśwież"),
        ("F10", "Powrót"),
    ):
        assert f'("{key}", "{label}")' in source
