from __future__ import annotations

import curses


FORM_ACTIVE_PAIR = 5


def active_field_attr() -> int:
    """Return a high-contrast attribute, with a monochrome fallback."""
    try:
        if curses.has_colors():
            return curses.color_pair(FORM_ACTIVE_PAIR) | curses.A_BOLD
    except curses.error:
        pass
    return curses.A_REVERSE | curses.A_BOLD


def field_marker(active: bool) -> str:
    return "▶" if active else " "
