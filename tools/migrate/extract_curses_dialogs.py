from __future__ import annotations

import ast
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

APP_FILE = ROOT / "src/elkman_dns/ui/curses_app.py"
DIALOGS_FILE = ROOT / "src/elkman_dns/ui/dialogs.py"
TEST_FILE = ROOT / "tests/test_ui_dialogs.py"


DIALOGS_SOURCE = '''from __future__ import annotations

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
'''


TEST_SOURCE = '''from __future__ import annotations

import unittest

from elkman_dns.ui.dialogs import CursesDialogs


class CursesDialogsTests(unittest.TestCase):
    def test_normalize_query_strips_whitespace(self) -> None:
        self.assertEqual(
            CursesDialogs.normalize_query("  elk.pl  "),
            "elk.pl",
        )

    def test_normalize_query_removes_outer_wildcards(self) -> None:
        self.assertEqual(
            CursesDialogs.normalize_query("*elk.pl"),
            "elk.pl",
        )
        self.assertEqual(
            CursesDialogs.normalize_query("elk.pl*"),
            "elk.pl",
        )
        self.assertEqual(
            CursesDialogs.normalize_query("*elk.pl*"),
            "elk.pl",
        )

    def test_normalize_query_keeps_internal_wildcard(self) -> None:
        self.assertEqual(
            CursesDialogs.normalize_query("elk*.pl"),
            "elk*.pl",
        )

    def test_normalize_empty_query(self) -> None:
        self.assertEqual(
            CursesDialogs.normalize_query("   "),
            "",
        )
        self.assertEqual(
            CursesDialogs.normalize_query("***"),
            "",
        )


if __name__ == "__main__":
    unittest.main()
'''


SEARCH_METHOD = '''    def _search(self, stdscr: curses.window) -> None:
        """Filtruje domeny na głównej liście."""
        query = CursesDialogs.search(
            stdscr,
            prompt=" Szukaj domeny: ",
            initial=self.query,
        )

        if query is None:
            return

        self.query = query
        self.selected = 0
        self.offset = 0
        self._rebuild_rows()

'''


def backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = path.with_name(
        f"{path.name}.bak-{stamp}"
    )
    shutil.copy2(path, destination)
    return destination


def write_python_file(
    path: Path,
    content: str,
) -> None:
    ast.parse(content, filename=str(path))

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if path.exists():
        backup_path = backup(path)
        print(f"Backup: {backup_path}")

    path.write_text(
        content,
        encoding="utf-8",
    )

    print(f"OK: zapisano {path}")


def ensure_dialogs_import(source: str) -> str:
    import_line = (
        "from elkman_dns.ui.dialogs import CursesDialogs\n"
    )

    if import_line in source:
        print("JUŻ JEST: import CursesDialogs")
        return source

    candidates = (
        "from elkman_dns.core.zone_model import",
        "from elkman_dns.core.zone_parser import",
    )

    for candidate in candidates:
        position = source.find(candidate)

        if position == -1:
            continue

        line_end = source.find("\n", position)

        if line_end == -1:
            raise RuntimeError(
                "Nie znaleziono końca linii importu"
            )

        print("OK: dodano import CursesDialogs")

        return (
            source[: line_end + 1]
            + import_line
            + source[line_end + 1 :]
        )

    future_import = (
        "from __future__ import annotations\\n"
    )

    if future_import in source:
        print("OK: dodano import CursesDialogs")

        return source.replace(
            future_import,
            future_import + "\\n" + import_line,
            1,
        )

    raise RuntimeError(
        "Nie znaleziono miejsca na import CursesDialogs"
    )


def replace_search_method(source: str) -> str:
    start_marker = "    def _search("
    end_marker = "    def _records_view("

    start = source.find(start_marker)
    end = source.find(end_marker, start)

    if start == -1:
        raise RuntimeError(
            "Nie znaleziono metody _search"
        )

    if end == -1:
        raise RuntimeError(
            "Nie znaleziono metody _records_view "
            "za metodą _search"
        )

    current = source[start:end]

    if current.strip() == SEARCH_METHOD.strip():
        print("JUŻ JEST: nowa metoda _search")
        return source

    print("OK: przeniesiono dialog wyszukiwania domen")

    return (
        source[:start]
        + SEARCH_METHOD
        + source[end:]
    )


def fix_clear_filter_behavior(source: str) -> str:
    old = '''            if key in (ord("c"), ord("C")):
                search_query = ""
                selected = 0
                offset = 0
                continue
'''

    new = '''            if key in (ord("c"), ord("C")):
                if search_query:
                    search_query = ""
                    selected = 0
                    offset = 0
                continue
'''

    if new in source:
        print("JUŻ JEST: poprawna obsługa klawisza c")
        return source

    if old not in source:
        print(
            "UWAGA: nie znaleziono standardowej "
            "obsługi klawisza c"
        )
        return source

    print("OK: klawisz c nie zeruje już zaznaczenia bez filtra")
    return source.replace(old, new, 1)


def main() -> None:
    if not APP_FILE.exists():
        raise SystemExit(
            f"Brak pliku: {APP_FILE}"
        )

    write_python_file(
        DIALOGS_FILE,
        DIALOGS_SOURCE,
    )

    write_python_file(
        TEST_FILE,
        TEST_SOURCE,
    )

    source = APP_FILE.read_text(
        encoding="utf-8",
    )

    updated = ensure_dialogs_import(source)
    updated = replace_search_method(updated)
    updated = fix_clear_filter_behavior(updated)

    ast.parse(
        updated,
        filename=str(APP_FILE),
    )

    backup_path = backup(APP_FILE)

    APP_FILE.write_text(
        updated,
        encoding="utf-8",
    )

    print(f"Backup: {backup_path}")
    print(f"OK: zapisano {APP_FILE}")
    print("Etap 1 refaktoryzacji zakończony")


if __name__ == "__main__":
    main()
