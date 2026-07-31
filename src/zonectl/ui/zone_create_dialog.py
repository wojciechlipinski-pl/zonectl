from __future__ import annotations

import curses
from dataclasses import dataclass

from .function_keys import decode_function_key
from .form_style import active_field_attr, field_marker


@dataclass(frozen=True, slots=True)
class ZoneCreateForm:
    name: str
    primary_ns: str
    admin: str
    nameservers: str
    ipv4: str = ""
    ipv6: str = ""
    add_www: bool = False


class ZoneCreateDialog:
    """Pełnoekranowy formularz parametrów nowej strefy DNS."""

    LABELS = (
        "Nazwa strefy",
        "Główny NS",
        "Administrator SOA",
        "Serwery NS",
        "IPv4 apex",
        "IPv6 apex",
        "Rekord www",
    )

    @staticmethod
    def _get_key(win: curses.window) -> int:
        key = win.getch()
        if key != 27:
            return key
        sequence: list[int] = []
        try:
            win.timeout(80)
            for _ in range(4):
                item = win.getch()
                if item == -1:
                    break
                sequence.append(item)
        finally:
            win.timeout(-1)
        decoded = decode_function_key(sequence)
        if decoded is not None:
            return decoded
        for item in reversed(sequence):
            try:
                curses.ungetch(item)
            except curses.error:
                break
        return 27

    @staticmethod
    def _put(win, row, column, text, attr=curses.A_NORMAL) -> None:
        height, width = win.getmaxyx()
        if not (0 <= row < height and 0 <= column < width):
            return
        try:
            win.addnstr(row, column, str(text), max(0, width - column - 1), attr)
        except curses.error:
            pass

    def _edit_line(self, win, row: int, column: int, initial: str) -> str | None:
        value = list(initial)
        cursor = len(value)
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        try:
            while True:
                height, width = win.getmaxyx()
                available = max(1, width - column - 2)
                offset = max(0, cursor - available + 1)
                visible = "".join(value[offset:offset + available])
                try:
                    win.move(row, column)
                    win.clrtoeol()
                    win.addnstr(row, column, visible.ljust(available), available, curses.A_REVERSE)
                    win.move(row, min(width - 2, column + cursor - offset))
                    win.refresh()
                except curses.error:
                    pass
                key = self._get_key(win)
                if key in (10, 13, curses.KEY_ENTER):
                    return "".join(value)
                if key == curses.KEY_F2:
                    return "".join(value)
                if key == 27:
                    return None
                if key == curses.KEY_LEFT:
                    cursor = max(0, cursor - 1)
                elif key == curses.KEY_RIGHT:
                    cursor = min(len(value), cursor + 1)
                elif key in (curses.KEY_BACKSPACE, 8, 127):
                    if cursor:
                        del value[cursor - 1]
                        cursor -= 1
                elif key == curses.KEY_DC:
                    if cursor < len(value):
                        del value[cursor]
                elif 32 <= key <= 126:
                    value.insert(cursor, chr(key))
                    cursor += 1
        finally:
            try:
                curses.curs_set(0)
            except curses.error:
                pass

    def collect(
        self,
        win: curses.window,
        *,
        primary_ns: str,
        admin: str,
        nameservers: str,
    ) -> ZoneCreateForm | None:
        values = ["", primary_ns, admin, nameservers, "", ""]
        add_www = False
        active = 0
        message = ""
        try:
            win.keypad(True)
            win.nodelay(False)
            win.timeout(-1)
        except curses.error:
            pass
        while True:
            win.erase()
            height, width = win.getmaxyx()
            self._put(
                win, 0, 0, " Kreator nowej strefy DNS ".ljust(width),
                curses.A_REVERSE | curses.A_BOLD,
            )
            for index, label in enumerate(self.LABELS):
                row = 3 + index * 2
                is_active = index == active
                attr = active_field_attr() if is_active else curses.A_NORMAL
                self._put(win, row, 0, field_marker(is_active), attr)
                self._put(
                    win,
                    row,
                    2,
                    f"{label:<18}: ",
                    attr if is_active else curses.A_BOLD,
                )
                text = ("[ TAK ]" if add_www else "[ NIE ]") if index == 6 else values[index]
                self._put(win, row, 23, text.ljust(max(1, width - 25)), attr)
            self._put(
                win,
                17,
                2,
                f"Aktywne pole: {self.LABELS[active]}",
                active_field_attr(),
            )
            if message:
                self._put(win, 18, 2, message, curses.A_BOLD)
            footer = " ↑/↓/Tab pole  Enter edytuj  Spacja przełącz www  F2 podgląd  Esc/q anuluj "
            self._put(win, height - 1, 0, footer.ljust(width), curses.A_REVERSE)
            win.refresh()
            key = self._get_key(win)
            if key in (27, ord("q"), ord("Q"), curses.KEY_F10):
                return None
            if key in (curses.KEY_DOWN, 9):
                active = (active + 1) % len(self.LABELS)
                continue
            if key in (curses.KEY_UP, curses.KEY_BTAB):
                active = (active - 1) % len(self.LABELS)
                continue
            if key == ord(" ") and active == 6:
                add_www = not add_www
                continue
            if key in (10, 13, curses.KEY_ENTER):
                if active == 6:
                    add_www = not add_www
                else:
                    edited = self._edit_line(win, 3 + active * 2, 23, values[active])
                    if edited is not None:
                        values[active] = edited.strip()
                continue
            if key == curses.KEY_F2:
                if not all(values[index].strip() for index in range(4)):
                    message = "Wypełnij nazwę strefy, główny NS, SOA i listę NS."
                    continue
                return ZoneCreateForm(
                    name=values[0].strip(),
                    primary_ns=values[1].strip(),
                    admin=values[2].strip(),
                    nameservers=values[3].strip(),
                    ipv4=values[4].strip(),
                    ipv6=values[5].strip(),
                    add_www=add_www,
                )
