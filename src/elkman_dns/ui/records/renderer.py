from __future__ import annotations

import curses
from collections.abc import Sequence

from elkman_dns.core.zone_parser import DNSRecord
from elkman_dns.ui.records.keybindings import render_footer


class RecordRenderer:
    """Renderuje ekran rekordów DNS bez obsługi klawiatury."""

    LIST_TOP = 6
    FOOTER_LINES = 3

    @classmethod
    def visible_rows(cls, height: int) -> int:
        return max(1, height - cls.LIST_TOP - cls.FOOTER_LINES)

    @staticmethod
    def summary_text(
        *,
        visible_count: int,
        total_count: int,
        sort_name: str,
        change_count: int,
        search_query: str = "",
    ) -> str:
        summary = (
            f"Rekordy: {visible_count}/{total_count}"
            f"   Sortowanie: {sort_name}"
            f"   Zmiany: {change_count}"
        )
        if search_query:
            summary += f'   Filtr: "{search_query}"'
        return summary

    @staticmethod
    def footer_text() -> str:
        return render_footer()

    @staticmethod
    def _put(
        win: curses.window,
        row: int,
        column: int,
        text: str,
        attr: int = curses.A_NORMAL,
    ) -> None:
        height, width = win.getmaxyx()
        if row < 0 or row >= height or column < 0 or column >= width:
            return

        available = max(0, width - column - 1)
        if available <= 0:
            return

        try:
            win.addnstr(row, column, str(text), available, attr)
        except curses.error:
            pass

    @classmethod
    def draw(
        cls,
        win: curses.window,
        *,
        zone_name: str,
        records: Sequence[DNSRecord],
        total_count: int,
        selected: int,
        offset: int,
        sort_name: str,
        change_count: int,
        search_query: str = "",
        error: str | None = None,
        error_attr: int = curses.A_BOLD,
    ) -> None:
        height, width = win.getmaxyx()
        win.erase()

        cls._put(
            win,
            0,
            0,
            f" Rekordy DNS: {zone_name} ".ljust(width),
            curses.A_REVERSE | curses.A_BOLD,
        )

        if error:
            cls._put(
                win,
                3,
                2,
                "Nie udało się odczytać rekordów:",
                curses.A_BOLD,
            )
            cls._put(win, 5, 2, error, error_attr)
            cls._put(
                win,
                height - 2,
                0,
                " q/Esc/Backspace powrót ".ljust(width),
                curses.A_REVERSE,
            )
            win.refresh()
            return

        cls._put(
            win,
            2,
            2,
            cls.summary_text(
                visible_count=len(records),
                total_count=total_count,
                sort_name=sort_name,
                change_count=change_count,
                search_query=search_query,
            ),
            curses.A_BOLD,
        )

        owner_width = max(12, min(28, width // 4))
        type_width = 7
        ttl_width = 10

        owner_column = 1
        type_column = owner_column + owner_width + 1
        ttl_column = type_column + type_width + 1
        value_column = ttl_column + ttl_width + 1

        cls._put(win, 4, owner_column, "NAZWA", curses.A_BOLD)
        cls._put(win, 4, type_column, "TYP", curses.A_BOLD)
        cls._put(win, 4, ttl_column, "TTL", curses.A_BOLD)
        cls._put(win, 4, value_column, "WARTOŚĆ", curses.A_BOLD)
        cls._put(win, 5, 1, "-" * max(1, width - 2), curses.A_DIM)

        visible = cls.visible_rows(height)

        if records:
            for screen_row, record in enumerate(
                records[offset : offset + visible],
                start=cls.LIST_TOP,
            ):
                index = offset + screen_row - cls.LIST_TOP
                attr = (
                    curses.A_REVERSE
                    if index == selected
                    else curses.A_NORMAL
                )
                owner = record.relative_owner(zone_name)
                ttl = "-" if record.ttl is None else str(record.ttl)

                cls._put(
                    win,
                    screen_row,
                    owner_column,
                    owner[:owner_width].ljust(owner_width),
                    attr,
                )
                cls._put(
                    win,
                    screen_row,
                    type_column,
                    record.rtype[:type_width].ljust(type_width),
                    attr,
                )
                cls._put(
                    win,
                    screen_row,
                    ttl_column,
                    ttl[:ttl_width].ljust(ttl_width),
                    attr,
                )
                cls._put(
                    win,
                    screen_row,
                    value_column,
                    record.rdata,
                    attr,
                )
        elif search_query:
            cls._put(
                win,
                cls.LIST_TOP,
                2,
                f'Brak rekordów pasujących do: "{search_query}"',
                curses.A_DIM,
            )
        else:
            cls._put(
                win,
                cls.LIST_TOP,
                2,
                "Brak rekordów do wyświetlenia.",
                curses.A_DIM,
            )

        cls._put(
            win,
            height - 2,
            0,
            cls.footer_text().ljust(width),
            curses.A_REVERSE,
        )
        win.refresh()
