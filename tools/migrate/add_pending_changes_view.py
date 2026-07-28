from __future__ import annotations

import ast
import re
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "src/elkman_dns/ui/curses_app.py"


def backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = path.with_name(f"{path.name}.bak-{stamp}")
    shutil.copy2(path, destination)
    return destination


def ensure_import(source: str) -> str:
    old = "from elkman_dns.core.zone_model import ZoneModel\n"
    new = (
        "from elkman_dns.core.zone_model import "
        "ChangeKind, ZoneChange, ZoneModel\n"
    )

    if new in source:
        return source

    if old in source:
        return source.replace(old, new, 1)

    raise RuntimeError(
        "Nie znaleziono importu ZoneModel"
    )


METHOD = r'''
    def _pending_changes_view(
        self,
        win: curses.window,
        model: ZoneModel,
        zone: Zone,
    ) -> None:
        """Wyświetla zmiany oczekujące w buforze edycji."""
        selected = 0
        offset = 0

        def record_text(record) -> str:
            owner = record.relative_owner(zone.name)
            ttl = "-" if record.ttl is None else str(record.ttl)

            return (
                f"{owner:<28} "
                f"{record.rtype:<7} "
                f"{ttl:<8} "
                f"{record.rdata}"
            )

        def change_lines(
            change: ZoneChange,
        ) -> list[tuple[str, int]]:
            if change.kind is ChangeKind.ADD:
                assert change.after is not None
                return [
                    (
                        "A  " + record_text(change.after),
                        curses.A_BOLD,
                    )
                ]

            if change.kind is ChangeKind.DELETE:
                assert change.before is not None
                return [
                    (
                        "D  " + record_text(change.before),
                        curses.A_DIM,
                    )
                ]

            assert change.before is not None
            assert change.after is not None

            return [
                (
                    "M- " + record_text(change.before),
                    curses.A_DIM,
                ),
                (
                    "M+ " + record_text(change.after),
                    curses.A_BOLD,
                ),
            ]

        while True:
            changes = list(model.pending_changes)
            lines: list[tuple[str, int, int]] = []

            for change_index, change in enumerate(changes):
                for text, attr in change_lines(change):
                    lines.append(
                        (
                            text,
                            attr,
                            change_index,
                        )
                    )

            height, width = win.getmaxyx()
            win.erase()

            title = (
                f" Oczekujące zmiany — {zone.name} "
            )

            win.addnstr(
                0,
                0,
                title.ljust(width),
                width,
                curses.A_REVERSE | curses.A_BOLD,
            )

            summary = (
                f" Zmiany: {len(changes)}"
                "   A=dodano  M=zmieniono  D=usunięto"
            )

            win.addnstr(
                2,
                0,
                summary,
                max(0, width - 1),
                curses.A_BOLD,
            )

            list_top = 4
            footer_lines = 3
            visible = max(
                1,
                height - list_top - footer_lines,
            )

            if lines:
                selected = min(
                    selected,
                    len(lines) - 1,
                )
            else:
                selected = 0

            if selected < offset:
                offset = selected

            if selected >= offset + visible:
                offset = selected - visible + 1

            if lines:
                visible_lines = lines[
                    offset : offset + visible
                ]

                for screen_row, (
                    text,
                    attr,
                    _change_index,
                ) in enumerate(
                    visible_lines,
                    start=list_top,
                ):
                    line_index = (
                        offset + screen_row - list_top
                    )

                    if line_index == selected:
                        attr |= curses.A_REVERSE

                    win.addnstr(
                        screen_row,
                        1,
                        text.ljust(max(1, width - 2)),
                        max(0, width - 2),
                        attr,
                    )

            else:
                win.addnstr(
                    list_top,
                    2,
                    "Brak oczekujących zmian.",
                    max(0, width - 3),
                    curses.A_DIM,
                )

            footer = (
                " ↑/↓ przewijanie"
                "   Home/End"
                "   u odrzuć wszystkie"
                "   q powrót "
            )

            win.addnstr(
                height - 2,
                0,
                footer.ljust(width),
                max(0, width - 1),
                curses.A_REVERSE,
            )

            win.refresh()
            key = win.getch()

            if key in (
                ord("q"),
                ord("Q"),
                27,
                curses.KEY_BACKSPACE,
                127,
                8,
            ):
                return

            if key in (
                curses.KEY_DOWN,
                ord("j"),
            ):
                if lines:
                    selected = min(
                        selected + 1,
                        len(lines) - 1,
                    )

            elif key in (
                curses.KEY_UP,
                ord("k"),
            ):
                selected = max(
                    selected - 1,
                    0,
                )

            elif key == curses.KEY_NPAGE:
                if lines:
                    selected = min(
                        selected + visible,
                        len(lines) - 1,
                    )

            elif key == curses.KEY_PPAGE:
                selected = max(
                    selected - visible,
                    0,
                )

            elif key == curses.KEY_HOME:
                selected = 0
                offset = 0

            elif key == curses.KEY_END:
                if lines:
                    selected = len(lines) - 1

            elif key in (
                ord("u"),
                ord("U"),
            ):
                if not model.dirty:
                    continue

                confirm = (
                    " Odrzucić wszystkie zmiany? [t/N] "
                )

                win.addnstr(
                    height - 1,
                    0,
                    confirm.ljust(width),
                    max(0, width - 1),
                    curses.A_BOLD,
                )
                win.refresh()

                answer = win.getch()

                if answer in (
                    ord("t"),
                    ord("T"),
                    ord("y"),
                    ord("Y"),
                ):
                    model.discard()
                    selected = 0
                    offset = 0

'''


