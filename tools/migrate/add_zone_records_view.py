from __future__ import annotations

import ast
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BIND_FILE = ROOT / "src/elkman_dns/core/bind.py"
UI_FILE = ROOT / "src/elkman_dns/ui/curses_app.py"


BIND_METHOD = '''
    def zone_records(self, zone: Zone) -> tuple[list[str], str | None]:
        """Zwraca kanoniczną listę rekordów z aktywnego pliku strefy."""
        if zone.file is None:
            return [], "Brak ścieżki do pliku strefy"

        if not zone.file.exists():
            return [], f"Plik strefy nie istnieje: {zone.file}"

        result = run(
            [
                "named-checkzone",
                "-D",
                zone.name,
                str(zone.file),
            ],
            15,
        )

        if result.returncode != 0:
            message = (result.stdout + result.stderr).strip()
            return [], message or "named-checkzone zakończył się błędem"

        records: list[str] = []

        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()

            if not line:
                continue

            lowered = line.casefold()

            if lowered.startswith("zone "):
                continue

            if lowered.startswith("loaded serial"):
                continue

            if lowered == "ok":
                continue

            records.append(line)

        return records, None
'''


UI_METHOD = '''
    def _records_view(self, win: curses.window, zone: Zone) -> None:
        """Wyświetla przewijaną listę rekordów wybranej strefy."""
        records, error = self.bind.zone_records(zone)
        selected = 0
        offset = 0

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

            title = f" Rekordy DNS: {zone.name} "
            put(
                0,
                0,
                title.ljust(width),
                curses.A_REVERSE | curses.A_BOLD,
            )

            if error:
                put(3, 2, "Nie udało się odczytać rekordów:", curses.A_BOLD)
                put(5, 2, error, self._color(Health.FAIL))

                footer = " q/Esc/Backspace powrót "
                put(
                    height - 2,
                    0,
                    footer.ljust(width),
                    curses.A_REVERSE,
                )

                win.refresh()
                key = win.getch()

                if key in (
                    ord("q"),
                    27,
                    curses.KEY_BACKSPACE,
                    127,
                    8,
                ):
                    return

                continue

            put(
                2,
                2,
                f"Liczba rekordów: {len(records)}",
                curses.A_BOLD,
            )

            list_top = 4
            visible = max(1, height - list_top - 3)

            if records:
                selected = min(selected, len(records) - 1)

                if selected < offset:
                    offset = selected

                if selected >= offset + visible:
                    offset = selected - visible + 1

                for screen_row, record in enumerate(
                    records[offset:offset + visible],
                    start=list_top,
                ):
                    index = offset + screen_row - list_top
                    attr = (
                        curses.A_REVERSE
                        if index == selected
                        else curses.A_NORMAL
                    )

                    put(
                        screen_row,
                        1,
                        record,
                        attr,
                    )
            else:
                put(
                    list_top,
                    2,
                    "Brak rekordów do wyświetlenia.",
                    curses.A_DIM,
                )

            footer = (
                " ↑/↓ przewijanie"
                "   PgUp/PgDn strona"
                "   Home/End"
                "   q/Esc powrót "
            )
            put(
                height - 2,
                0,
                footer.ljust(width),
                curses.A_REVERSE,
            )

            win.refresh()
            key = win.getch()

            if key in (
                ord("q"),
                27,
                curses.KEY_BACKSPACE,
                127,
                8,
            ):
                return

            if not records:
                continue

            if key in (curses.KEY_DOWN, ord("j")):
                selected = min(selected + 1, len(records) - 1)

            elif key in (curses.KEY_UP, ord("k")):
                selected = max(selected - 1, 0)

            elif key == curses.KEY_NPAGE:
                selected = min(
                    selected + visible,
                    len(records) - 1,
                )

            elif key == curses.KEY_PPAGE:
                selected = max(selected - visible, 0)

            elif key == curses.KEY_HOME:
                selected = 0

            elif key == curses.KEY_END:
                selected = len(records) - 1
'''


def backup(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"{path.name}.bak-{timestamp}")
    shutil.copy2(path, target)
    return target


def insert_before_method(
    source: str,
    method_name: str,
    new_method: str,
) -> str:
    marker = f"    def {method_name}("

    if marker not in source:
        raise RuntimeError(
            f"Nie znaleziono metody {method_name}()"
        )

    return source.replace(
        marker,
        new_method.rstrip() + "\n\n" + marker,
        1,
    )


def update_bind() -> None:
    source = BIND_FILE.read_text(encoding="utf-8")

    if "def zone_records(" in source:
        print("BindService.zone_records() już istnieje")
        return

    updated = insert_before_method(
        source,
        "quick_status",
        BIND_METHOD,
    )

    ast.parse(updated, filename=str(BIND_FILE))
    backup_path = backup(BIND_FILE)
    BIND_FILE.write_text(updated, encoding="utf-8")

    print(f"OK: zmieniono {BIND_FILE}")
    print(f"Backup: {backup_path}")


def update_ui() -> None:
    source = UI_FILE.read_text(encoding="utf-8")

    if "def _records_view(" not in source:
        source = insert_before_method(
            source,
            "_domain_view",
            UI_METHOD,
        )

    old_footer = '''            footer = (
                " r odśwież strefę"
                "   q/Esc/Backspace powrót "
            )'''

    new_footer = '''            footer = (
                " v rekordy"
                "   r odśwież strefę"
                "   q/Esc/Backspace powrót "
            )'''

    if old_footer in source:
        source = source.replace(
            old_footer,
            new_footer,
            1,
        )
    elif '" v rekordy"' not in source:
        raise RuntimeError(
            "Nie znaleziono stopki widoku domeny"
        )

    key_marker = '''            if key in (ord("r"), ord("R")):
                notice = "Sprawdzanie strefy..."'''

    key_replacement = '''            if key in (ord("v"), ord("V")):
                self._records_view(win, zone)
                continue

            if key in (ord("r"), ord("R")):
                notice = "Sprawdzanie strefy..."'''

    if key_marker in source:
        source = source.replace(
            key_marker,
            key_replacement,
            1,
        )
    elif "self._records_view(win, zone)" not in source:
        raise RuntimeError(
            "Nie znaleziono obsługi klawisza r"
        )

    ast.parse(source, filename=str(UI_FILE))
    backup_path = backup(UI_FILE)
    UI_FILE.write_text(source, encoding="utf-8")

    print(f"OK: zmieniono {UI_FILE}")
    print(f"Backup: {backup_path}")


def main() -> None:
    update_bind()
    update_ui()
    print("OK: podgląd rekordów został wdrożony")


if __name__ == "__main__":
    main()
