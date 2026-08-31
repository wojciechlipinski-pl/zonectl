"""Dyskretny podpis twórców projektu w głównym widoku TUI."""

from __future__ import annotations

import curses


PROJECT_OWNER_LINES = (
    "Project Owner",
    "Wojciech Lipiński",
    "Domain Expert • QA • Product Design",
)

AI_DEVELOPMENT_LINES = (
    "AI-assisted Architecture & Development",
    "OpenAI ChatGPT",
)


def _safe_addnstr(
    window: curses.window,
    row: int,
    column: int,
    text: str,
    width: int,
    attributes: int = curses.A_NORMAL,
) -> None:
    """Rysuje tekst bez przerywania pracy przy małym terminalu."""
    if width <= 0 or row < 0 or column < 0:
        return

    try:
        window.addnstr(
            row,
            column,
            text,
            width,
            attributes,
        )
    except curses.error:
        pass


def draw_project_credits(window: curses.window) -> None:
    """
    Wyświetla dane twórców w prawym dolnym rogu głównego widoku.

    Podpis jest pomijany, gdy terminal jest zbyt mały, dzięki czemu
    nie nachodzi na listę domen ani dolny pasek klawiszy.
    """
    height, width = window.getmaxyx()

    left_block = PROJECT_OWNER_LINES
    right_block = AI_DEVELOPMENT_LINES

    gap = 5
    left_width = max(map(len, left_block))
    right_width = max(map(len, right_block))
    block_width = left_width + gap + right_width

    # Ostatni wiersz zajmuje pasek pomocy.
    footer_row = height - 1
    block_height = max(len(left_block), len(right_block))
    start_row = footer_row - block_height - 1
    start_column = width - block_width - 3

    # Nie pokazujemy podpisu, jeśli zabrakłoby bezpiecznej przestrzeni.
    if height < 16 or width < block_width + 8 or start_row < 8 or start_column < 2:
        return

    heading_attr = curses.A_BOLD | curses.A_DIM
    normal_attr = curses.A_DIM

    for offset, line in enumerate(left_block):
        attributes = heading_attr if offset == 0 else normal_attr
        _safe_addnstr(
            window,
            start_row + offset,
            start_column,
            line,
            left_width,
            attributes,
        )

    right_column = start_column + left_width + gap

    for offset, line in enumerate(right_block):
        attributes = heading_attr if offset == 0 else normal_attr
        _safe_addnstr(
            window,
            start_row + offset,
            right_column,
            line,
            right_width,
            attributes,
        )
