from __future__ import annotations

import ast
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UI_FILE = ROOT / "src/elkman_dns/ui/curses_app.py"


def backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = path.with_name(f"{path.name}.bak-{stamp}")
    shutil.copy2(path, destination)
    return destination


def method_bounds(
    source: str,
    method_name: str,
) -> tuple[int, int]:
    lines = source.splitlines()
    start = None

    for index, line in enumerate(lines):
        if line.startswith(f"    def {method_name}("):
            start = index
            break

    if start is None:
        raise RuntimeError(f"Nie znaleziono metody {method_name}()")

    end = len(lines)

    for index in range(start + 1, len(lines)):
        line = lines[index]

        if line.startswith("    def ") or line.startswith("    @"):
            end = index
            break

    return start, end


def replace_method(
    source: str,
    method_name: str,
    replacement: str,
) -> str:
    lines = source.splitlines()
    start, end = method_bounds(source, method_name)

    updated = (
        lines[:start]
        + replacement.rstrip().splitlines()
        + [""]
        + lines[end:]
    )

    return "\n".join(updated).rstrip() + "\n"


NEW_SEARCH = r'''    def _search(self, stdscr: curses.window) -> None:
        """Wyszukuje domeny na głównej liście."""
        height, width = stdscr.getmaxyx()
        prompt = " Szukaj domeny: "
        row = max(0, height - 1)

        try:
            stdscr.nodelay(False)
            stdscr.timeout(-1)
        except curses.error:
            pass

        try:
            curses.curs_set(1)
        except curses.error:
            pass

        curses.echo()

        try:
            stdscr.move(row, 0)
            stdscr.clrtoeol()

            stdscr.addnstr(
                row,
                0,
                prompt,
                max(0, width - 1),
                curses.A_REVERSE,
            )

            stdscr.refresh()

            available = max(1, width - len(prompt) - 2)

            raw = stdscr.getstr(
                row,
                len(prompt),
                available,
            )

            query = raw.decode(
                "utf-8",
                errors="replace",
            ).strip()

            self.search_query = query
            self._rebuild_rows()

            if query:
                for index, row_item in enumerate(self.rows):
                    zone = getattr(row_item, "zone", None)

                    if zone is None:
                        continue

                    zone_name = getattr(zone, "name", "")

                    if query.casefold() in zone_name.casefold():
                        self.selected = index
                        break
                else:
                    self.selected = 0

            else:
                self.selected = 0

        except curses.error:
            pass

        finally:
            curses.noecho()

            try:
                curses.curs_set(0)
            except curses.error:
                pass

            try:
                stdscr.nodelay(True)
            except curses.error:
                pass
'''


def main() -> None:
    source = UI_FILE.read_text(encoding="utf-8")

    updated = replace_method(
        source,
        "_search",
        NEW_SEARCH,
    )

    ast.parse(updated, filename=str(UI_FILE))

    backup_path = backup(UI_FILE)
    UI_FILE.write_text(updated, encoding="utf-8")

    print("OK: naprawiono wyszukiwanie domen na głównym ekranie")
    print(f"Plik:   {UI_FILE}")
    print(f"Backup: {backup_path}")


if __name__ == "__main__":
    main()
