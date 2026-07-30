from __future__ import annotations

from zonectl.ui.credits import draw_project_credits
from zonectl.core.zone_model import ChangeKind, ZoneChange, ZoneModel
from zonectl.ui.dialogs import CursesDialogs
from zonectl.ui.function_keys import decode_function_key
from zonectl.ui.records.editor import RecordEditor
from zonectl.ui.records.new_record import NewRecordDialog
from zonectl.ui.records.renderer import RecordRenderer

import curses
import queue
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .. import __version__
from ..core.bind import BindService
from ..core.config import ToolkitConfig
from ..core.models import Health, Zone, ZoneStatus
from ..core.transaction import TransactionEngine, TransactionResult
from ..core.zone_edit_session import (
    ZoneEditSession,
    ZoneEditSessionError,
)
from ..presentation import transaction_lines, transaction_title


@dataclass(slots=True)
class Row:
    kind: str  # group | zone
    label: str
    zone: Zone | None = None
    count: int = 0


class CursesApp:
    SORTS = ("A-Z", "Health", "DNSSEC", "Serial")

    def __init__(
        self,
        zones: list[Zone],
        bind: BindService,
        group_order: list[str] | None = None,
        *,
        config: ToolkitConfig | None = None,
    ):
        self.all_zones = zones
        self.bind = bind
        self.group_order = group_order or []
        self.transaction_engine = (
            TransactionEngine(config)
            if config is not None
            else None
        )
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
            key = self._get_key(
                stdscr,
                restore_timeout=150,
            )
            if key in (ord("q"), 27, curses.KEY_F10):
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
        title = f" ZoneCTL {__version__} "
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
                if row.zone.health_profile == "rpz":
                    age = (
                        f"{status.file_age_seconds // 60:02d}m"
                        if status.file_age_seconds is not None
                        else "-"
                    )
                    line = (
                        f"   {marker} {row.zone.name:<38} "
                        f"{status.health.value:<7} RPZ  AGE {age}"
                    )
                else:
                    dnssec = "✔" if status.dnssec is True else "✘" if status.dnssec is False else "?"
                    serial = status.local_serial or "-"
                    line = f"   {marker} {row.zone.name:<38} {status.health.value:<7} DNSSEC {dnssec}  SOA {serial}"
                attr = self._color(status.health)
            if idx == self.selected:
                attr |= curses.A_REVERSE
            win.addnstr(screen_row, 0, line.ljust(width), max(0, width - 1), attr)

        footer = " Enter/Spacja otwórz-zwiń  / szukaj  g grupy  F7/s sortuj  r odśwież  q/Esc/F10 wyjście "
        win.addnstr(height - 2, 0, footer.ljust(width), max(0, width - 1), curses.A_REVERSE)
        draw_project_credits(win)
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
        """Wyświetla i edytuje źródłowy dokument strefy."""
        if self.transaction_engine is None:
            self._message_view(
                win,
                title="Błąd konfiguracji",
                lines=[
                    "Brak TransactionEngine.",
                    "Aplikacja TUI nie otrzymała ToolkitConfig.",
                ],
                error=True,
            )
            return

        try:
            session = ZoneEditSession(
                zone,
                self.transaction_engine,
            )
        except ZoneEditSessionError as exc:
            self._message_view(
                win,
                title=f"Nie można otworzyć: {zone.name}",
                lines=[str(exc)],
                error=True,
            )
            return
        except Exception as exc:
            self._message_view(
                win,
                title=f"Błąd otwierania: {zone.name}",
                lines=[f"{type(exc).__name__}: {exc}"],
                error=True,
            )
            return

        model = session.model
        error = None
        selected = 0
        offset = 0
        sort_mode = 0
        search_query = ""

        sort_names = ("Nazwa", "Typ", "TTL")

        def ordered_records():
            views = list(model.record_views)

            def name_key(view):
                record = view.record
                return (
                    record.relative_owner(zone.name).casefold(),
                    record.rtype.casefold(),
                    record.rdata.casefold(),
                    view.identifier,
                )

            def type_key(view):
                record = view.record
                return (
                    record.rtype.casefold(),
                    record.relative_owner(zone.name).casefold(),
                    record.rdata.casefold(),
                    view.identifier,
                )

            def ttl_key(view):
                record = view.record
                return (
                    record.ttl is None,
                    record.ttl or 0,
                    record.relative_owner(zone.name).casefold(),
                    record.rtype.casefold(),
                    view.identifier,
                )

            if sort_mode == 1:
                result = sorted(views, key=type_key)
            elif sort_mode == 2:
                result = sorted(views, key=ttl_key)
            else:
                result = sorted(views, key=name_key)

            query = search_query.strip().casefold()

            if not query:
                return result

            filtered = []

            for view in result:
                record = view.record
                owner = record.relative_owner(zone.name)
                ttl = "" if record.ttl is None else str(record.ttl)

                searchable = " ".join(
                    (
                        view.marker,
                        owner,
                        record.rtype,
                        ttl,
                        record.rdata,
                    )
                ).casefold()

                if query in searchable:
                    filtered.append(view)

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
                total_count=len(model.record_views),
                selected=selected,
                offset=offset,
                sort_name=sort_names[sort_mode],
                change_count=model.change_count,
                search_query=search_query,
                error=error,
                error_attr=self._color(Health.FAIL),
            )

            key = self._get_key(win)

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
                if model.dirty:
                    discard = CursesDialogs.confirm(
                        win,
                        "Są niezapisane zmiany. Porzucić je?",
                    )

                    if not discard:
                        continue

                    session.discard()

                return

            # F2 / Ctrl+S
            if key in (curses.KEY_F2, 19):
                if not model.dirty:
                    self._message_view(
                        win,
                        title=f"Zapis: {zone.name}",
                        lines=["Brak zmian do zapisania."],
                    )
                    continue

                confirmed = CursesDialogs.confirm(
                    win,
                    (
                        f"Zapisać {model.change_count} "
                        f"zmian w strefie {zone.name}?"
                    ),
                )

                if not confirmed:
                    continue

                try:
                    save_result = session.save(
                        commit=True,
                    )
                except Exception as exc:
                    self._message_view(
                        win,
                        title=f"Błąd zapisu: {zone.name}",
                        lines=[
                            f"{type(exc).__name__}: {exc}",
                        ],
                        error=True,
                    )
                    continue

                self._transaction_result_view(
                    win,
                    save_result.transaction,
                )

                if (
                    save_result.transaction.committed
                    or save_result.transaction.status
                    == "NO-CHANGE"
                ):
                    if (
                        save_result.transaction.status
                        == "NO-CHANGE"
                    ):
                        session.reload()

                    model = session.model
                    selected = 0
                    offset = 0
                    search_query = ""

                    self._start_refresh(force=True)

                continue

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
                    session,
                    model,
                    zone,
                )
                model = session.model
                selected = 0
                offset = 0
                search_query = ""
                continue

            if key in (ord("d"), ord("D")):
                self._diff_view(win, session)
                continue

            if key in (ord("x"), ord("X")):
                self._export_diff(win, session)
                continue

            if key in (ord("u"), ord("U")):
                if session.undo():
                    model = session.model
                    selected = min(
                        selected,
                        max(0, len(model.record_views) - 1),
                    )
                    offset = min(offset, selected)
                    search_query = ""
                else:
                    self._message_view(
                        win,
                        title=f"Cofanie: {zone.name}",
                        lines=["Brak zmian do cofnięcia."],
                    )
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
                    identifiers_before = {
                        view.identifier
                        for view in model.record_views
                    }

                    model.add(new_record)

                    added_view = next(
                        (
                            view
                            for view in model.record_views
                            if view.identifier not in identifiers_before
                        ),
                        None,
                    )

                    search_query = ""
                    visible_records = ordered_records()

                    if added_view is not None:
                        try:
                            selected = next(
                                index
                                for index, view in enumerate(
                                    visible_records
                                )
                                if view.identifier
                                == added_view.identifier
                            )
                        except StopIteration:
                            selected = max(
                                0,
                                len(visible_records) - 1,
                            )
                    else:
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

                current_view = visible_records[selected]

                if current_view.deleted:
                    continue

                current_record = current_view.record

                edited_record = RecordEditor(
                    error_attr=self._color(Health.FAIL),
                ).edit_record_dialog(
                    win,
                    current_record,
                    zone,
                )

                if edited_record is not None:
                    model.replace_by_identifier(
                        current_view.identifier,
                        edited_record,
                    )

                    visible_records = ordered_records()

                    try:
                        selected = next(
                            index
                            for index, view in enumerate(
                                visible_records
                            )
                            if view.identifier
                            == current_view.identifier
                        )
                    except StopIteration:
                        selected = 0

                    offset = min(offset, selected)

                continue

            if key == curses.KEY_DC:
                if not visible_records:
                    continue

                current_view = visible_records[selected]

                if current_view.deleted:
                    continue

                model.delete_by_identifier(
                    current_view.identifier
                )

                visible_records = ordered_records()

                try:
                    selected = next(
                        index
                        for index, view in enumerate(
                            visible_records
                        )
                        if view.identifier
                        == current_view.identifier
                    )
                except StopIteration:
                    selected = min(
                        selected,
                        max(0, len(visible_records) - 1),
                    )

                offset = min(offset, selected)
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




    def _message_view(
        self,
        win: curses.window,
        *,
        title: str,
        lines: list[str],
        error: bool = False,
    ) -> None:
        """Wyświetla prosty modalny komunikat."""
        win.erase()
        height, width = win.getmaxyx()

        title_attr = curses.A_REVERSE | curses.A_BOLD
        body_attr = (
            self._color(Health.FAIL)
            if error
            else curses.A_NORMAL
        )

        try:
            win.addnstr(
                0,
                0,
                f" {title} ".ljust(width),
                max(0, width - 1),
                title_attr,
            )

            row = 2

            for line in lines:
                if row >= height - 2:
                    break

                win.addnstr(
                    row,
                    2,
                    str(line),
                    max(0, width - 4),
                    body_attr,
                )
                row += 1

            footer = " Dowolny klawisz — powrót "
            win.addnstr(
                height - 1,
                0,
                footer.ljust(width),
                max(0, width - 1),
                curses.A_REVERSE,
            )
            win.refresh()
            win.getch()

        except curses.error:
            pass

    @staticmethod
    def _function_key_sequence(
        sequence: list[int],
    ) -> int | None:
        return decode_function_key(sequence)

    @classmethod
    def _get_key(
        cls,
        win: curses.window,
        restore_timeout: int = -1,
    ) -> int:
        """
        Odczytuje klawisz i rozpoznaje F2 wysyłane jako ESC [ 12 ~.
        """
        key = win.getch()

        if key != 27:
            return key

        sequence: list[int] = []

        try:
            win.timeout(80)

            for _ in range(4):
                next_key = win.getch()

                if next_key == -1:
                    break

                sequence.append(next_key)
        finally:
            try:
                win.timeout(restore_timeout)
            except curses.error:
                pass

        function_key = cls._function_key_sequence(sequence)

        if function_key is not None:
            return function_key

        for item in reversed(sequence):
            try:
                curses.ungetch(item)
            except curses.error:
                break

        return 27

    def _transaction_result_view(
        self,
        win: curses.window,
        result: TransactionResult,
    ) -> None:
        """Wyświetla wynik zapisu lub rollbacku transakcji."""
        self._message_view(
            win,
            title=transaction_title(result),
            lines=transaction_lines(result),
            error=not result.ok,
        )

    def _pending_changes_view(
        self,
        win: curses.window,
        session: ZoneEditSession,
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
                "   d diff"
                "   x eksport"
                "   u cofnij"
                "   F2/Ctrl+S zapisz"
                "   PgUp/PgDn"
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
            key = self._get_key(win)

            if key in (
                ord("q"),
                ord("Q"),
                27,
                curses.KEY_BACKSPACE,
                127,
                8,
            ):
                return

            if key in (curses.KEY_F2, 19):
                if not changes:
                    self._message_view(
                        win,
                        title=f"Zapis: {zone.name}",
                        lines=["Brak zmian do zapisania."],
                    )
                    continue

                try:
                    save_result = session.save(commit=True)
                except Exception as exc:
                    self._message_view(
                        win,
                        title=f"Błąd zapisu: {zone.name}",
                        lines=[f"{type(exc).__name__}: {exc}"],
                        error=True,
                    )
                    continue

                self._transaction_result_view(
                    win,
                    save_result.transaction,
                )

                if (
                    save_result.transaction.committed
                    or save_result.transaction.status == "NO-CHANGE"
                ):
                    if save_result.transaction.status == "NO-CHANGE":
                        session.reload()
                    return

            if key in (ord("d"), ord("D")):
                self._diff_view(win, session)
                continue

            if key in (ord("x"), ord("X")):
                self._export_diff(win, session)
                continue

            if key in (ord("u"), ord("U")):
                if not session.undo():
                    self._message_view(
                        win,
                        title=f"Cofanie: {zone.name}",
                        lines=["Brak zmian do cofnięcia."],
                    )
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

    def _diff_view(
        self,
        win: curses.window,
        session: ZoneEditSession,
    ) -> None:
        """Wyświetl przewijany unified diff bez zapisywania strefy."""
        text = session.unified_diff()
        lines = (
            text.splitlines()
            if text
            else ["Brak różnic względem aktywnego pliku."]
        )
        offset = 0

        while True:
            win.erase()
            height, width = win.getmaxyx()
            visible = max(1, height - 4)
            offset = min(
                offset,
                max(0, len(lines) - visible),
            )

            try:
                win.addnstr(
                    0,
                    0,
                    f" Podgląd zmian: {session.zone.name} ".ljust(width),
                    max(0, width - 1),
                    curses.A_REVERSE | curses.A_BOLD,
                )

                for row, line in enumerate(
                    lines[offset:offset + visible],
                    start=2,
                ):
                    attr = curses.A_NORMAL

                    if line.startswith("+") and not line.startswith("+++"):
                        attr = self._color(Health.PASS)
                    elif line.startswith("-") and not line.startswith("---"):
                        attr = self._color(Health.FAIL)
                    elif line.startswith("@@"):
                        attr = curses.A_BOLD

                    win.addnstr(
                        row,
                        1,
                        line,
                        max(0, width - 2),
                        attr,
                    )

                footer = (
                    f" Linie {offset + 1}-"
                    f"{min(len(lines), offset + visible)}/{len(lines)}"
                    "   ↑/↓ PgUp/PgDn Home/End"
                    "   q/Esc powrót "
                )
                win.addnstr(
                    height - 1,
                    0,
                    footer.ljust(width),
                    max(0, width - 1),
                    curses.A_REVERSE,
                )
                win.refresh()
            except curses.error:
                pass

            key = self._get_key(win)

            if key in (
                ord("q"),
                ord("Q"),
                27,
                curses.KEY_BACKSPACE,
                127,
                8,
            ):
                return

            if key in (curses.KEY_DOWN, ord("j")):
                offset = min(
                    offset + 1,
                    max(0, len(lines) - visible),
                )
            elif key in (curses.KEY_UP, ord("k")):
                offset = max(0, offset - 1)
            elif key == curses.KEY_NPAGE:
                offset = min(
                    offset + visible,
                    max(0, len(lines) - visible),
                )
            elif key == curses.KEY_PPAGE:
                offset = max(0, offset - visible)
            elif key == curses.KEY_HOME:
                offset = 0
            elif key == curses.KEY_END:
                offset = max(0, len(lines) - visible)

    def _export_diff(
        self,
        win: curses.window,
        session: ZoneEditSession,
    ) -> None:
        """Wyeksportuj oczekujące zmiany bez wykonywania COMMIT."""
        try:
            destination = session.export_diff()
        except (OSError, ZoneEditSessionError) as exc:
            self._message_view(
                win,
                title=f"Eksport zmian: {session.zone.name}",
                lines=[str(exc)],
                error=True,
            )
            return

        self._message_view(
            win,
            title=f"Eksport zmian: {session.zone.name}",
            lines=[
                "Zapisano unified diff:",
                str(destination),
                "",
                "Aktywny plik strefy nie został zmieniony.",
            ],
        )

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
