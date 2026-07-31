from __future__ import annotations

import curses

from zonectl.ui.form_style import active_field_attr, field_marker


def test_active_field_has_monochrome_fallback(monkeypatch) -> None:
    monkeypatch.setattr(curses, "has_colors", lambda: False)

    attr = active_field_attr()

    assert attr & curses.A_REVERSE
    assert attr & curses.A_BOLD


def test_active_marker_is_visible_without_colour() -> None:
    assert field_marker(True) == "▶"
    assert field_marker(False) == " "
