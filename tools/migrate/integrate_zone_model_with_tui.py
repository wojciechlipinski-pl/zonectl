from __future__ import annotations

import ast
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


def add_import(source: str) -> str:
    import_line = (
        "from elkman_dns.core.zone_model import ZoneModel\n"
    )

    if import_line in source:
        return source

    parser_import = (
        "from elkman_dns.core.zone_parser import "
    )

    index = source.find(parser_import)

    if index != -1:
        line_end = source.find("\n", index)

        if line_end == -1:
            raise RuntimeError(
                "Nie udało się znaleźć końca importu zone_parser"
            )

        return (
            source[: line_end + 1]
            + import_line
            + source[line_end + 1 :]
        )

    # Awaryjnie dodajemy po importach przyszłości.
    future_line = "from __future__ import annotations\n"

    if future_line in source:
        return source.replace(
            future_line,
            future_line + "\n" + import_line,
            1,
        )

    raise RuntimeError(
        "Nie znaleziono miejsca do dodania importu ZoneModel"
    )


def replace_once(
    source: str,
    old: str,
    new: str,
    description: str,
) -> str:
    if new in source:
        print(f"JUŻ JEST: {description}")
        return source

    count = source.count(old)

    if count != 1:
        raise RuntimeError(
            f"{description}: oczekiwano 1 wystąpienia, znaleziono {count}"
        )

    print(f"OK: {description}")
    return source.replace(old, new, 1)


def main() -> None:
    if not TARGET.exists():
        raise SystemExit(f"Brak pliku: {TARGET}")

    source = TARGET.read_text(encoding="utf-8")
    updated = add_import(source)

    updated = replace_once(
        updated,
        '''        records, error = self.bind.parsed_zone_records(zone)
        selected = 0
''',
        '''        records, error = self.bind.parsed_zone_records(zone)
        model = ZoneModel(zone.name, records)
        selected = 0
''',
        "utworzenie ZoneModel po odczytaniu rekordów",
    )

    updated = replace_once(
        updated,
        '''        def ordered_records():
            if sort_mode == 1:
''',
        '''        def ordered_records():
            records = list(model.records)

            if sort_mode == 1:
''',
        "pobieranie rekordów tabeli z ZoneModel",
    )

    updated = replace_once(
        updated,
        '''                f"Rekordy: {len(visible_records)}/{len(records)}"
                f"   Sortowanie: {sort_names[sort_mode]}"
''',
        '''                f"Rekordy: {len(visible_records)}/{len(model.records)}"
                f"   Sortowanie: {sort_names[sort_mode]}"
                f"   Zmiany: {model.change_count}"
''',
        "licznik rekordów i zmian z ZoneModel",
    )

    ast.parse(updated, filename=str(TARGET))

    backup_path = backup(TARGET)
    TARGET.write_text(updated, encoding="utf-8")

    print()
    print(f"Backup: {backup_path}")
    print(f"Zapisano: {TARGET}")
    print("Integracja ZoneModel z TUI zakończona")


if __name__ == "__main__":
    main()
