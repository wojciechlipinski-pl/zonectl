from __future__ import annotations

import ast
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UI_FILE = ROOT / "src/elkman_dns/ui/curses_app.py"


OLD = '''        def prompt_search() -> str | None:
            height, width = win.getmaxyx()
            prompt = " Szukaj: "
            row = max(0, height - 2)

            try:
                curses.curs_set(1)
            except curses.error:
                pass

            curses.echo()

            try:
                win.move(row, 0)
                win.clrtoeol()
                win.addnstr(
                    row,
                    0,
                    prompt,
                    max(0, width - 1),
                    curses.A_REVERSE,
                )

                available = max(1, width - len(prompt) - 2)

                raw = win.getstr(
                    row,
                    len(prompt),
                    available,
                )

                return raw.decode(
                    "utf-8",
                    errors="replace",
                ).strip()

            except curses.error:
                return None

            finally:
                curses.noecho()

                try:
                    curses.curs_set(0)
                except curses.error:
                    pass
'''


NEW = '''        def prompt_search() -> str | None:
            height, width = win.getmaxyx()
            prompt = " Szukaj: "
            row = max(0, height - 2)

            try:
                win.nodelay(False)
                win.timeout(-1)
            except curses.error:
                pass

            try:
                curses.curs_set(1)
            except curses.error:
                pass

            curses.echo()

            try:
                win.move(row, 0)
                win.clrtoeol()

                win.addnstr(
                    row,
                    0,
                    prompt,
                    max(0, width - 1),
                    curses.A_REVERSE,
                )

                win.refresh()

                available = max(1, width - len(prompt) - 2)

                raw = win.getstr(
                    row,
                    len(prompt),
                    available,
                )

                return raw.decode(
                    "utf-8",
                    errors="replace",
                ).strip()

            except curses.error:
                return None

            finally:
                curses.noecho()

                try:
                    curses.curs_set(0)
                except curses.error:
                    pass

                try:
                    win.nodelay(True)
                except curses.error:
                    pass
'''


def backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = path.with_name(f"{path.name}.bak-{stamp}")
    shutil.copy2(path, destination)
    return destination


def main() -> None:
    source = UI_FILE.read_text(encoding="utf-8")

    if OLD not in source:
        if "win.nodelay(False)" in source:
            print("Poprawka wyszukiwania jest już wdrożona")
            return

        raise RuntimeError(
            "Nie znaleziono funkcji prompt_search() w oczekiwanej postaci"
        )

    updated = source.replace(OLD, NEW, 1)

    ast.parse(updated, filename=str(UI_FILE))

    backup_path = backup(UI_FILE)
    UI_FILE.write_text(updated, encoding="utf-8")

    print("OK: naprawiono wpisywanie frazy wyszukiwania")
    print(f"Plik:   {UI_FILE}")
    print(f"Backup: {backup_path}")


if __name__ == "__main__":
    main()
