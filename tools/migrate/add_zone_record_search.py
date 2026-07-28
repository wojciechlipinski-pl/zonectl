from __future__ import annotations

import ast
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UI_FILE = ROOT / "src/elkman_dns/ui/curses_app.py"


NEW_RECORDS_VIEW = r'''    def _records_view(self, win: curses.window, zone: Zone) -> None:
        """Wyświetla rekordy strefy jako przeszukiwalną tabelę."""
        records, error = self.bind.parsed_zone_records(zone)
        selected = 0
        offset = 0
        sort_mode = 0
        search_query = ""

        sort_names = ("Nazwa", "Typ", "TTL")

        def ordered_records():
            if sort_mode == 1:
                result = sorted(
                    records,
                    key=lambda item: (
                        item.rtype.casefold(),
                        item.relative_owner(zone.name).casefold(),
                        item.rdata.casefold(),
                    ),
                )

            elif sort_mode == 2:
                result = sorted(
                    records,
                    key=lambda item: (
                        item.ttl is None,
                        item.ttl or 0,
                        item.relative_owner(zone.name).casefold(),
                    ),
                )

            else:
                result = sorted(
                    records,
                    key=lambda item: (
                        item.relative_owner(zone.name).casefold(),
                        item.rtype.casefold(),
                        item.rdata.casefold(),
                    ),
                )

            query = search_query.strip().casefold()

            if not query:
                return result

            filtered = []

            for record in result:
                owner = record.relative_owner(zone.name)
                ttl = "" if record.ttl is None else str(record.ttl)

                searchable = " ".join(
                    (
                        owner,
                        record.owner,
                        record.rtype,
                        record.rrclass,
                        ttl,
                        record.rdata,
                        record.raw,
                    )
                ).casefold()

                if query in searchable:
                    filtered.append(record)

            return filtered

        def prompt_search() -> str | None:
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

        while True:
            visible_records = ordered_records()

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
                put(
                    3,
                    2,
                    "Nie udało się odczytać rekordów:",
                    curses.A_BOLD,
                )
                put(
                    5,
                    2,
                    error,
                    self._color(Health.FAIL),
                )
                put(
                    height - 2,
                    0,
                    " q/Esc/Backspace powrót ".ljust(width),
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

            summary = (
                f"Rekordy: {len(visible_records)}/{len(records)}"
                f"   Sortowanie: {sort_names[sort_mode]}"
            )

            if search_query:
                summary += f'   Filtr: "{search_query}"'

            put(
                2,
                2,
                summary,
                curses.A_BOLD,
            )

            owner_width = max(12, min(28, width // 4))
            type_width = 7
            ttl_width = 10

            owner_column = 1
            type_column = owner_column + owner_width + 1
            ttl_column = type_column + type_width + 1
            value_column = ttl_column + ttl_width + 1

            put(4, owner_column, "NAZWA", curses.A_BOLD)
            put(4, type_column, "TYP", curses.A_BOLD)
            put(4, ttl_column, "TTL", curses.A_BOLD)
            put(4, value_column, "WARTOŚĆ", curses.A_BOLD)

            separator = "-" * max(1, width - 2)
            put(5, 1, separator, curses.A_DIM)

            list_top = 6
            visible = max(1, height - list_top - 3)

            if visible_records:
                selected = min(
                    selected,
                    len(visible_records) - 1,
                )

                if selected < offset:
                    offset = selected

                if selected >= offset + visible:
                    offset = selected - visible + 1

                for screen_row, record in enumerate(
                    visible_records[offset:offset + visible],
                    start=list_top,
                ):
                    index = offset + screen_row - list_top

                    attr = (
                        curses.A_REVERSE
                        if index == selected
                        else curses.A_NORMAL
                    )

                    owner = record.relative_owner(zone.name)
                    ttl = (
                        str(record.ttl)
                        if record.ttl is not None
                        else "-"
                    )

                    put(
                        screen_row,
                        owner_column,
                        owner[:owner_width].ljust(owner_width),
                        attr,
                    )
                    put(
                        screen_row,
                        type_column,
                        record.rtype[:type_width].ljust(type_width),
                        attr,
                    )
                    put(
                        screen_row,
                        ttl_column,
                        ttl[:ttl_width].ljust(ttl_width),
                        attr,
                    )
                    put(
                        screen_row,
                        value_column,
                        record.rdata,
                        attr,
                    )

            elif search_query:
                put(
                    list_top,
                    2,
                    f'Brak rekordów pasujących do: "{search_query}"',
                    curses.A_DIM,
                )

            else:
                put(
                    list_top,
                    2,
                    "Brak rekordów do wyświetlenia.",
                    curses.A_DIM,
                )

            footer = (
                " ↑/↓ wybór"
                "   / szukaj"
                "   n/N następny/poprzedni"
                "   c wyczyść"
                "   s sortuj"
                "   q powrót "
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

            if key == ord("/"):
                value = prompt_search()

                if value is not None:
                    search_query = value
                    selected = 0
                    offset = 0

                continue

            if key in (ord("c"), ord("C")):
                search_query = ""
                selected = 0
                offset = 0
                continue

            if key in (ord("s"), ord("S"), curses.KEY_F7):
                sort_mode = (sort_mode + 1) % len(sort_names)
                selected = 0
                offset = 0
                continue

            if not visible_records:
                continue

            if key in (
                curses.KEY_DOWN,
                ord("j"),
                ord("n"),
            ):
                selected = min(
                    selected + 1,
                    len(visible_records) - 1,
                )

            elif key in (
                curses.KEY_UP,
                ord("k"),
                ord("N"),
            ):
                selected = max(selected - 1, 0)

            elif key == curses.KEY_NPAGE:
                selected = min(
                    selected + visible,
                    len(visible_records) - 1,
                )

            elif key == curses.KEY_PPAGE:
                selected = max(
                    selected - visible,
                    0,
                )

            elif key == curses.KEY_HOME:
                selected = 0

            elif key == curses.KEY_END:
                selected = len(visible_records) - 1
'''


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
        raise RuntimeError(
            f"Nie znaleziono metody {method_name}()"
        )

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


def main() -> None:
    source = UI_FILE.read_text(encoding="utf-8")

    if 'def prompt_search()' in source:
        print("Wyszukiwanie rekordów jest już wdrożone")
        return

    updated = replace_method(
        source,
        "_records_view",
        NEW_RECORDS_VIEW,
    )

    ast.parse(updated, filename=str(UI_FILE))

    backup_path = backup(UI_FILE)
    UI_FILE.write_text(updated, encoding="utf-8")

    print("OK: wdrożono wyszukiwanie rekordów")
    print(f"Plik:   {UI_FILE}")
    print(f"Backup: {backup_path}")


if __name__ == "__main__":
    main()
