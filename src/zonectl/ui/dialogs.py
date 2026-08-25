from __future__ import annotations

import curses
from collections.abc import Callable

from .function_keys import decode_function_key


class CursesDialogs:
    """Wspólne dialogi tekstowe interfejsu curses."""

    @staticmethod
    def normalize_query(value: str) -> str:
        """
        Normalizuje frazę wyszukiwania.

        Wyszukiwanie działa jako dopasowanie fragmentu tekstu.
        Gwiazdki na początku i końcu są traktowane jak opcjonalne
        symbole wildcard, np. *elk.pl oraz elk.pl*.
        """
        query = value.strip()

        while query.startswith("*"):
            query = query[1:]

        while query.endswith("*"):
            query = query[:-1]

        return query.strip()

    @staticmethod
    def text_input(
        win: curses.window,
        prompt: str,
        *,
        initial: str = "",
        row: int | None = None,
    ) -> str | None:
        """
        Wyświetla jednowierszowy dialog tekstowy.

        Enter zatwierdza wartość.
        ESC anuluje dialog.
        """
        height, width = win.getmaxyx()

        if row is None:
            row = max(0, height - 1)

        row = max(0, min(row, height - 1))
        available = max(1, width - len(prompt) - 1)

        try:
            win.nodelay(False)

            win.timeout(-1)
            curses.noecho()
            curses.curs_set(1)

            win.move(row, 0)
            win.clrtoeol()

            win.addnstr(
                row,
                0,
                prompt,
                max(0, width - 1),
                curses.A_BOLD,
            )

            return CursesDialogs._edit_line(
                win, row, len(prompt), initial, available,
            )

        except KeyboardInterrupt:
            return None

        except curses.error:
            return None

        finally:
            curses.noecho()

            try:
                curses.curs_set(0)
            except curses.error:
                pass

            try:
                win.move(row, 0)
                win.clrtoeol()
                win.refresh()
            except curses.error:
                pass

            try:
                win.timeout(0)
                win.nodelay(True)
            except curses.error:
                pass

    @classmethod
    def search(
        cls,
        win: curses.window,
        *,
        prompt: str = " Szukaj: ",
        initial: str = "",
        row: int | None = None,
    ) -> str | None:
        value = cls.text_input(
            win,
            prompt,
            initial=initial,
            row=row,
        )

        if value is None:
            return None

        return cls.normalize_query(value)

    @staticmethod
    def confirm(
        win: curses.window,
        message: str,
        *,
        row: int | None = None,
        key_reader: Callable[[curses.window], int] | None = None,
    ) -> bool:
        """Wyświetla potwierdzenie [t/N]."""
        height, width = win.getmaxyx()

        if row is None:
            row = max(0, height - 1)

        row = max(0, min(row, height - 1))

        try:
            win.move(row, 0)
            win.clrtoeol()
            win.addnstr(
                row,
                0,
                f" {message} [t/N] ",
                max(0, width - 1),
                curses.A_BOLD,
            )
            win.refresh()

            # Okno główne pracuje z krótkim timeoutem na potrzeby
            # odświeżania statusów. Potwierdzenie musi jednak czekać
            # na świadomą odpowiedź operatora.
            win.timeout(-1)
            read_key = key_reader or (lambda window: window.getch())
            while True:
                key = read_key(win)
                if curses.KEY_F1 <= key <= curses.KEY_F12:
                    continue
                break

            return key in (
                ord("t"),
                ord("T"),
                ord("y"),
                ord("Y"),
            )

        except curses.error:
            return False

        finally:
            try:
                win.timeout(150)
            except curses.error:
                pass

            try:
                win.move(row, 0)
                win.clrtoeol()
                win.refresh()
            except curses.error:
                pass
    @staticmethod
    def _get_key(win: curses.window) -> int:
        """Read one key, normalizing xterm/PuTTY escape sequences."""
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
            try:
                win.timeout(-1)
            except curses.error:
                pass
        decoded = decode_function_key(sequence)
        if decoded is not None:
            return decoded
        for item in reversed(sequence):
            try:
                curses.ungetch(item)
            except curses.error:
                break
        return 27

    @classmethod
    def _edit_line(
        cls, win: curses.window, row: int, column: int,
        initial: str, available: int,
    ) -> str | None:
        """Edit a real initial buffer with cursor, Delete and Home/End."""
        value = list(initial)
        cursor = len(value)
        offset = 0
        while True:
            if cursor < offset:
                offset = cursor
            elif cursor >= offset + available:
                offset = cursor - available + 1
            offset = max(0, offset)
            visible = "".join(value[offset:offset + available])
            win.move(row, column)
            win.clrtoeol()
            win.addnstr(row, column, visible.ljust(available), available)
            win.move(row, min(column + available - 1, column + cursor - offset))
            win.refresh()
            key = cls._get_key(win)
            if key in (10, 13, curses.KEY_ENTER):
                return "".join(value)
            if key == 27:
                return None
            if key == curses.KEY_LEFT:
                cursor = max(0, cursor - 1)
            elif key == curses.KEY_RIGHT:
                cursor = min(len(value), cursor + 1)
            elif key == curses.KEY_HOME:
                cursor = 0
            elif key == curses.KEY_END:
                cursor = len(value)
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
