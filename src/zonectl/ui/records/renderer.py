from __future__ import annotations

import curses
from collections.abc import Sequence

from zonectl.core.zone_model import ChangeKind, ZoneRecordView
from zonectl.ui.records.keybindings import RECORD_VIEW_BINDINGS, render_footer


class RecordRenderer:
    """Renderuje ekran rekordów DNS bez obsługi klawiatury."""

    LIST_TOP = 6
    FOOTER_LINES = 3

    @classmethod
    def panel_enabled(cls, height: int, width: int) -> bool:
        return width >= 118 and height >= 28

    @classmethod
    def details_height(cls, height: int, width: int) -> int:
        if not cls.panel_enabled(height, width):
            return 0
        return max(
            9,
            (height - cls.LIST_TOP - cls.FOOTER_LINES) // 3,
        )

    @classmethod
    def visible_rows(cls, height: int, width: int = 0) -> int:
        panel = cls.details_height(height, width)
        return max(
            1,
            height
            - cls.LIST_TOP
            - cls.FOOTER_LINES
            - panel
            - (1 if panel else 0),
        )

    @staticmethod
    def summary_text(
        *,
        visible_count: int,
        total_count: int,
        sort_name: str,
        change_count: int,
        search_query: str = "",
        read_only: bool = False,
    ) -> str:
        summary = (
            f"Rekordy: {visible_count}/{total_count}"
            f"   Sortowanie: {sort_name}"
            f"   Zmiany: {change_count}"
        )

        if search_query:
            summary += f'   Filtr: "{search_query}"'

        if read_only:
            summary += "   TYLKO ODCZYT"

        return summary

    @staticmethod
    def footer_text(*, read_only: bool = False) -> str:
        return render_footer(read_only=read_only)

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
            win.addnstr(
                row,
                column,
                str(text),
                available,
                attr,
            )
        except curses.error:
            pass

    @staticmethod
    def _change_attr(view: ZoneRecordView) -> int:
        if view.change_kind is ChangeKind.ADD:
            return curses.A_BOLD

        if view.change_kind is ChangeKind.MODIFY:
            return curses.A_BOLD

        if view.change_kind is ChangeKind.DELETE:
            return curses.A_DIM

        return curses.A_NORMAL

    @classmethod
    def _draw_footer(
        cls,
        win: curses.window,
        row: int,
        width: int,
        *,
        read_only: bool,
    ) -> None:
        bindings = tuple(
            binding for binding in RECORD_VIEW_BINDINGS
            if not read_only
            or binding.key not in {"Ins", "F4", "Del", "b", "u", "F2"}
        )
        cls._put(win, row, 0, " " * width, curses.A_REVERSE)
        column = 1
        key_attr = (
            curses.color_pair(6) | curses.A_DIM
            if curses.has_colors()
            else curses.A_REVERSE | curses.A_BOLD
        )
        for binding in bindings:
            segment = f"{binding.key} {binding.description}  "
            if column + len(segment) >= width:
                break
            cls._put(win, row, column, binding.key, key_attr)
            column += len(binding.key)
            label = f" {binding.description}  "
            cls._put(win, row, column, label, curses.A_REVERSE)
            column += len(label)

    @classmethod
    def _draw_details_panel(
        cls, win: curses.window, *, top: int, height: int, width: int,
        zone_name: str, view: ZoneRecordView | None, change_count: int,
    ) -> None:
        try:
            for column in range(width - 1):
                win.addch(top - 1, column, curses.ACS_HLINE, curses.A_DIM)
        except curses.error:
            pass
        divider = min(max(54, width * 2 // 3), width - 28)
        heading = curses.A_BOLD | (curses.color_pair(4) if curses.has_colors() else 0)
        cls._put(win, top, 2, " Szczegóły rekordu ", heading)
        cls._put(win, top, divider + 2, " Stan operacyjny ", heading)
        try:
            for row in range(top + 1, top + height):
                win.addch(row, divider, curses.ACS_VLINE, curses.A_DIM)
        except curses.error:
            pass
        if view is None:
            cls._put(win, top + 2, 2, "Wybierz rekord z listy.")
        else:
            record = view.record
            lines = (
                f"Nazwa          {record.relative_owner(zone_name)}",
                f"Typ            {record.rtype}",
                f"TTL            {'-' if record.ttl is None else record.ttl}",
                f"Wartość        {record.rdata}",
            )
            for index, line in enumerate(lines, start=2):
                cls._put(win, top + index, 2, line[: max(1, divider - 4)])
        state = (
            "USUNIĘTY"
            if view and view.deleted
            else "ZMIENIONY"
            if view and view.change_kind
            else "BEZ ZMIAN"
        )
        cls._put(win, top + 2, divider + 2, f"Status         {state}", curses.A_BOLD)
        cls._put(win, top + 3, divider + 2, f"Zmiany strefy  {change_count}")

    @classmethod
    def draw(
        cls,
        win: curses.window,
        *,
        zone_name: str,
        records: Sequence[ZoneRecordView],
        total_count: int,
        selected: int,
        offset: int,
        sort_name: str,
        change_count: int,
        search_query: str = "",
        read_only: bool = False,
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
            cls._put(
                win,
                5,
                2,
                error,
                error_attr,
            )
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
                read_only=read_only,
            ),
            curses.A_BOLD,
        )

        marker_width = 1
        owner_width = max(12, min(28, width // 4))
        type_width = 7
        ttl_width = 10

        marker_column = 1
        owner_column = marker_column + marker_width + 1
        type_column = owner_column + owner_width + 1
        ttl_column = type_column + type_width + 1
        value_column = ttl_column + ttl_width + 1

        cls._put(
            win,
            4,
            marker_column,
            "S",
            curses.A_BOLD,
        )
        cls._put(
            win,
            4,
            owner_column,
            "NAZWA",
            curses.A_BOLD,
        )
        cls._put(
            win,
            4,
            type_column,
            "TYP",
            curses.A_BOLD,
        )
        cls._put(
            win,
            4,
            ttl_column,
            "TTL",
            curses.A_BOLD,
        )
        cls._put(
            win,
            4,
            value_column,
            "WARTOŚĆ",
            curses.A_BOLD,
        )
        cls._put(
            win,
            5,
            1,
            "-" * max(1, width - 2),
            curses.A_DIM,
        )

        visible = cls.visible_rows(height, width)

        if records:
            for screen_row, view in enumerate(
                records[offset : offset + visible],
                start=cls.LIST_TOP,
            ):
                index = offset + screen_row - cls.LIST_TOP
                record = view.record

                attr = cls._change_attr(view)

                if index == selected:
                    attr = (
                        curses.color_pair(5) | curses.A_BOLD
                        if curses.has_colors()
                        else attr | curses.A_REVERSE
                    )

                owner = record.relative_owner(zone_name)
                ttl = "-" if record.ttl is None else str(record.ttl)

                cls._put(
                    win,
                    screen_row,
                    marker_column,
                    view.marker,
                    attr,
                )
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

        if cls.panel_enabled(height, width):
            selected_view = (
                records[selected]
                if records and 0 <= selected < len(records)
                else None
            )
            cls._draw_details_panel(
                win, top=cls.LIST_TOP + visible + 1,
                height=cls.details_height(height, width), width=width,
                zone_name=zone_name, view=selected_view, change_count=change_count,
            )
        cls._draw_footer(win, height - 2, width, read_only=read_only)
        win.refresh()
