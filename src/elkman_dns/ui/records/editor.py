"""Formularz edycji rekordów DNS w interfejsie curses."""

from __future__ import annotations

from typing import Any

import curses

from ...core.models import Zone


class RecordEditor:
    """Obsługuje formularz edycji pojedynczego rekordu DNS."""

    def __init__(self, error_attr: int = curses.A_BOLD) -> None:
        self._error_attr = error_attr

    def _edit_line(
        self,
        win: curses.window,
        row: int,
        column: int,
        initial_value: str,
        max_width: int,
    ) -> str | None:
        """Prosty edytor pojedynczej linii dla formularzy curses."""
        value = list(str(initial_value))
        cursor = len(value)
        offset = 0

        try:
            curses.curs_set(1)
        except curses.error:
            pass

        def adjust_offset() -> None:
            nonlocal offset

            visible_width = max(1, max_width)

            if cursor < offset:
                offset = cursor
            elif cursor >= offset + visible_width:
                offset = cursor - visible_width + 1

            offset = max(0, offset)

        try:
            while True:
                adjust_offset()

                visible_width = max(1, max_width)
                visible = "".join(
                    value[offset : offset + visible_width]
                )

                try:
                    win.move(row, column)
                    win.clrtoeol()
                    win.addnstr(
                        row,
                        column,
                        visible.ljust(visible_width),
                        visible_width,
                        curses.A_REVERSE,
                    )

                    cursor_column = column + cursor - offset
                    cursor_column = min(
                        column + visible_width - 1,
                        max(column, cursor_column),
                    )
                    win.move(row, cursor_column)
                except curses.error:
                    pass

                win.refresh()
                key = win.getch()

                if key in (10, 13, curses.KEY_ENTER):
                    return "".join(value)

                if key == 27:
                    return None

                if key == curses.KEY_LEFT:
                    cursor = max(0, cursor - 1)
                    continue

                if key == curses.KEY_RIGHT:
                    cursor = min(len(value), cursor + 1)
                    continue

                if key == curses.KEY_HOME:
                    cursor = 0
                    continue

                if key == curses.KEY_END:
                    cursor = len(value)
                    continue

                if key in (
                    curses.KEY_BACKSPACE,
                    8,
                    127,
                ):
                    if cursor > 0:
                        del value[cursor - 1]
                        cursor -= 1
                    continue

                if key == curses.KEY_DC:
                    if cursor < len(value):
                        del value[cursor]
                    continue

                if 32 <= key <= 126:
                    value.insert(cursor, chr(key))
                    cursor += 1
                    continue

                try:
                    character = chr(key)
                except (TypeError, ValueError):
                    continue

                if character.isprintable():
                    value.insert(cursor, character)
                    cursor += 1
        finally:
            try:
                curses.curs_set(0)
            except curses.error:
                pass

    def edit_record_dialog(
        self,
        win: curses.window,
        record,
        zone: Zone,
    ):
        """Edytuje rekord w pamięci. Zwraca nowy rekord albo None."""
        from dataclasses import replace

        fields = [
            ("Nazwa", record.relative_owner(zone.name)),
            ("Typ", record.rtype),
            ("TTL", "" if record.ttl is None else str(record.ttl)),
            ("Dane", record.rdata),
        ]
        values = [value for _, value in fields]
        active = 0
        message = ""

        def absolute_owner(value: str) -> str:
            value = value.strip()

            if value in ("", "@"):
                return zone.name.rstrip(".") + "."

            if value.endswith("."):
                return value

            return f"{value}.{zone.name.rstrip('.')}."

        while True:
            win.erase()
            height, width = win.getmaxyx()

            def put(
                row: int,
                column: int,
                text: str,
                attr: int = curses.A_NORMAL,
            ) -> None:
                if row < 0 or row >= height:
                    return
                if column < 0 or column >= width:
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

            put(
                0,
                0,
                f" Edycja rekordu: {zone.name} ".ljust(width),
                curses.A_REVERSE | curses.A_BOLD,
            )

            for index, ((label, _), value) in enumerate(
                zip(fields, values),
                start=0,
            ):
                row = 3 + index * 2
                attr = (
                    curses.A_REVERSE
                    if index == active
                    else curses.A_NORMAL
                )
                put(row, 2, f"{label:<8}: ", curses.A_BOLD)
                put(row, 13, value or "", attr)

            if message:
                put(12, 2, message, self._error_attr)

            footer = (
                " ↑/↓ pole"
                "   Enter edytuj"
                "   F2 zapisz"
                "   Esc anuluj "
            )
            put(
                height - 2,
                0,
                footer.ljust(width),
                curses.A_REVERSE,
            )

            win.refresh()
            key = win.getch()

            if key in (27, ord("q"), ord("Q")):
                return None

            if key in (curses.KEY_UP, ord("k")):
                active = max(0, active - 1)
                continue

            if key in (curses.KEY_DOWN, ord("j"), 9):
                active = min(len(values) - 1, active + 1)
                continue

            if key in (10, 13, curses.KEY_ENTER):
                row = 3 + active * 2

                edited_value = self._edit_line(
                    win=win,
                    row=row,
                    column=13,
                    initial_value=values[active],
                    max_width=max(1, width - 14),
                )

                if edited_value is not None:
                    values[active] = edited_value
                    message = ""

                continue

            if key == curses.KEY_F2:
                owner_value = values[0].strip()
                rtype_value = values[1].strip().upper()
                ttl_value = values[2].strip()
                rdata_value = values[3].strip()

                if not rtype_value:
                    message = "Typ rekordu nie może być pusty."
                    continue

                if not rdata_value:
                    message = "Dane rekordu nie mogą być puste."
                    continue

                try:
                    ttl = None if not ttl_value else int(ttl_value)
                except ValueError:
                    message = "TTL musi być liczbą całkowitą."
                    continue

                if ttl is not None and ttl < 0:
                    message = "TTL nie może być ujemny."
                    continue

                try:
                    return replace(
                        record,
                        owner=absolute_owner(owner_value),
                        rtype=rtype_value,
                        ttl=ttl,
                        rdata=rdata_value,
                    )
                except TypeError as exc:
                    message = f"Nie można utworzyć rekordu: {exc}"
