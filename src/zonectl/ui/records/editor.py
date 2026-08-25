"""Formularz edycji rekordów DNS w interfejsie curses."""

from __future__ import annotations

from typing import Any

import curses

from ...core.models import Zone
from ...core.record_validation import (
    SUPPORTED_RECORD_TYPES,
    validate_rdata,
)
from ...core.zone_parser import DNSRecord
from ..function_keys import decode_function_key
from ..form_style import active_field_attr, field_marker


class RecordEditor:
    """Obsługuje formularz edycji pojedynczego rekordu DNS."""

    def __init__(self, error_attr: int = curses.A_BOLD) -> None:
        self._error_attr = error_attr
        self._save_requested = False

    @staticmethod
    def _owner_from_form(
        value: str,
        record: DNSRecord,
        zone: Zone,
    ) -> str:
        """Zachowaj źródłową postać właściciela, jeśli jej nie zmieniono."""
        value = value.strip()
        original_relative = record.relative_owner(zone.name)

        if value.casefold() == original_relative.casefold():
            return record.owner

        if value in ("", "@"):
            return zone.name.rstrip(".") + "."

        if value.endswith("."):
            return value

        return f"{value}.{zone.name.rstrip('.')}."

    @staticmethod
    def _get_key(win: curses.window) -> int:
        """Odczytuje klawisz i rozpoznaje F2 wysyłane jako ESC [ 12 ~."""
        key = win.getch()

        if key != 27:
            return key

        sequence: list[int] = []

        try:
            # Krótko czekamy na dalszą część sekwencji ESC.
            win.timeout(80)

            for _ in range(4):
                next_key = win.getch()

                if next_key == -1:
                    break

                sequence.append(next_key)
        finally:
            try:
                win.timeout(-1)
            except curses.error:
                pass

        function_key = decode_function_key(sequence)

        if function_key is not None:
            return function_key

        # To nie było F2. Odtwarzamy pobrane znaki,
        # a samo ESC zwracamy jako anulowanie.
        for item in reversed(sequence):
            try:
                curses.ungetch(item)
            except curses.error:
                break

        return 27

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
                        active_field_attr(),
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
                key = self._get_key(win)

                if key == curses.KEY_F2:
                    self._save_requested = True
                    return "".join(value)

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

    def create_record_dialog(
        self,
        win: curses.window,
        zone: Zone,
    ) -> DNSRecord | None:
        """Tworzy nowy rekord, wykorzystując formularz edycji."""
        template = DNSRecord(
            owner=zone.name.rstrip(".") + ".",
            ttl=None,
            rrclass="IN",
            rtype="A",
            rdata="",
            raw="",
        )

        return self.edit_record_dialog(
            win,
            template,
            zone,
        )

    def edit_record_dialog(
        self,
        win: curses.window,
        record: DNSRecord,
        zone: Zone,
    ) -> DNSRecord | None:
        """Edytuje rekord w pamięci. Zwraca nowy rekord albo None."""
        from dataclasses import replace

        if record.rtype.upper() == "SOA":
            return self.edit_soa_dialog(win, record, zone)

        self._save_requested = False

        # Formularz musi pracować w trybie blokującym.
        # W trybie nodelay sekwencje klawiszy funkcyjnych, np. F2,
        # mogą zostać odczytane jako osobne znaki ESC, [, 1, 2, ~.
        try:
            win.keypad(True)
            win.nodelay(False)
            win.timeout(-1)
        except curses.error:
            pass

        fields = [
            ("Nazwa", record.relative_owner(zone.name)),
            ("Typ", record.rtype),
            ("TTL", "" if record.ttl is None else str(record.ttl)),
            ("Dane", record.rdata),
        ]
        values = [value for _, value in fields]
        active = 0
        message = ""

        def build_record() -> tuple[DNSRecord | None, str]:
            owner_value = values[0].strip()
            rtype_value = values[1].strip().upper()
            ttl_value = values[2].strip()
            rdata_value = values[3].strip()

            if not rtype_value:
                return None, "Typ rekordu nie może być pusty."

            if rtype_value not in SUPPORTED_RECORD_TYPES:
                return None, "Nieobsługiwany typ rekordu."

            try:
                ttl = None if not ttl_value else int(ttl_value)
            except ValueError:
                return None, "TTL musi być liczbą całkowitą."

            if ttl is not None and not 0 <= ttl <= 2147483647:
                return None, "TTL musi mieć zakres 0–2147483647."

            validation_error = validate_rdata(
                rtype_value,
                rdata_value,
            )
            if validation_error:
                return None, validation_error

            try:
                updated_record = replace(
                    record,
                    owner=self._owner_from_form(
                        owner_value,
                        record,
                        zone,
                    ),
                    rtype=rtype_value,
                    ttl=ttl,
                    rdata=rdata_value,
                )
            except TypeError as exc:
                return None, f"Nie można utworzyć rekordu: {exc}"

            return updated_record, ""

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
                is_active = index == active
                attr = active_field_attr() if is_active else curses.A_NORMAL
                put(row, 0, field_marker(is_active), attr)
                put(
                    row,
                    2,
                    f"{label:<8}: ",
                    attr if is_active else curses.A_BOLD,
                )
                put(row, 13, (value or "").ljust(max(1, width - 15)), attr)

            put(
                11,
                2,
                f"Aktywne pole: {fields[active][0]}",
                active_field_attr(),
            )

            if message:
                put(12, 2, message, self._error_attr)

            wide = width >= 100 and height >= 20
            divider = max(62, min(width - 38, int(width * 0.68)))
            if wide:
                try:
                    has_colors = curses.has_colors()
                except curses.error:
                    has_colors = False
                heading_attr = curses.A_BOLD | (
                    curses.color_pair(4)
                    if has_colors else curses.A_NORMAL
                )
                try:
                    for row in range(2, height - 2):
                        win.addnstr(
                            row, divider + 1, " " * (width - divider - 2),
                            width - divider - 2,
                        )
                        win.addch(row, divider, curses.ACS_VLINE, curses.A_DIM)
                except curses.error:
                    pass
                right = divider + 3
                right_width = max(1, width - right - 3)
                put(2, right, "PODGLĄD REKORDU", heading_attr)
                preview = (
                    ("Strefa", zone.name),
                    ("Nazwa", values[0] or "@"),
                    ("Typ", values[1] or "-"),
                    ("TTL", values[2] or "domyślny"),
                    ("Dane", values[3] or "-"),
                    ("Stan", "BŁĄD" if message else "EDYCJA"),
                )
                panel_row = 4
                for label, value in preview:
                    put(panel_row, right, label)
                    for part in [str(value)[i:i + max(1, right_width - 13)] for i in range(0, max(1, len(str(value))), max(1, right_width - 13))]:
                        put(panel_row, right + 13, part)
                        panel_row += 1
                    panel_row += 1

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
            key = self._get_key(win)

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
                self._save_requested = False

                edited_value = self._edit_line(
                    win=win,
                    row=row,
                    column=13,
                    initial_value=values[active],
                    max_width=max(
                        1,
                        (divider - 15) if width >= 100 and height >= 20
                        else width - 14,
                    ),
                )

                if edited_value is not None:
                    values[active] = edited_value
                    message = ""

                    if self._save_requested:
                        self._save_requested = False
                        updated_record, message = build_record()

                        if updated_record is not None:
                            return updated_record

                        continue

                    if active < len(values) - 1:
                        active += 1

                continue

            if key == curses.KEY_F2:
                updated_record, message = build_record()

                if updated_record is not None:
                    return updated_record

    @staticmethod
    def _soa_values(record: DNSRecord) -> tuple[list[str] | None, str]:
        fields = record.rdata.replace("(", " ").replace(")", " ").split()
        if len(fields) != 7:
            return None, (
                "Rekord SOA nie zawiera siedmiu wymaganych pól; "
                "edycja została zablokowana."
            )
        return fields, ""

    @staticmethod
    def build_soa_record(
        record: DNSRecord,
        *,
        primary: str,
        administrator: str,
        refresh: str,
        retry: str,
        expire: str,
        minimum: str,
        ttl_text: str,
    ) -> tuple[DNSRecord | None, str]:
        """Zbuduj SOA, zachowując serial zarządzany automatycznie."""
        from dataclasses import replace

        soa, error = RecordEditor._soa_values(record)
        if soa is None:
            return None, error

        ttl_value = ttl_text.strip()
        try:
            ttl = None if not ttl_value else int(ttl_value)
        except ValueError:
            return None, "TTL musi być liczbą całkowitą albo pozostać pusty."
        if ttl is not None and not 0 <= ttl <= 2147483647:
            return None, "TTL musi mieć zakres 0–2147483647."

        rdata = " ".join((
            primary.strip(), administrator.strip(), soa[2],
            refresh.strip(), retry.strip(), expire.strip(), minimum.strip(),
        ))
        validation_error = validate_rdata("SOA", rdata)
        if validation_error:
            return None, validation_error
        return replace(record, ttl=ttl, rdata=rdata), ""

    def edit_soa_dialog(
        self,
        win: curses.window,
        record: DNSRecord,
        zone: Zone,
    ) -> DNSRecord | None:
        """Edytuj SOA w osobnych polach bez ręcznej zmiany serialu."""
        soa, _ = self._soa_values(record)
        if soa is None:
            return None

        labels = (
            "Primary NS", "Administrator", "Refresh", "Retry",
            "Expire", "Minimum", "TTL",
        )
        values = [
            soa[0], soa[1], soa[3], soa[4], soa[5], soa[6],
            "" if record.ttl is None else str(record.ttl),
        ]
        active = 0
        message = ""
        self._save_requested = False

        try:
            win.keypad(True)
            win.nodelay(False)
            win.timeout(-1)
        except curses.error:
            pass

        def build() -> tuple[DNSRecord | None, str]:
            return self.build_soa_record(
                record,
                primary=values[0], administrator=values[1],
                refresh=values[2], retry=values[3], expire=values[4],
                minimum=values[5], ttl_text=values[6],
            )

        try:
            while True:
                win.erase()
                height, width = win.getmaxyx()

                def put(row: int, column: int, text: str, attr: int = 0) -> None:
                    if not (0 <= row < height and 0 <= column < width):
                        return
                    try:
                        win.addnstr(
                            row, column, str(text),
                            max(0, width - column - 1), attr,
                        )
                    except curses.error:
                        pass

                put(0, 0, f" Edycja SOA: {zone.name} ".ljust(width),
                    curses.A_REVERSE | curses.A_BOLD)
                put(2, 2, "Serial", curses.A_BOLD)
                put(2, 20, f"{soa[2]} (automatycznie podbijany przy zapisie)")
                for index, (label, value) in enumerate(zip(labels, values)):
                    row = 4 + index * 2
                    selected = index == active
                    attr = active_field_attr() if selected else curses.A_NORMAL
                    put(row, 0, field_marker(selected), attr)
                    put(row, 2, f"{label:<15}: ",
                        attr if selected else curses.A_BOLD)
                    put(row, 20, value, attr)
                if message:
                    put(height - 4, 2, message, self._error_attr)
                put(height - 2, 0,
                    " ↑/↓ pole   Enter edytuj   F2 zatwierdź zmianę   Esc anuluj ".ljust(width),
                    curses.A_REVERSE)
                win.refresh()
                key = self._get_key(win)

                if key in (27, ord("q"), ord("Q")):
                    return None
                if key in (curses.KEY_UP, ord("k")):
                    active = (active - 1) % len(values)
                    message = ""
                    continue
                if key in (curses.KEY_DOWN, ord("j"), 9):
                    active = (active + 1) % len(values)
                    message = ""
                    continue
                if key in (10, 13, curses.KEY_ENTER):
                    self._save_requested = False
                    edited = self._edit_line(
                        win=win, row=4 + active * 2, column=20,
                        initial_value=values[active],
                        max_width=max(1, width - 22),
                    )
                    if edited is not None:
                        values[active] = edited
                        message = ""
                    if self._save_requested:
                        self._save_requested = False
                        updated, message = build()
                        if updated is not None:
                            return updated
                    continue
                if key == curses.KEY_F2:
                    updated, message = build()
                    if updated is not None:
                        return updated
        finally:
            try:
                curses.curs_set(0)
            except curses.error:
                pass
            try:
                win.nodelay(True)
            except curses.error:
                pass
