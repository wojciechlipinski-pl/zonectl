from __future__ import annotations

import curses


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

        previous_nodelay: bool | None = None

        try:
            try:
                previous_nodelay = win.nodelay(False)
            except TypeError:
                # Niektóre implementacje curses nie zwracają
                # poprzedniego stanu.
                win.nodelay(False)

            win.timeout(-1)
            curses.echo()
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

            if initial:
                win.addnstr(
                    row,
                    len(prompt),
                    initial,
                    available,
                )

            win.move(
                row,
                min(
                    width - 1,
                    len(prompt) + len(initial),
                ),
            )
            win.refresh()

            raw = win.getstr(
                row,
                len(prompt),
                available,
            )

            return raw.decode(
                "utf-8",
                errors="replace",
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

            key = win.getch()

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
                win.move(row, 0)
                win.clrtoeol()
                win.refresh()
            except curses.error:
                pass
