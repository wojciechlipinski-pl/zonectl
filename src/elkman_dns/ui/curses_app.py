from __future__ import annotations

from elkman_dns.core.zone_model import ChangeKind, ZoneChange, ZoneModel
from elkman_dns.ui.dialogs import CursesDialogs
from elkman_dns.ui.records.editor import RecordEditor
from elkman_dns.ui.records.new_record import NewRecordDialog
from elkman_dns.ui.records.renderer import RecordRenderer

import curses
import queue
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from ..core.bind import BindService
from ..core.models import Health, Zone, ZoneStatus


@dataclass(slots=True)
class Row:
    kind: str  # group | zone
    label: str
    zone: Zone | None = None
    count: int = 0


class CursesApp:
    SORTS = ("A-Z", "Health", "DNSSEC", "Serial")

    def __init__(self, zones: list[Zone], bind: BindService, group_order: list[str] | None = None):
        self.all_zones = zones
        self.bind = bind
        self.group_order = group_order or []
        self.statuses: dict[str, ZoneStatus] = {}
        self.selected = 0
        self.offset = 0
        self.query = ""
        self.grouped = True
        self.collapsed: set[str] = set()
        self.sort_index = 0
        self.rows: list[Row] = []
        self.messages: queue.Queue[tuple[str, ZoneStatus]] = queue.Queue()
        self.stop_event = threading.Event()
        self._rebuild_rows()

    def run(self) -> None:
        curses.wrapper(self._main)

    def _main(self, stdscr: curses.window) -> None:
        curses.curs_set(0)
        stdscr.keypad(True)
        stdscr.timeout(150)
        self._init_colors()
        self._start_refresh()
        while not self.stop_event.is_set():
            changed = self._consume_results()
            if changed and self.SORTS[self.sort_index] != "A-Z":
                self._rebuild_rows(keep_zone=self._selected_zone_name())
            self._draw(stdscr)
            key = stdscr.getch()
            if key in (ord("q"), 27):
                break
            if key in (curses.KEY_DOWN, ord("j")):
                self.selected = min(self.selected + 1, max(0, len(self.rows) - 1))
            elif key in (curses.KEY_UP, ord("k")):
                self.selected = max(0, self.selected - 1)
            elif key in (10, 13, curses.KEY_ENTER, ord(" ")):
                self._activate(stdscr)
            elif key == ord("/"):
                self._search(stdscr)
            elif key in (curses.KEY_F7, ord("s")):
                self.sort_index = (self.sort_index + 1) % len(self.SORTS)
                self._rebuild_rows(keep_zone=self._selected_zone_name())
            elif key == ord("g"):
                self.grouped = not self.grouped
                self._rebuild_rows(keep_zone=self._selected_zone_name())
            elif key == ord("r"):
                self._start_refresh(force=True)
        self.stop_event.set()

    def _init_colors(self) -> None:
        if not curses.has_colors():
            return
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)
        curses.init_pair(2, curses.COLOR_YELLOW, -1)
        curses.init_pair(3, curses.COLOR_RED, -1)
        curses.init_pair(4, curses.COLOR_CYAN, -1)

    def _color(self, health: Health) -> int:
        if not curses.has_colors():
            return curses.A_NORMAL
        return {
            Health.PASS: curses.color_pair(1),
            Health.WARN: curses.color_pair(2),
            Health.FAIL: curses.color_pair(3),
            Health.UNKNOWN: curses.A_DIM,
        }[health]

    @staticmethod
    def _symbol(health: Health) -> str:
        return {Health.PASS: "●", Health.WARN: "●", Health.FAIL: "●", Health.UNKNOWN: "○"}[health]

    def _start_refresh(self, force: bool = False) -> None:
        if getattr(self, "worker", None) and self.worker.is_alive():
            if not force:
                return
            return  # do not start two concurrent scans
        self.worker = threading.Thread(target=self._refresh_worker, daemon=True)
        self.worker.start()

    def _refresh_worker(self) -> None:
        with ThreadPoolExecutor(max_workers=min(8, max(1, len(self.all_zones)))) as pool:
            futures = {pool.submit(self.bind.quick_status, zone): zone.name for zone in self.all_zones}
            for future in as_completed(futures):
                if self.stop_event.is_set():
                    return
                name = futures[future]
                try:
                    status = future.result()
                except Exception as exc:
                    zone = next(z for z in self.all_zones if z.name == name)
                    status = ZoneStatus(zone=zone, health=Health.FAIL, message=str(exc))
                self.messages.put((name, status))

    def _consume_results(self) -> bool:
        changed = False
        while True:
            try:
                name, status = self.messages.get_nowait()
            except queue.Empty:
                break
            self.statuses[name] = status
            changed = True
        return changed

    def _zone_key(self, zone: Zone):
        status = self.statuses.get(zone.name, ZoneStatus(zone=zone))
        mode = self.SORTS[self.sort_index]
        if mode == "Health":
            rank = {Health.FAIL: 0, Health.WARN: 1, Health.UNKNOWN: 2, Health.PASS: 3}[status.health]
            return rank, zone.name.casefold()
        if mode == "DNSSEC":
            rank = {False: 0, None: 1, True: 2}[status.dnssec]
            return rank, zone.name.casefold()
        if mode == "Serial":
            mismatch = bool(
                (zone.dns2 and status.dns2_serial != status.local_serial)
                or (zone.he and status.he_serial != status.local_serial)
            )
            return (0 if mismatch else 1), zone.name.casefold()
        return zone.name.casefold(),

    def _ordered_groups(self, groups: dict[str, list[Zone]]) -> list[str]:
        configured = [name for name in self.group_order if name in groups]
        remaining = sorted((name for name in groups if name not in configured and name != "Pozostałe"), key=str.casefold)
        if "Pozostałe" in groups:
            remaining.append("Pozostałe")
        return configured + remaining

    def _rebuild_rows(self, keep_zone: str | None = None) -> None:
        q = self.query.casefold()
        zones = [z for z in self.all_zones if q in z.name.casefold() or q in z.group.casefold()]
        rows: list[Row] = []
        if self.grouped:
            groups: dict[str, list[Zone]] = {}
            for zone in zones:
                groups.setdefault(zone.group, []).append(zone)
            for group in self._ordered_groups(groups):
                members = sorted(groups[group], key=self._zone_key)
                rows.append(Row("group", group, count=len(members)))
                if group not in self.collapsed:
                    rows.extend(Row("zone", z.name, zone=z) for z in members)
        else:
            rows = [Row("zone", z.name, zone=z) for z in sorted(zones, key=self._zone_key)]
        self.rows = rows
        self.selected = min(self.selected, max(0, len(rows) - 1))
        if keep_zone:
            for idx, row in enumerate(rows):
                if row.zone and row.zone.name == keep_zone:
                    self.selected = idx
                    break
        self.offset = min(self.offset, self.selected)

    def _selected_zone_name(self) -> str | None:
        if self.rows and self.rows[self.selected].zone:
            return self.rows[self.selected].zone.name
        return None

    def _draw(self, win: curses.window) -> None:
        win.erase()
        height, width = win.getmaxyx()
        title = " elkman DNS Toolkit 3.1.0 — Transaction Layer "
        win.addnstr(0, 0, title.ljust(width), width, curses.A_REVERSE | curses.A_BOLD)
        checked = len(self.statuses)
        subtitle = (
            f" Domeny: {len(self.all_zones)}  Sprawdzone: {checked}/{len(self.all_zones)}  "
            f"Widok: {'grupy' if self.grouped else 'lista'}  Sort: {self.SORTS[self.sort_index]}  "
            f"Szukaj: {self.query or '-'}"
        )
        win.addnstr(2, 0, subtitle, max(0, width - 1), curses.A_BOLD)
        list_top = 4
        footer_lines = 3
        visible = max(1, height - list_top - footer_lines)
        if self.selected < self.offset:
            self.offset = self.selected
        if self.selected >= self.offset + visible:
            self.offset = self.selected - visible + 1

        for screen_row, row in enumerate(self.rows[self.offset:self.offset + visible], start=list_top):
            idx = self.offset + screen_row - list_top
            attr = curses.A_NORMAL
            if row.kind == "group":
                arrow = "▸" if row.label in self.collapsed else "▾"
                line = f" {arrow} {row.label} ({row.count})"
                attr = curses.A_BOLD | (curses.color_pair(4) if curses.has_colors() else 0)
            else:
                assert row.zone is not None
                status = self.statuses.get(row.zone.name, ZoneStatus(zone=row.zone))
                marker = self._symbol(status.health)
                dnssec = "✔" if status.dnssec is True else "✘" if status.dnssec is False else "?"
                serial = status.local_serial or "-"
                line = f"   {marker} {row.zone.name:<38} {status.health.value:<7} DNSSEC {dnssec}  SOA {serial}"
                attr = self._color(status.health)
            if idx == self.selected:
                attr |= curses.A_REVERSE
            win.addnstr(screen_row, 0, line.ljust(width), max(0, width - 1), attr)

        footer = " Enter/Spacja otwórz-zwiń  / szukaj  g grupy  F7/s sortuj  r odśwież  q wyjście "
        win.addnstr(height - 2, 0, footer.ljust(width), max(0, width - 1), curses.A_REVERSE)
        win.refresh()

    def _activate(self, win: curses.window) -> None:
        if not self.rows:
            return
        row = self.rows[self.selected]
        if row.kind == "group":
            if row.label in self.collapsed:
                self.collapsed.remove(row.label)
            else:
                self.collapsed.add(row.label)
            self._rebuild_rows()
        elif row.zone:
            self._domain_view(win, row.zone)

    def _search(self, stdscr: curses.window) -> None:
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

    def _records_view(self, win: curses.window, zone: Zone) -> None:
        """Wyświetla rekordy strefy jako przeszukiwalną tabelę."""
        records, error = self.bind.parsed_zone_records(zone)
        model = ZoneModel(zone.name, records)
        selected = 0
        offset = 0
        sort_mode = 0
        search_query = ""

        sort_names = ("Nazwa", "Typ", "TTL")

        def ordered_records():
            records = list(model.records)

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

        while True:
            visible_records = ordered_records()

            height, width = win.getmaxyx()
            visible = RecordRenderer.visible_rows(height)

            if visible_records:
                selected = min(selected, len(visible_records) - 1)

                if selected < offset:
                    offset = selected

                if selected >= offset + visible:
                    offset = selected - visible + 1

            RecordRenderer.draw(
                win,
                zone_name=zone.name,
                records=visible_records,
                total_count=len(model.records),
                selected=selected,
                offset=offset,
                sort_name=sort_names[sort_mode],
                change_count=model.change_count,
                search_query=search_query,
                error=error,
                error_attr=self._color(Health.FAIL),
            )

            key = win.getch()

            if error:
                if key in (
                    ord("q"),
                    27,
                    curses.KEY_BACKSPACE,
                    127,
                    8,
                ):
                    return

                continue

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

            if key in (ord("p"), ord("P")):
                self._pending_changes_view(
                    win,
                    model,
                    zone,
                )
                selected = 0
                offset = 0
                continue

            if key in (ord("a"), ord("A")):
                new_record = NewRecordDialog(
                    error_attr=self._color(Health.FAIL),
                ).create_record_dialog(
                    win=win,
                    zone=zone,
                    records=model.records,
                )

                if new_record is not None:
                    added_index = model.add(new_record)

                    search_query = ""
                    visible_records = ordered_records()

                    try:
                        added_record = model.records[added_index]
                        selected = visible_records.index(added_record)
                    except (IndexError, ValueError):
                        selected = max(
                            0,
                            len(visible_records) - 1,
                        )

                    offset = max(
                        0,
                        selected - max(1, visible) + 1,
                    )

                continue

            if key in (ord("e"), ord("E")):
                if not visible_records:
                    continue

                current_record = visible_records[selected]

                try:
                    model_index = model.records.index(current_record)
                except ValueError:
                    continue

                edited_record = RecordEditor(
                    error_attr=self._color(Health.FAIL),
                ).edit_record_dialog(
                    win,
                    current_record,
                    zone,
                )

                if edited_record is not None:
                    model.replace(model_index, edited_record)
                    selected = 0
                    offset = 0

                continue

            if key in (ord("c"), ord("C")):
                if search_query:
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




    def _pending_changes_view(
        self,
        win: curses.window,
        model: ZoneModel,
        zone: Zone,
    ) -> None:
        """Wyświetla oczekujące zmiany w rekordach strefy."""
        selected = 0
        offset = 0

        labels = {
            ChangeKind.ADD: ("+", "DODANO"),
            ChangeKind.MODIFY: ("~", "ZMIENIONO"),
            ChangeKind.DELETE: ("-", "USUNIĘTO"),
        }

        def record_text(change: ZoneChange) -> str:
            record = change.record
            owner = record.relative_owner(zone.name)
            ttl = str(record.ttl) if record.ttl is not None else "-"
            return f"{owner:<28} {record.rtype:<7} {ttl:<10} {record.rdata}"

        while True:
            changes = model.pending_changes
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

            title = f" Oczekujące zmiany: {zone.name} "
            put(
                0,
                0,
                title.ljust(width),
                curses.A_REVERSE | curses.A_BOLD,
            )

            put(
                2,
                2,
                f"Liczba zmian: {len(changes)}",
                curses.A_BOLD,
            )

            list_top = 5
            visible = max(1, height - list_top - 3)

            if changes:
                selected = min(selected, len(changes) - 1)

                if selected < offset:
                    offset = selected

                if selected >= offset + visible:
                    offset = selected - visible + 1

                put(
                    4,
                    1,
                    "  STATUS       NAZWA                        TYP     TTL        WARTOŚĆ",
                    curses.A_BOLD,
                )

                for screen_row, change in enumerate(
                    changes[offset:offset + visible],
                    start=list_top,
                ):
                    index = offset + screen_row - list_top
                    symbol, label = labels[change.kind]

                    attr = (
                        curses.A_REVERSE
                        if index == selected
                        else curses.A_NORMAL
                    )

                    line = f"{symbol} {label:<11} {record_text(change)}"
                    put(screen_row, 1, line, attr)
            else:
                put(
                    list_top,
                    2,
                    "Brak oczekujących zmian.",
                    curses.A_DIM,
                )

            footer = (
                " ↑/↓ wybór"
                "   PgUp/PgDn przewijanie"
                "   Home/End"
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
                ord("Q"),
                27,
                curses.KEY_BACKSPACE,
                127,
                8,
            ):
                return

            if not changes:
                continue

            if key in (
                curses.KEY_DOWN,
                ord("j"),
                ord("n"),
            ):
                selected = min(selected + 1, len(changes) - 1)
            elif key in (
                curses.KEY_UP,
                ord("k"),
                ord("N"),
            ):
                selected = max(selected - 1, 0)
            elif key == curses.KEY_NPAGE:
                selected = min(selected + visible, len(changes) - 1)
            elif key == curses.KEY_PPAGE:
                selected = max(selected - visible, 0)
            elif key == curses.KEY_HOME:
                selected = 0
            elif key == curses.KEY_END:
                selected = len(changes) - 1

    def _domain_view(self, win: curses.window, zone: Zone) -> None:
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
                " v rekordy"
                "   r odśwież strefę"
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

            if key in (ord("v"), ord("V")):
                self._records_view(win, zone)
                continue

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
    @staticmethod
    def _serial_ok(zone: Zone, status: ZoneStatus) -> bool:
        if not status.local_serial:
            return False
        if zone.dns2 and status.dns2_serial != status.local_serial:
            return False
        if zone.he and status.he_serial != status.local_serial:
            return False
        return True

    @staticmethod
    def _bool_text(value: bool | None) -> str:
        if value is True:
            return "✔"
        if value is False:
            return "✘"
        return "?"
