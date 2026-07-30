"""Interaktywny kreator nowych rekordów DNS."""

from __future__ import annotations

from collections.abc import Iterable
from ipaddress import IPv4Address, IPv6Address

import curses

from ...core.models import Zone
from ...core.record_validation import (
    SUPPORTED_RECORD_TYPES,
    validate_rdata as validate_record_rdata,
)
from ...core.zone_parser import DNSRecord


RECORD_TYPES = SUPPORTED_RECORD_TYPES


class NewRecordDialog:
    """Tworzy rekord DNS bez modyfikowania pliku strefy."""

    FIELD_OWNER = 0
    FIELD_TYPE = 1
    FIELD_TTL = 2
    FIELD_RDATA = 3

    def __init__(
        self,
        error_attr: int = curses.A_BOLD,
    ) -> None:
        self._error_attr = error_attr

    @staticmethod
    def default_ttl(
        zone_name: str,
        records: Iterable[DNSRecord],
    ) -> int:
        """Pobiera TTL z głównego rekordu SOA strefy."""
        records_list = list(records)
        apex = zone_name.rstrip(".").casefold()

        for record in records_list:
            if (
                record.rtype.upper() == "SOA"
                and record.owner.rstrip(".").casefold() == apex
                and record.ttl is not None
            ):
                return record.ttl

        for record in records_list:
            if (
                record.rtype.upper() == "SOA"
                and record.ttl is not None
            ):
                return record.ttl

        for record in records_list:
            if record.ttl is not None:
                return record.ttl

        return 3600

    @staticmethod
    def absolute_owner(
        owner: str,
        zone_name: str,
    ) -> str:
        value = owner.strip()
        zone = zone_name.rstrip(".")

        if value in ("", "@"):
            return f"{zone}."

        if value.endswith("."):
            return value

        return f"{value}.{zone}."

    @staticmethod
    def validate_hostname(value: str) -> bool:
        value = value.rstrip(".")

        if not value or len(value) > 253:
            return False

        labels = value.split(".")

        for label in labels:
            if not label or len(label) > 63:
                return False

            if label.startswith("-") or label.endswith("-"):
                return False

            if not all(
                character.isalnum() or character in "-_"
                for character in label
            ):
                return False

        return True

    @classmethod
    def validate_rdata(
        cls,
        rtype: str,
        rdata: str,
    ) -> str | None:
        value = rdata.strip()

        if not value:
            return "Dane rekordu nie mogą być puste."

        if rtype == "A":
            try:
                IPv4Address(value)
            except ValueError:
                return "Rekord A wymaga poprawnego adresu IPv4."

        elif rtype == "AAAA":
            try:
                IPv6Address(value)
            except ValueError:
                return "Rekord AAAA wymaga poprawnego adresu IPv6."

        elif rtype in ("CNAME", "NS", "PTR"):
            if not cls.validate_hostname(value):
                return f"Rekord {rtype} wymaga poprawnej nazwy hosta."

        elif rtype == "MX":
            fields = value.split()

            if len(fields) != 2:
                return "MX: oczekiwany format „priorytet serwer”."

            try:
                priority = int(fields[0])
            except ValueError:
                return "Priorytet MX musi być liczbą."

            if not 0 <= priority <= 65535:
                return "Priorytet MX musi mieć zakres 0–65535."

            if not cls.validate_hostname(fields[1]):
                return "MX zawiera niepoprawną nazwę serwera."

        elif rtype == "SRV":
            fields = value.split()

            if len(fields) != 4:
                return (
                    "SRV: oczekiwany format "
                    "„priorytet waga port serwer”."
                )

            try:
                numbers = tuple(int(item) for item in fields[:3])
            except ValueError:
                return "Pierwsze trzy wartości SRV muszą być liczbami."

            if any(not 0 <= number <= 65535 for number in numbers):
                return "Wartości SRV muszą mieć zakres 0–65535."

            if not cls.validate_hostname(fields[3]):
                return "SRV zawiera niepoprawną nazwę serwera."

        elif rtype == "CAA":
            fields = value.split(None, 2)

            if len(fields) != 3:
                return 'CAA: oczekiwany format „0 issue "ca.example"”.'

            try:
                flags = int(fields[0])
            except ValueError:
                return "Flagi CAA muszą być liczbą."

            if not 0 <= flags <= 255:
                return "Flagi CAA muszą mieć zakres 0–255."

        elif rtype == "TLSA":
            fields = value.split()

            if len(fields) != 4:
                return (
                    "TLSA: oczekiwany format "
                    "„usage selector matching-type dane”."
                )

            try:
                usage, selector, matching = (
                    int(fields[0]),
                    int(fields[1]),
                    int(fields[2]),
                )
            except ValueError:
                return "Pierwsze trzy wartości TLSA muszą być liczbami."

            if usage not in range(4):
                return "TLSA usage musi mieć zakres 0–3."

            if selector not in range(2):
                return "TLSA selector musi mieć zakres 0–1."

            if matching not in range(3):
                return "TLSA matching-type musi mieć zakres 0–2."

        return None

    @classmethod
    def build_record(
        cls,
        zone_name: str,
        owner: str,
        rtype: str,
        ttl_text: str,
        rdata: str,
    ) -> tuple[DNSRecord | None, str]:
        normalized_type = rtype.strip().upper()

        if normalized_type not in RECORD_TYPES:
            return None, "Nieobsługiwany typ rekordu."

        try:
            ttl = int(ttl_text.strip())
        except ValueError:
            return None, "TTL musi być liczbą całkowitą."

        if not 0 <= ttl <= 2147483647:
            return None, "TTL musi mieć zakres 0–2147483647."

        error = validate_record_rdata(
            normalized_type,
            rdata,
        )

        if error:
            return None, error

        absolute_owner = cls.absolute_owner(
            owner,
            zone_name,
        )
        normalized_rdata = rdata.strip()

        record = DNSRecord(
            owner=absolute_owner,
            ttl=ttl,
            rrclass="IN",
            rtype=normalized_type,
            rdata=normalized_rdata,
            raw=(
                f"{absolute_owner} {ttl} IN "
                f"{normalized_type} {normalized_rdata}"
            ),
        )

        return record, ""

    @staticmethod
    def _put(
        win: curses.window,
        row: int,
        column: int,
        text: str,
        attr: int = curses.A_NORMAL,
    ) -> None:
        height, width = win.getmaxyx()

        if not 0 <= row < height:
            return

        if not 0 <= column < width:
            return

        available = width - column - 1

        if available <= 0:
            return

        try:
            win.addnstr(
                row,
                column,
                text,
                available,
                attr,
            )
        except curses.error:
            pass

    @staticmethod
    def _type_window(
        type_index: int,
        maximum: int = 9,
    ) -> tuple[int, int]:
        half = maximum // 2
        start = max(0, type_index - half)
        end = min(len(RECORD_TYPES), start + maximum)
        start = max(0, end - maximum)

        return start, end

    def create_record_dialog(
        self,
        win: curses.window,
        zone: Zone,
        records: Iterable[DNSRecord],
    ) -> DNSRecord | None:
        values = [
            "",
            "A",
            str(self.default_ttl(zone.name, records)),
            "",
        ]

        labels = (
            "Nazwa",
            "Typ",
            "TTL",
            "Dane",
        )

        active = self.FIELD_OWNER
        type_index = RECORD_TYPES.index("A")
        cursors = [
            len(value)
            for value in values
        ]
        message = ""

        # Formularz musi działać w trybie blokującym.
        # Bez keypad(True) klawisz F2 może zostać odczytany
        # jako sekwencja zaczynająca się od Esc, co anuluje dialog.
        try:
            win.keypad(True)
            win.nodelay(False)
            win.timeout(-1)
        except curses.error:
            pass

        try:
            curses.curs_set(1)
        except curses.error:
            pass

        try:
            while True:
                win.erase()
                height, width = win.getmaxyx()

                self._put(
                    win,
                    0,
                    0,
                    f" Dodawanie rekordu: {zone.name} ".ljust(width),
                    curses.A_REVERSE | curses.A_BOLD,
                )

                for index, label in enumerate(labels):
                    row = 3 + index * 2
                    attr = (
                        curses.A_REVERSE
                        if index == active
                        else curses.A_NORMAL
                    )

                    self._put(
                        win,
                        row,
                        2,
                        f"{label:<8}: ",
                        curses.A_BOLD,
                    )

                    if index == self.FIELD_TYPE:
                        text = f"[ {values[index]} ▼ ]"
                    else:
                        text = values[index]

                    self._put(
                        win,
                        row,
                        13,
                        text.ljust(max(1, width - 15)),
                        attr,
                    )

                # Lista typów rozwija się automatycznie,
                # gdy aktywne jest pole Typ.
                if active == self.FIELD_TYPE:
                    start, end = self._type_window(type_index)

                    self._put(
                        win,
                        12,
                        13,
                        "Typy rekordów:",
                        curses.A_BOLD,
                    )

                    for display_row, index in enumerate(
                        range(start, end),
                        start=13,
                    ):
                        marker = "▶" if index == type_index else " "
                        attr = (
                            curses.A_REVERSE
                            if index == type_index
                            else curses.A_NORMAL
                        )

                        self._put(
                            win,
                            display_row,
                            13,
                            f"{marker} {RECORD_TYPES[index]}".ljust(16),
                            attr,
                        )

                if message:
                    self._put(
                        win,
                        height - 4,
                        2,
                        message,
                        self._error_attr,
                    )

                footer = (
                    " Enter/Tab następne"
                    "   Shift+Tab poprzednie"
                    "   F2 dodaj"
                    "   Esc anuluj "
                )

                self._put(
                    win,
                    height - 2,
                    0,
                    footer.ljust(width),
                    curses.A_REVERSE,
                )

                # Kursor jest od razu aktywny w bieżącym polu.
                if active != self.FIELD_TYPE:
                    cursor = min(
                        cursors[active],
                        len(values[active]),
                    )
                    cursor_column = min(
                        width - 2,
                        13 + cursor,
                    )

                    try:
                        win.move(
                            3 + active * 2,
                            cursor_column,
                        )
                    except curses.error:
                        pass

                win.refresh()
                key = win.getch()

                if key in (27,):
                    return None

                if key == curses.KEY_F2:
                    record, message = self.build_record(
                        zone_name=zone.name,
                        owner=values[self.FIELD_OWNER],
                        rtype=values[self.FIELD_TYPE],
                        ttl_text=values[self.FIELD_TTL],
                        rdata=values[self.FIELD_RDATA],
                    )

                    if record is not None:
                        return record

                    continue

                if key == curses.KEY_BTAB:
                    active = (active - 1) % len(values)
                    message = ""
                    continue

                if key in (
                    10,
                    13,
                    curses.KEY_ENTER,
                ):
                    # Enter w ostatnim polu zatwierdza cały formularz.
                    if active == self.FIELD_RDATA:
                        record, message = self.build_record(
                            zone_name=zone.name,
                            owner=values[self.FIELD_OWNER],
                            rtype=values[self.FIELD_TYPE],
                            ttl_text=values[self.FIELD_TTL],
                            rdata=values[self.FIELD_RDATA],
                        )

                        if record is not None:
                            return record

                        continue

                    active = (active + 1) % len(values)
                    message = ""
                    continue

                if key == 9:
                    # Tab wyłącznie przechodzi do następnego pola.
                    active = (active + 1) % len(values)
                    message = ""
                    continue

                if active == self.FIELD_TYPE:
                    if key in (
                        curses.KEY_UP,
                        curses.KEY_LEFT,
                        ord("k"),
                    ):
                        type_index = (
                            type_index - 1
                        ) % len(RECORD_TYPES)
                        values[self.FIELD_TYPE] = RECORD_TYPES[type_index]
                        message = ""
                        continue

                    if key in (
                        curses.KEY_DOWN,
                        curses.KEY_RIGHT,
                        ord("j"),
                    ):
                        type_index = (
                            type_index + 1
                        ) % len(RECORD_TYPES)
                        values[self.FIELD_TYPE] = RECORD_TYPES[type_index]
                        message = ""
                        continue

                    # Wybór typu również po wpisaniu pierwszej litery.
                    if 32 <= key <= 126:
                        character = chr(key).upper()

                        for offset in range(1, len(RECORD_TYPES) + 1):
                            candidate = (
                                type_index + offset
                            ) % len(RECORD_TYPES)

                            if RECORD_TYPES[candidate].startswith(character):
                                type_index = candidate
                                values[self.FIELD_TYPE] = (
                                    RECORD_TYPES[type_index]
                                )
                                break

                    continue

                value = values[active]
                cursor = cursors[active]

                if key == curses.KEY_LEFT:
                    cursors[active] = max(0, cursor - 1)
                    continue

                if key == curses.KEY_RIGHT:
                    cursors[active] = min(
                        len(value),
                        cursor + 1,
                    )
                    continue

                if key == curses.KEY_HOME:
                    cursors[active] = 0
                    continue

                if key == curses.KEY_END:
                    cursors[active] = len(value)
                    continue

                if key in (
                    curses.KEY_BACKSPACE,
                    8,
                    127,
                ):
                    if cursor > 0:
                        values[active] = (
                            value[: cursor - 1]
                            + value[cursor:]
                        )
                        cursors[active] -= 1
                    continue

                if key == curses.KEY_DC:
                    if cursor < len(value):
                        values[active] = (
                            value[:cursor]
                            + value[cursor + 1 :]
                        )
                    continue

                if 32 <= key <= 126:
                    character = chr(key)

                    # TTL przyjmuje tylko cyfry.
                    if (
                        active == self.FIELD_TTL
                        and not character.isdigit()
                    ):
                        message = "TTL może zawierać wyłącznie cyfry."
                        continue

                    values[active] = (
                        value[:cursor]
                        + character
                        + value[cursor:]
                    )
                    cursors[active] += 1
                    message = ""
                    continue
        finally:
            try:
                curses.curs_set(0)
            except curses.error:
                pass

            # Widok rekordów działa w trybie nieblokującym.
            try:
                win.nodelay(True)
            except curses.error:
                pass
