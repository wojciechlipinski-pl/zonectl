from __future__ import annotations

import ast
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PARSER_FILE = ROOT / "src/elkman_dns/core/zone_parser.py"
BIND_FILE = ROOT / "src/elkman_dns/core/bind.py"
UI_FILE = ROOT / "src/elkman_dns/ui/curses_app.py"


PARSER_SOURCE = '''from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class DNSRecord:
    owner: str
    ttl: int | None
    rrclass: str
    rtype: str
    rdata: str
    raw: str

    def relative_owner(self, zone_name: str) -> str:
        zone = zone_name.rstrip(".").casefold()
        owner = self.owner.rstrip(".")
        lowered = owner.casefold()

        if lowered == zone:
            return "@"

        suffix = "." + zone
        if lowered.endswith(suffix):
            return owner[: -len(suffix)]

        return self.owner


class ZoneRecordParser:
    """Parser kanonicznego wyjścia `named-checkzone -D`."""

    IGNORED_PREFIXES = (
        "zone ",
        "loaded serial ",
    )

    @classmethod
    def parse_output(cls, output: str) -> list[DNSRecord]:
        records: list[DNSRecord] = []

        for raw_line in output.splitlines():
            line = raw_line.strip()

            if not line:
                continue

            lowered = line.casefold()

            if lowered == "ok":
                continue

            if any(
                lowered.startswith(prefix)
                for prefix in cls.IGNORED_PREFIXES
            ):
                continue

            record = cls.parse_line(line)

            if record is not None:
                records.append(record)

        return records

    @staticmethod
    def parse_line(line: str) -> DNSRecord | None:
        """
        Oczekiwany format kanoniczny:

            owner TTL CLASS TYPE RDATA

        RDATA pozostaje tekstem, dzięki czemu zachowujemy składnię
        rekordów TXT, SOA, MX, SRV, CAA i innych typów.
        """
        fields = line.split(None, 4)

        if len(fields) < 5:
            return None

        owner, ttl_text, rrclass, rtype, rdata = fields

        try:
            ttl = int(ttl_text)
        except ValueError:
            ttl = None

        return DNSRecord(
            owner=owner,
            ttl=ttl,
            rrclass=rrclass.upper(),
            rtype=rtype.upper(),
            rdata=rdata,
            raw=line,
        )
'''


BIND_IMPORT = "from .zone_parser import DNSRecord, ZoneRecordParser\n"


BIND_METHOD = '''
    def parsed_zone_records(
        self,
        zone: Zone,
    ) -> tuple[list[DNSRecord], str | None]:
        """Zwraca rekordy strefy przekształcone do modelu DNSRecord."""
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

        records = ZoneRecordParser.parse_output(result.stdout)
        return records, None
'''


NEW_RECORDS_VIEW = '''    def _records_view(self, win: curses.window, zone: Zone) -> None:
        """Wyświetla rekordy strefy jako tabelę."""
        records, error = self.bind.parsed_zone_records(zone)
        selected = 0
        offset = 0
        sort_mode = 0
        sort_names = ("Nazwa", "Typ", "TTL")

        def ordered_records():
            if sort_mode == 1:
                return sorted(
                    records,
                    key=lambda item: (
                        item.rtype.casefold(),
                        item.relative_owner(zone.name).casefold(),
                        item.rdata.casefold(),
                    ),
                )

            if sort_mode == 2:
                return sorted(
                    records,
                    key=lambda item: (
                        item.ttl is None,
                        item.ttl or 0,
                        item.relative_owner(zone.name).casefold(),
                    ),
                )

            return sorted(
                records,
                key=lambda item: (
                    item.relative_owner(zone.name).casefold(),
                    item.rtype.casefold(),
                    item.rdata.casefold(),
                ),
            )

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

            put(
                2,
                2,
                (
                    f"Rekordy: {len(visible_records)}"
                    f"   Sortowanie: {sort_names[sort_mode]}"
                ),
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
                selected = min(selected, len(visible_records) - 1)

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
                    ttl = str(record.ttl) if record.ttl is not None else "-"

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
            else:
                put(
                    list_top,
                    2,
                    "Brak rekordów do wyświetlenia.",
                    curses.A_DIM,
                )

            footer = (
                " ↑/↓ wybór"
                "   PgUp/PgDn"
                "   Home/End"
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

            if key in (ord("s"), ord("S"), curses.KEY_F7):
                sort_mode = (sort_mode + 1) % len(sort_names)
                selected = 0
                offset = 0
                continue

            if not visible_records:
                continue

            if key in (curses.KEY_DOWN, ord("j")):
                selected = min(
                    selected + 1,
                    len(visible_records) - 1,
                )

            elif key in (curses.KEY_UP, ord("k")):
                selected = max(selected - 1, 0)

            elif key == curses.KEY_NPAGE:
                selected = min(
                    selected + visible,
                    len(visible_records) - 1,
                )

            elif key == curses.KEY_PPAGE:
                selected = max(selected - visible, 0)

            elif key == curses.KEY_HOME:
                selected = 0

            elif key == curses.KEY_END:
                selected = len(visible_records) - 1
'''


def make_backup(path: Path) -> Path:
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


def insert_before_method(
    source: str,
    method_name: str,
    addition: str,
) -> str:
    marker = f"    def {method_name}("

    if marker not in source:
        raise RuntimeError(
            f"Nie znaleziono metody {method_name}()"
        )

    return source.replace(
        marker,
        addition.rstrip() + "\n\n" + marker,
        1,
    )


def update_parser() -> None:
    if PARSER_FILE.exists():
        current = PARSER_FILE.read_text(encoding="utf-8")

        if "class ZoneRecordParser" in current:
            print("Parser rekordów już istnieje")
            return

        make_backup(PARSER_FILE)

    ast.parse(PARSER_SOURCE, filename=str(PARSER_FILE))
    PARSER_FILE.write_text(PARSER_SOURCE, encoding="utf-8")
    print(f"OK: utworzono {PARSER_FILE}")


def update_bind() -> None:
    source = BIND_FILE.read_text(encoding="utf-8")

    if BIND_IMPORT not in source:
        marker = "from .runner import run\n"

        if marker not in source:
            raise RuntimeError(
                "Nie znaleziono importu runner.run"
            )

        source = source.replace(
            marker,
            marker + BIND_IMPORT,
            1,
        )

    if "def parsed_zone_records(" not in source:
        source = insert_before_method(
            source,
            "quick_status",
            BIND_METHOD,
        )

    ast.parse(source, filename=str(BIND_FILE))
    backup = make_backup(BIND_FILE)
    BIND_FILE.write_text(source, encoding="utf-8")

    print(f"OK: zmieniono {BIND_FILE}")
    print(f"Backup: {backup}")


def update_ui() -> None:
    source = UI_FILE.read_text(encoding="utf-8")
    source = replace_method(
        source,
        "_records_view",
        NEW_RECORDS_VIEW,
    )

    ast.parse(source, filename=str(UI_FILE))
    backup = make_backup(UI_FILE)
    UI_FILE.write_text(source, encoding="utf-8")

    print(f"OK: zmieniono {UI_FILE}")
    print(f"Backup: {backup}")


def main() -> None:
    update_parser()
    update_bind()
    update_ui()

    print("OK: parser i tabela rekordów zostały wdrożone")


if __name__ == "__main__":
    main()
