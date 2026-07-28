from __future__ import annotations

import ast
import shutil
from datetime import datetime
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
TARGET = PROJECT / "src/elkman_dns/ui/curses_app.py"


DOMAIN_VIEW = '''    def _domain_view(self, win: curses.window, zone: Zone) -> None:
        """
        Wyświetla szczegóły wybranej strefy.

        Klawisze:
        - r: ponowne sprawdzenie strefy,
        - q / Esc / Backspace: powrót do listy.
        """
        status = self.statuses.get(
            zone.name,
            ZoneStatus(zone=zone),
        )
        notice = ""

        while True:
            win.erase()
            height, width = win.getmaxyx()

            def put(
                row: int,
                column: int,
                text: str,
                attr: int = curses.A_NORMAL,
            ) -> None:
                """Bezpiecznie wypisuje tekst także w małym terminalu."""
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

            title = f" Strefa DNS: {zone.name} "
            put(
                0,
                0,
                title.ljust(width),
                curses.A_REVERSE | curses.A_BOLD,
            )

            if height < 14 or width < 60:
                put(
                    2,
                    2,
                    "Terminal jest zbyt mały.",
                    curses.A_BOLD,
                )
                put(
                    4,
                    2,
                    "Minimalny zalecany rozmiar: 60x14.",
                )
                put(
                    height - 2,
                    0,
                    " q/Esc powrót ".ljust(width),
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

            health_attr = self._color(status.health) | curses.A_BOLD
            health_symbol = self._symbol(status.health)

            dnssec_text = (
                "WŁĄCZONY"
                if status.dnssec is True
                else "WYŁĄCZONY"
                if status.dnssec is False
                else "NIEZNANY"
            )

            file_text = str(zone.file) if zone.file else "-"
            file_exists_text = (
                "TAK"
                if status.file_exists is True
                else "NIE"
                if status.file_exists is False
                else "NIE SPRAWDZONO"
            )

            transfer_targets: list[str] = []
            if zone.dns2:
                transfer_targets.append("DNS2")
            if zone.he:
                transfer_targets.append("HE")
            transfer_text = ", ".join(transfer_targets) or "brak"

            serial_local = status.local_serial or "-"
            serial_dns2 = (
                status.dns2_serial or "-"
                if zone.dns2
                else "nieużywany"
            )
            serial_he = (
                status.he_serial or "-"
                if zone.he
                else "nieużywany"
            )

            put(2, 2, "STATUS", curses.A_BOLD)
            put(
                2,
                21,
                f"{health_symbol} {status.health.value}",
                health_attr,
            )

            put(3, 2, "Komunikat")
            put(3, 21, status.message or "-")

            put(5, 2, "KONFIGURACJA", curses.A_BOLD)
            put(6, 2, "Grupa")
            put(6, 21, zone.group)

            put(7, 2, "Plik strefy")
            put(7, 21, file_text)

            put(8, 2, "Plik istnieje")
            file_attr = (
                self._color(Health.PASS)
                if status.file_exists is True
                else self._color(Health.FAIL)
                if status.file_exists is False
                else curses.A_DIM
            )
            put(8, 21, file_exists_text, file_attr)

            put(9, 2, "Notify")
            put(9, 21, "TAK" if zone.notify else "NIE")

            put(10, 2, "Reload")
            put(10, 21, "TAK" if zone.reload else "NIE")

            put(11, 2, "Transfer")
            put(11, 21, transfer_text)

            put(13, 2, "STAN DNS", curses.A_BOLD)

            put(14, 2, "SOA LOCAL")
            put(14, 21, serial_local)

            put(15, 2, "SOA DNS2")
            dns2_attr = curses.A_NORMAL
            if zone.dns2:
                dns2_attr = (
                    self._color(Health.PASS)
                    if (
                        status.local_serial
                        and status.dns2_serial == status.local_serial
                    )
                    else self._color(Health.FAIL)
                )
            put(15, 21, serial_dns2, dns2_attr)

            put(16, 2, "SOA HE")
            he_attr = curses.A_NORMAL
            if zone.he:
                he_attr = (
                    self._color(Health.PASS)
                    if (
                        status.local_serial
                        and status.he_serial == status.local_serial
                    )
                    else self._color(Health.FAIL)
                )
            put(16, 21, serial_he, he_attr)

            put(17, 2, "DNSSEC")
            dnssec_attr = (
                self._color(Health.PASS)
                if status.dnssec is True
                else self._color(Health.WARN)
                if status.dnssec is False
                else curses.A_DIM
            )
            put(17, 21, dnssec_text, dnssec_attr)

            if zone.file:
                try:
                    stat = zone.file.stat()
                    put(19, 2, "ROZMIAR PLIKU")
                    put(19, 21, f"{stat.st_size} B")
                except OSError:
                    pass

            if notice:
                put(
                    height - 4,
                    2,
                    notice,
                    curses.A_BOLD,
                )

            footer = (
                " r odśwież strefę"
                "   q/Esc/Backspace powrót "
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

            if key in (ord("r"), ord("R")):
                notice = "Sprawdzanie strefy..."

                put(
                    height - 4,
                    2,
                    notice,
                    curses.A_BOLD,
                )
                win.refresh()

                try:
                    status = self.bind.quick_status(zone)
                    self.statuses[zone.name] = status
                    notice = "Odświeżono dane strefy."
                except Exception as exc:
                    status = ZoneStatus(
                        zone=zone,
                        health=Health.FAIL,
                        message=str(exc),
                    )
                    self.statuses[zone.name] = status
                    notice = f"Błąd odświeżania: {exc}"
'''


def locate_method(lines: list[str], method_name: str) -> tuple[int, int]:
    start: int | None = None

    for index, line in enumerate(lines):
        if line.startswith(f"    def {method_name}("):
            start = index
            break

    if start is None:
        raise RuntimeError(
            f"Nie znaleziono metody {method_name}() w {TARGET}"
        )

    end = len(lines)

    for index in range(start + 1, len(lines)):
        line = lines[index]

        if line.startswith("    def "):
            end = index
            break

        if line.startswith("    @"):
            end = index
            break

        if line.startswith("class "):
            end = index
            break

    return start, end


def validate(source: str) -> None:
    ast.parse(source, filename=str(TARGET))


def main() -> None:
    if not TARGET.exists():
        raise SystemExit(f"Brak pliku: {TARGET}")

    original = TARGET.read_text(encoding="utf-8")
    lines = original.splitlines()

    start, end = locate_method(lines, "_domain_view")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = TARGET.with_name(
        f"{TARGET.name}.bak-{timestamp}"
    )
    shutil.copy2(TARGET, backup)

    replacement = DOMAIN_VIEW.rstrip().splitlines()

    updated_lines = (
        lines[:start]
        + replacement
        + lines[end:]
    )

    updated = "\n".join(updated_lines).rstrip() + "\n"

    try:
        validate(updated)
        TARGET.write_text(updated, encoding="utf-8")
    except Exception:
        shutil.copy2(backup, TARGET)
        raise

    print("OK: wdrożono widok szczegółów domeny")
    print(f"Plik:   {TARGET}")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