def add_method(source: str) -> str:
    if "def _pending_changes_view(" in source:
        print("JUŻ JEST: metoda _pending_changes_view")
        return source

    marker = "    def _records_view("

    position = source.find(marker)

    if position == -1:
        raise RuntimeError(
            "Nie znaleziono metody _records_view"
        )

    print("OK: dodano widok oczekujących zmian")
    return (
        source[:position]
        + METHOD
        + "\n"
        + source[position:]
    )


def update_footer(source: str) -> str:
    if "p zmiany" in source:
        print("JUŻ JEST: skrót p w stopce rekordów")
        return source

    patterns = (
        (
            '"   s sortuj"\n'
            '                "   q powrót "\n',
            '"   s sortuj"\n'
            '                "   p zmiany"\n'
            '                "   q powrót "\n',
        ),
        (
            '"   d usuń"\n'
            '                "   q powrót "\n',
            '"   d usuń"\n'
            '                "   p zmiany"\n'
            '                "   q powrót "\n',
        ),
        (
            '"   u odrzuć"\n'
            '                "   q powrót "\n',
            '"   u odrzuć"\n'
            '                "   p zmiany"\n'
            '                "   q powrót "\n',
        ),
    )

    for old, new in patterns:
        if old in source:
            print("OK: dodano skrót p do stopki")
            return source.replace(old, new, 1)

    print(
        "UWAGA: nie znaleziono znanego wariantu stopki; "
        "skrót nadal będzie działał"
    )
    return source


def add_key_handler(source: str) -> str:
    handler = '''            if key in (ord("p"), ord("P")):
                self._pending_changes_view(
                    win,
                    model,
                    zone,
                )
                selected = 0
                offset = 0
                continue

'''

    if (
        "self._pending_changes_view(" in source
        and source.count(
            "self._pending_changes_view("
        ) > 1
    ):
        print("JUŻ JEST: obsługa klawisza p")
        return source

    marker_candidates = (
        '            if key in (ord("c"), ord("C")):\n',
        '            if key in (ord("s"), ord("S"), curses.KEY_F7):\n',
        '            if not visible_records:\n',
    )

    records_position = source.find(
        "    def _records_view("
    )

    if records_position == -1:
        raise RuntimeError(
            "Nie znaleziono _records_view"
        )

    next_method = source.find(
        "\n    def ",
        records_position + 5,
    )

    records_end = (
        len(source)
        if next_method == -1
        else next_method
    )

    for marker in marker_candidates:
        position = source.find(
            marker,
            records_position,
            records_end,
        )

        if position != -1:
            print("OK: dodano obsługę klawisza p")
            return (
                source[:position]
                + handler
                + source[position:]
            )

    raise RuntimeError(
        "Nie znaleziono miejsca na obsługę klawisza p"
    )


def main() -> None:
    if not TARGET.exists():
        raise SystemExit(f"Brak pliku: {TARGET}")

    source = TARGET.read_text(encoding="utf-8")

    updated = ensure_import(source)
    updated = add_method(updated)
    updated = update_footer(updated)
    updated = add_key_handler(updated)

    ast.parse(
        updated,
        filename=str(TARGET),
    )

    backup_path = backup(TARGET)
    TARGET.write_text(
        updated,
        encoding="utf-8",
    )

    print()
    print(f"Backup: {backup_path}")
    print(f"Zapisano: {TARGET}")
    print("Widok zmian oczekujących został wdrożony")


if __name__ == "__main__":
    main()
