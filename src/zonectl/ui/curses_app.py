from __future__ import annotations

from zonectl.ui.credits import draw_project_credits
from zonectl.core.zone_model import ChangeKind, ZoneChange, ZoneModel
from zonectl.ui.dialogs import CursesDialogs
from zonectl.ui.function_keys import decode_function_key
from zonectl.ui.records.editor import RecordEditor
from zonectl.ui.records.new_record import NewRecordDialog
from zonectl.ui.records.controller import natural_name_key
from zonectl.ui.records.renderer import RecordRenderer
from zonectl.ui.zone_create_dialog import ZoneCreateDialog
from zonectl.ui.dnssec_status_view import DnssecStatusView

import curses
import queue
import threading
import textwrap
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from .. import __version__
from ..core.bind import BindService
from ..core.bind_access_inventory import (
    BindAccessInventoryError,
    BindAccessInventoryReader,
)
from ..core.bind_secondary_plan import BindSecondaryPlanError, BindSecondaryPlanner
from ..core.bind_secondary_report import BindSecondaryReporter
from ..core.bind_secondary_transaction import BindSecondaryTransaction
from ..core.bulk_operations import BulkOperation, BulkOperationError
from ..core.config import ToolkitConfig
from ..core.dnssec_ds_check import DnssecDsChecker
from ..core.dnssec_confirm_ds import DnssecConfirmDsTransaction
from ..core.dnssec_disable_plan import DnssecDisablePlanner
from ..core.dnssec_disable_transaction import DnssecDisableTransaction
from ..core.dnssec_enable_plan import DnssecEnablePlanner
from ..core.dnssec_enable_transaction import DnssecEnableTransaction
from ..core.dnssec_report import DnssecReporter
from ..core.dnssec_withdrawal_backup import DnssecWithdrawalBackup
from ..core.managed_zone_migration import (
    ManagedZoneMigrationError,
    ManagedZoneMigrationPlanner,
)
from ..core.managed_zone_migration_transaction import (
    ManagedZoneMigrationTransaction,
)
from ..core.edit_lock import ZoneEditLockedError
from ..core.models import Health, Zone, ZoneStatus
from ..core.multi_zone_session import (
    MultiZoneEditSession,
    MultiZoneSessionError,
)
from ..core.paths import EDIT_LOCK_DIR
from ..core.record_filter import RecordFilter, RecordFilterError
from ..core.record_validation import (
    ValidationSeverity,
    validate_zone,
)
from ..core.transaction import TransactionEngine, TransactionResult
from ..core.zone_edit_session import (
    ZoneEditSession,
    ZoneEditSessionError,
)
from ..core.zone_create_transaction import ZoneCreateTransaction
from ..core.zone_lifecycle import (
    ZoneCreateRequest,
    ZoneLifecycleError,
    ZoneLifecyclePlanner,
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
        self.config = config
        self.read_only = bool(
            config.read_only
            if config is not None
            else False
        )
        self.edit_lock_directory = (
            Path(
                config.toolkit.get(
                    "edit_lock_dir",
                    str(EDIT_LOCK_DIR),
                )
            )
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
        self.multi_selected: set[str] = set()
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
            elif key in (10, 13, curses.KEY_ENTER):
                self._activate(stdscr)
            elif key == ord(" "):
                self._toggle_multi_selection()
            elif key in (ord("m"), ord("M")):
                self._multi_zone_view(stdscr)
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
            elif key == curses.KEY_IC:
                self._create_zone_wizard(stdscr)
            elif key == curses.KEY_F9:
                self._bind_access_view(stdscr)
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
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_CYAN)

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
            f"Zaznaczone: {len(self.multi_selected)}  "
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
                selected_marker = (
                    "[x]"
                    if row.zone.name in self.multi_selected
                    else "[ ]"
                )
                if row.zone.health_profile == "rpz":
                    age = (
                        f"{status.file_age_seconds // 60:02d}m"
                        if status.file_age_seconds is not None
                        else "-"
                    )
                    line = (
                        f" {selected_marker} {marker} {row.zone.name:<38} "
                        f"{status.health.value:<7} RPZ  AGE {age}"
                    )
                else:
                    dnssec = "✔" if status.dnssec is True else "✘" if status.dnssec is False else "?"
                    serial = status.local_serial or "-"
                    line = f" {selected_marker} {marker} {row.zone.name:<38} {status.health.value:<7} DNSSEC {dnssec}  SOA {serial}"
                attr = self._color(status.health)
            if idx == self.selected:
                attr |= curses.A_REVERSE
            win.addnstr(screen_row, 0, line.ljust(width), max(0, width - 1), attr)

        footer = " Enter otwórz  Ins nowa strefa  F9 ACL/secondary  Spacja zaznacz  / szukaj  F7 sortuj  r odśwież  F10 wyjście "
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

    def _toggle_multi_selection(self) -> None:
        """Dodaj lub usuń bieżącą strefę z zestawu wielostrefowego."""
        if not self.rows:
            return
        zone = self.rows[self.selected].zone
        if zone is None:
            self._activate_group_selection()
            return
        if zone.name in self.multi_selected:
            self.multi_selected.remove(zone.name)
        else:
            self.multi_selected.add(zone.name)

    def _activate_group_selection(self) -> None:
        """Zachowaj dotychczasowe działanie Spacji dla nagłówka grupy."""
        if not self.rows:
            return
        row = self.rows[self.selected]
        if row.kind != "group":
            return
        if row.label in self.collapsed:
            self.collapsed.remove(row.label)
        else:
            self.collapsed.add(row.label)
        self._rebuild_rows()

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

    def _create_zone_wizard(self, win: curses.window) -> None:
        """Collect, preview and transactionally create a primary zone."""
        if self.read_only:
            self._message_view(
                win,
                title="Tryb tylko do odczytu",
                lines=[
                    "Tworzenie stref jest zablokowane.",
                    "Ustawienie: [toolkit] read_only = yes",
                ],
                error=True,
            )
            return

        toolkit = self.config.toolkit if self.config is not None else {}
        defaults = {
            "primary_ns": toolkit.get("default_primary_ns", "ns1.elkman.pl."),
            "admin": toolkit.get("default_soa_admin", "hostmaster.elkman.pl."),
            "nameservers": toolkit.get(
                "default_nameservers",
                "ns1.elkman.pl., ns2.elkman.pl.",
            ),
        }

        form = ZoneCreateDialog().collect(
            win,
            primary_ns=defaults["primary_ns"],
            admin=defaults["admin"],
            nameservers=defaults["nameservers"],
        )
        if form is None:
            return

        nameservers = tuple(
            value.strip()
            for value in form.nameservers.split(",")
            if value.strip()
        )
        try:
            plan = ZoneLifecyclePlanner(self.all_zones).plan_create(
                ZoneCreateRequest(
                    name=form.name,
                    primary_ns=form.primary_ns,
                    admin=form.admin,
                    nameservers=nameservers,
                    apex_ipv4=form.ipv4 or None,
                    apex_ipv6=form.ipv6 or None,
                    add_www=form.add_www,
                )
            )
        except ZoneLifecycleError as exc:
            self._message_view(
                win,
                title="Błąd planu nowej strefy",
                lines=[str(exc)],
                error=True,
            )
            return

        preview = [
            f"Strefa: {plan.zone_name}",
            f"Plik: {plan.zone_file}",
            f"Deklaracja: {plan.zone_declaration_file}",
            f"Serial: {plan.serial}",
            "",
            *plan.zone_text.splitlines(),
        ]
        self._message_view(
            win,
            title=f"Plan utworzenia: {plan.zone_name}",
            lines=preview,
        )
        if not CursesDialogs.confirm(
            win,
            f"Utworzyć i aktywować strefę {plan.zone_name}?",
        ):
            return

        result = ZoneCreateTransaction(
            Path("/var/backups/zonectl-zone-create/manifests")
        ).apply(plan, commit=True, activate=True)
        lines = [
            f"Status: {result.status}",
            f"Commit: {'TAK' if result.committed else 'NIE'}",
            f"Rollback: {'TAK' if result.rolled_back else 'NIE'}",
            "",
            *(
                f"[{'OK' if step.ok else 'BŁĄD'}] "
                f"{step.name}: {step.message}"
                for step in result.steps
            ),
        ]
        self._message_view(
            win,
            title=f"Tworzenie strefy: {plan.zone_name}",
            lines=lines,
            error=not (result.ok and result.status == "COMMIT"),
        )
        if result.ok and result.status == "COMMIT":
            self.all_zones.append(
                Zone(name=plan.zone_name, file=plan.zone_file)
            )
            self._rebuild_rows(keep_zone=plan.zone_name)

    def _records_view(
        self,
        win: curses.window,
        zone: Zone,
        *,
        existing_session: ZoneEditSession | None = None,
        keep_open: bool = False,
    ) -> None:
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
            session = existing_session or ZoneEditSession(
                zone,
                self.transaction_engine,
                read_only=self.read_only,
                edit_lock_directory=self.edit_lock_directory,
            )
        except ZoneEditLockedError as exc:
            self._message_view(
                win,
                title=f"Strefa jest już edytowana: {zone.name}",
                lines=[
                    str(exc),
                    "",
                    "Druga sesja może nadal otworzyć strefę",
                    "w trybie tylko do odczytu.",
                ],
                error=True,
            )
            return
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
                    natural_name_key(record.relative_owner(zone.name)),
                    record.rtype.casefold(),
                    record.rdata.casefold(),
                    view.identifier,
                )

            def type_key(view):
                record = view.record
                return (
                    record.rtype.casefold(),
                    natural_name_key(record.relative_owner(zone.name)),
                    record.rdata.casefold(),
                    view.identifier,
                )

            def ttl_key(view):
                record = view.record
                return (
                    record.ttl is None,
                    record.ttl or 0,
                    natural_name_key(record.relative_owner(zone.name)),
                    record.rtype.casefold(),
                    view.identifier,
                )

            if sort_mode == 1:
                result = sorted(views, key=type_key)
            elif sort_mode == 2:
                result = sorted(views, key=ttl_key)
            else:
                result = sorted(views, key=name_key)

            return RecordFilter(search_query).apply(
                result,
                zone.name,
            )

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
                read_only=self.read_only,
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
                    if not keep_open:
                        session.close()
                    return

                continue

            if key in (
                ord("q"),
                27,
                curses.KEY_BACKSPACE,
                127,
                8,
            ):
                if keep_open:
                    return
                if model.dirty:
                    discard = CursesDialogs.confirm(
                        win,
                        "Są niezapisane zmiany. Porzucić je?",
                    )

                    if not discard:
                        continue

                    session.discard()

                session.close()
                return

            # F2 / Ctrl+S
            if key in (curses.KEY_F2, 19):
                if self.read_only:
                    self._read_only_message(win, zone)
                    continue
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
                    try:
                        RecordFilter(value)
                    except RecordFilterError as exc:
                        self._message_view(
                            win,
                            title="Nieprawidłowy filtr",
                            lines=[
                                str(exc),
                                "",
                                "Przykład: type:A ttl>=3600 -name:test",
                            ],
                            error=True,
                        )
                        continue

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

            if key == curses.KEY_F3:
                self._diff_view(win, session)
                continue

            if key in (ord("x"), ord("X")):
                self._export_diff(win, session)
                continue

            if key in (ord("b"), ord("B")):
                if self.read_only:
                    self._read_only_message(win, zone)
                    continue
                self._bulk_operation_view(
                    win,
                    zone,
                    model,
                )
                selected = 0
                offset = 0
                search_query = ""
                continue

            if key in (ord("u"), ord("U")):
                if self.read_only:
                    self._read_only_message(win, zone)
                    continue
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

            if key == curses.KEY_IC:
                if self.read_only:
                    self._read_only_message(win, zone)
                    continue
                new_record = NewRecordDialog(
                    error_attr=self._color(Health.FAIL),
                ).create_record_dialog(
                    win=win,
                    zone=zone,
                    records=model.records,
                )

                if new_record is not None:
                    proposed_records = [
                        *model.records,
                        new_record,
                    ]
                    if not self._approve_zone_change(
                        win,
                        zone,
                        model.records,
                        proposed_records,
                    ):
                        continue

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

            if key == curses.KEY_F4:
                if self.read_only:
                    self._read_only_message(win, zone)
                    continue
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
                    proposed_records = [
                        (
                            edited_record
                            if view.identifier
                            == current_view.identifier
                            else view.record
                        )
                        for view in model.record_views
                        if not view.deleted
                    ]
                    if not self._approve_zone_change(
                        win,
                        zone,
                        model.records,
                        proposed_records,
                    ):
                        continue

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
                if self.read_only:
                    self._read_only_message(win, zone)
                    continue
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
        """Wyświetla zawijany i przewijany modalny komunikat."""
        title_attr = curses.A_REVERSE | curses.A_BOLD
        body_attr = (
            self._color(Health.FAIL)
            if error
            else curses.A_NORMAL
        )
        offset = 0
        try:
            win.timeout(-1)
            while True:
                win.erase()
                height, width = win.getmaxyx()
                wrapped = self._wrap_message_lines(lines, max(1, width - 4))
                visible = max(1, height - 4)
                maximum = max(0, len(wrapped) - visible)
                offset = min(offset, maximum)
                win.addnstr(
                    0,
                    0,
                    f" {title} ".ljust(width),
                    max(0, width - 1),
                    title_attr,
                )
                for row, line in enumerate(
                    wrapped[offset : offset + visible], start=2
                ):
                    win.addnstr(
                        row,
                        2,
                        line,
                        max(0, width - 4),
                        body_attr,
                    )
                footer = (
                    f" Linie {offset + 1}-{min(len(wrapped), offset + visible)}"
                    f"/{len(wrapped)}  ↑/↓ PgUp/PgDn Home/End  q/Esc powrót "
                )
                win.addnstr(
                    height - 1,
                    0,
                    footer.ljust(width),
                    max(0, width - 1),
                    curses.A_REVERSE,
                )
                win.refresh()
                key = self._get_key(win)
                if key in (curses.KEY_DOWN, ord("j")):
                    offset = min(offset + 1, maximum)
                elif key in (curses.KEY_UP, ord("k")):
                    offset = max(0, offset - 1)
                elif key == curses.KEY_NPAGE:
                    offset = min(offset + visible, maximum)
                elif key == curses.KEY_PPAGE:
                    offset = max(0, offset - visible)
                elif key == curses.KEY_HOME:
                    offset = 0
                elif key == curses.KEY_END:
                    offset = maximum
                else:
                    return
        except curses.error:
            pass
        finally:
            try:
                win.timeout(150)
            except curses.error:
                pass

    @staticmethod
    def _wrap_message_lines(lines: list[str], width: int) -> list[str]:
        """Zawijaj tekst, zachowując puste linie i wcięcie kontynuacji."""
        wrapped: list[str] = []
        for value in lines:
            line = str(value)
            if not line:
                wrapped.append("")
                continue
            indentation = line[: len(line) - len(line.lstrip())]
            wrapped.extend(
                textwrap.wrap(
                    line,
                    width=max(1, width),
                    subsequent_indent=indentation,
                    replace_whitespace=False,
                    drop_whitespace=True,
                    break_long_words=True,
                    break_on_hyphens=False,
                )
                or [""]
            )
        return wrapped

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
                "   F3 diff"
                "   x eksport"
                "   u cofnij"
                "   F2/Ctrl+S zapisz"
                "   PgUp/PgDn"
                "   Home/End"
                "   q powrót "
            )
            if self.read_only:
                footer = (
                    " TYLKO ODCZYT"
                    "   F3 diff"
                    "   x eksport"
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
                if self.read_only:
                    self._read_only_message(win, zone)
                    continue
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

            if key == curses.KEY_F3:
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

    def _read_only_message(
        self,
        win: curses.window,
        zone: Zone,
    ) -> None:
        self._message_view(
            win,
            title=f"Tylko odczyt: {zone.name}",
            lines=[
                "Modyfikowanie rekordów i COMMIT są zablokowane.",
                "Ustawienie: [toolkit] read_only = yes",
            ],
        )

    def _bulk_operation_view(
        self,
        win: curses.window,
        zone: Zone,
        model: ZoneModel,
    ) -> None:
        command = CursesDialogs.text_input(
            win,
            " Operacja masowa: ",
        )
        if command is None or not command.strip():
            return

        try:
            operation = BulkOperation.parse(command)
            matches = operation.matches(model)
        except BulkOperationError as exc:
            self._message_view(
                win,
                title="Nieprawidłowa operacja masowa",
                lines=[
                    str(exc),
                    "",
                    "Przykład: SELECT type:A SET ttl=7200",
                ],
                error=True,
            )
            return

        if not matches:
            self._message_view(
                win,
                title=f"Operacja masowa: {zone.name}",
                lines=["Filtr nie wskazał żadnego rekordu."],
            )
            return

        action = (
            "DELETE"
            if operation.action.value == "DELETE"
            else f"SET {operation.field}={operation.value}"
        )
        preview = [
            f"{match.before.relative_owner(zone.name):<24} "
            f"{match.before.rtype:<7} "
            f"{match.before.rdata}"
            for match in matches[:10]
        ]
        if len(matches) > len(preview):
            preview.append(
                f"... oraz {len(matches) - len(preview)} kolejnych"
            )

        if not self._bulk_preview_view(
            win,
            title=f"Podgląd operacji masowej: {zone.name}",
            lines=[
                f"Operacja: {action}",
                f"Dopasowane rekordy: {len(matches)}",
                "",
                *preview,
            ],
        ):
            return

        if not CursesDialogs.confirm(
            win,
            f"Zastosować {action} do {len(matches)} rekordów?",
            key_reader=self._get_key,
        ):
            return

        try:
            proposed = operation.proposed_records(model)
        except BulkOperationError as exc:
            self._message_view(
                win,
                title="Błąd operacji masowej",
                lines=[str(exc)],
                error=True,
            )
            return

        if not self._approve_zone_change(
            win,
            zone,
            model.records,
            proposed,
        ):
            return

        changed = operation.apply(model)
        self._message_view(
            win,
            title=f"Operacja masowa: {zone.name}",
            lines=[
                f"Zmieniono rekordów: {changed}",
                "Zmiany są tylko w bieżącej sesji.",
                "Klawisz u cofnie całą operację.",
                "COMMIT nie został wykonany.",
            ],
        )

    def _bulk_preview_view(
        self,
        win: curses.window,
        *,
        title: str,
        lines: list[str],
    ) -> bool:
        """Pokaż podgląd; Enter przechodzi do potwierdzenia."""
        win.erase()
        height, width = win.getmaxyx()

        try:
            win.addnstr(
                0,
                0,
                f" {title} ".ljust(width),
                max(0, width - 1),
                curses.A_REVERSE | curses.A_BOLD,
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
                    curses.A_NORMAL,
                )
                row += 1

            footer = " Enter — dalej    q/Esc — anuluj "
            win.addnstr(
                height - 1,
                0,
                footer.ljust(width),
                max(0, width - 1),
                curses.A_REVERSE,
            )
            win.refresh()

            while True:
                key = self._get_key(win)
                if key in (10, 13, curses.KEY_ENTER):
                    return True
                if key in (ord("q"), ord("Q"), 27):
                    return False
                # Pozostałe klawisze, w tym F1–F12, nie zamykają
                # ekranu podglądu.

        except curses.error:
            return False
        finally:
            try:
                win.timeout(150)
            except curses.error:
                pass

    def _approve_zone_change(
        self,
        win: curses.window,
        zone: Zone,
        current_records,
        proposed_records,
    ) -> bool:
        """Odrzuć nowe błędy i wymagaj potwierdzenia nowych ostrzeżeń."""
        existing = {
            issue.key
            for issue in validate_zone(
                zone.name,
                current_records,
            )
        }
        introduced = [
            issue
            for issue in validate_zone(
                zone.name,
                proposed_records,
            )
            if issue.key not in existing
        ]
        errors = [
            issue
            for issue in introduced
            if issue.severity is ValidationSeverity.ERROR
        ]
        warnings = [
            issue
            for issue in introduced
            if issue.severity is ValidationSeverity.WARN
        ]

        if errors:
            self._message_view(
                win,
                title=f"Błąd spójności: {zone.name}",
                lines=[
                    f"[{issue.code}] {issue.message}"
                    for issue in errors[:8]
                ],
                error=True,
            )
            return False

        if warnings:
            self._message_view(
                win,
                title=f"Ostrzeżenie: {zone.name}",
                lines=[
                    f"[{issue.code}] {issue.message}"
                    for issue in warnings[:8]
                ],
            )
            return CursesDialogs.confirm(
                win,
                "Kontynuować mimo ostrzeżeń?",
            )

        return True

    def _multi_zone_view(self, win: curses.window) -> None:
        """Edytuj kilka zaznaczonych stref w jednej sesji TUI."""
        selected_zones = [
            zone
            for zone in self.all_zones
            if zone.name in self.multi_selected
        ]
        if len(selected_zones) < 2:
            self._message_view(
                win,
                title="Sesja wielu stref",
                lines=[
                    "Zaznacz co najmniej dwie strefy klawiszem Spacja.",
                ],
            )
            return
        if self.transaction_engine is None:
            self._message_view(
                win,
                title="Sesja wielu stref",
                lines=["Brak TransactionEngine."],
                error=True,
            )
            return

        def factory(zone: Zone) -> ZoneEditSession:
            return ZoneEditSession(
                zone,
                self.transaction_engine,
                read_only=self.read_only,
                edit_lock_directory=self.edit_lock_directory,
            )

        multi = MultiZoneEditSession(selected_zones, factory)
        try:
            for zone in selected_zones:
                multi.open(zone.name)
        except Exception as exc:
            multi.close(discard=True)
            self._message_view(
                win,
                title="Nie można otworzyć sesji wielu stref",
                lines=[f"{type(exc).__name__}: {exc}"],
                error=True,
            )
            return

        selected = 0
        try:
            while True:
                win.erase()
                height, width = win.getmaxyx()
                win.addnstr(
                    0,
                    0,
                    " Sesja wielu stref ".ljust(width),
                    max(0, width - 1),
                    curses.A_REVERSE | curses.A_BOLD,
                )
                dirty = set(multi.dirty_zone_names)
                summary = (
                    f" Strefy: {len(selected_zones)}  "
                    f"Ze zmianami: {len(dirty)}"
                )
                win.addnstr(
                    2,
                    0,
                    summary,
                    max(0, width - 1),
                    curses.A_BOLD,
                )
                visible = max(1, height - 7)
                offset = max(
                    0,
                    min(
                        selected,
                        max(0, len(selected_zones) - visible),
                    ),
                )
                for row_number, zone in enumerate(
                    selected_zones[offset : offset + visible],
                    start=4,
                ):
                    index = offset + row_number - 4
                    session = multi.open(zone.name)
                    state = (
                        f"ZMIANY: {session.change_count}"
                        if session.dirty
                        else "bez zmian"
                    )
                    line = f" {zone.name:<42} {state}"
                    attr = (
                        curses.A_REVERSE
                        if index == selected
                        else curses.A_NORMAL
                    )
                    win.addnstr(
                        row_number,
                        0,
                        line.ljust(width),
                        max(0, width - 1),
                        attr,
                    )
                footer = (
                    " Enter edytuj  F2 waliduj i zapisz wszystkie  "
                    "q/Esc zakończ "
                )
                win.addnstr(
                    height - 2,
                    0,
                    footer.ljust(width),
                    max(0, width - 1),
                    curses.A_REVERSE,
                )
                win.refresh()
                key = self._get_key(win)

                if key in (curses.KEY_DOWN, ord("j")):
                    selected = min(
                        selected + 1,
                        len(selected_zones) - 1,
                    )
                    continue
                if key in (curses.KEY_UP, ord("k")):
                    selected = max(0, selected - 1)
                    continue
                if key in (10, 13, curses.KEY_ENTER):
                    zone = selected_zones[selected]
                    self._records_view(
                        win,
                        zone,
                        existing_session=multi.open(zone.name),
                        keep_open=True,
                    )
                    continue
                if key in (curses.KEY_F2, 19):
                    if self.read_only:
                        self._read_only_message(
                            win,
                            selected_zones[selected],
                        )
                        continue
                    if not dirty:
                        self._message_view(
                            win,
                            title="Sesja wielu stref",
                            lines=["Brak zmian do zapisania."],
                        )
                        continue
                    if not CursesDialogs.confirm(
                        win,
                        (
                            f"Zweryfikować i zapisać "
                            f"{len(dirty)} stref?"
                        ),
                        key_reader=self._get_key,
                    ):
                        continue
                    result = multi.save_all()
                    for saved in result.validated:
                        if not saved.ok:
                            self._transaction_result_view(
                                win,
                                saved.transaction,
                            )
                    for saved in result.committed:
                        self._transaction_result_view(
                            win,
                            saved.transaction,
                        )
                    if result.failed is not None:
                        self._transaction_result_view(
                            win,
                            result.failed.transaction,
                        )
                    else:
                        self._message_view(
                            win,
                            title="Sesja wielu stref",
                            lines=[
                                "Wszystkie zmienione strefy zapisano.",
                                f"Transakcje: {len(result.committed)}",
                            ],
                        )
                        self._start_refresh(force=True)
                    continue
                if key in (ord("q"), ord("Q"), 27, curses.KEY_F10):
                    if dirty and not CursesDialogs.confirm(
                        win,
                        (
                            f"Porzucić zmiany w "
                            f"{len(dirty)} strefach?"
                        ),
                        key_reader=self._get_key,
                    ):
                        continue
                    multi.close(discard=True)
                    return
        except MultiZoneSessionError as exc:
            self._message_view(
                win,
                title="Błąd sesji wielu stref",
                lines=[str(exc)],
                error=True,
            )
        finally:
            try:
                multi.close(discard=True)
            except Exception:
                pass

    def _collect_dnssec_status(self, zone: Zone) -> DnssecStatusView:
        toolkit = self.config.toolkit if self.config is not None else {}
        local_server = toolkit.get("local_server", "127.0.0.1")
        timeout = int(toolkit.get("dig_timeout", "3"))
        resolvers = tuple(
            item.strip()
            for item in toolkit.get(
                "dnssec_resolvers",
                "1.1.1.1,8.8.8.8,9.9.9.9",
            ).split(",")
            if item.strip()
        )
        key_directory = zone.key_directory
        if key_directory is None:
            configured = toolkit.get(
                "dnssec_key_directory",
                "/var/lib/bind/keys",
            ).strip()
            key_directory = Path(configured) if configured else None

        report = DnssecReporter(
            local_server=local_server,
            resolver=resolvers[0],
            timeout=timeout,
        ).collect(zone, key_directory)
        delegation = DnssecDsChecker(
            local_server=local_server,
            timeout=timeout,
        ).collect(zone.name, resolvers)
        return DnssecStatusView.build(report, delegation)

    @staticmethod
    def _ensure_dnssec_tui_allowed(zone: Zone) -> None:
        if zone.health_profile.casefold() == "rpz":
            raise RuntimeError(
                f"Operacje DNSSEC w TUI są zablokowane dla RPZ: {zone.name}"
            )

    def _dnssec_disable_plan(self, zone: Zone):
        self._ensure_dnssec_tui_allowed(zone)
        if self.config is None:
            raise RuntimeError("Brak konfiguracji ZoneCTL")
        discovered = self.config.discovered_zone(zone.name)
        if discovered is None:
            raise RuntimeError(
                "Autodetekcja nie znalazła deklaracji BIND dla strefy"
            )
        return DnssecDisablePlanner().plan(discovered)

    def _dnssec_enable_plan(self, zone: Zone):
        self._ensure_dnssec_tui_allowed(zone)
        if self.config is None:
            raise RuntimeError("Brak konfiguracji ZoneCTL")
        discovered = self.config.discovered_zone(zone.name)
        if discovered is None:
            raise RuntimeError(
                "Autodetekcja nie znalazła deklaracji BIND dla strefy"
            )
        return DnssecEnablePlanner().plan(discovered)

    def _dnssec_enable_dry_run(self, zone: Zone):
        plan = self._dnssec_enable_plan(zone)
        return DnssecEnableTransaction(
            Path("/var/backups/zonectl-dnssec-enable/backups"),
            Path("/var/backups/zonectl-dnssec-enable/manifests"),
        ).apply(plan)

    def _dnssec_enable_commit(self, zone: Zone):
        plan = self._dnssec_enable_plan(zone)
        return DnssecEnableTransaction(
            Path("/var/backups/zonectl-dnssec-enable/backups"),
            Path("/var/backups/zonectl-dnssec-enable/manifests"),
        ).apply(plan, commit=True, activate=True)

    def _dnssec_confirm_ds(self, zone: Zone, *, commit: bool = False):
        self._ensure_dnssec_tui_allowed(zone)
        toolkit = self.config.toolkit if self.config is not None else {}
        local_server = toolkit.get("local_server", "127.0.0.1")
        timeout = int(toolkit.get("dig_timeout", "3"))
        resolvers = tuple(
            item.strip()
            for item in toolkit.get(
                "dnssec_resolvers",
                "1.1.1.1,8.8.8.8,9.9.9.9",
            ).split(",")
            if item.strip()
        )
        checker = DnssecDsChecker(local_server=local_server, timeout=timeout)
        return DnssecConfirmDsTransaction(
            Path("/var/backups/zonectl-dnssec-confirm-ds/manifests"),
            checker=checker.collect,
        ).apply(
            zone.name,
            resolvers,
            commit=commit,
            acknowledge_published=commit,
        )

    def _dnssec_finalize_dry_run(self, zone: Zone):
        plan = self._dnssec_disable_plan(zone)
        return DnssecDisableTransaction(
            Path("/var/backups/zonectl-dnssec-disable/backups"),
            Path("/var/backups/zonectl-dnssec-disable/manifests"),
        ).apply(plan, stage="finalize")

    def _dnssec_finalize_commit(self, zone: Zone):
        plan = self._dnssec_disable_plan(zone)
        return DnssecDisableTransaction(
            Path("/var/backups/zonectl-dnssec-disable/backups"),
            Path("/var/backups/zonectl-dnssec-disable/manifests"),
        ).apply(plan, stage="finalize", commit=True, activate=True)

    def _dnssec_withdrawal_backup(self, zone: Zone, *, commit: bool = False):
        plan = self._dnssec_disable_plan(zone)
        toolkit = self.config.toolkit if self.config is not None else {}
        local_server = toolkit.get("local_server", "127.0.0.1")
        timeout = int(toolkit.get("dig_timeout", "3"))
        resolvers = tuple(
            item.strip()
            for item in toolkit.get(
                "dnssec_resolvers",
                "1.1.1.1,8.8.8.8,9.9.9.9",
            ).split(",")
            if item.strip()
        )
        report = DnssecReporter(
            local_server=local_server,
            resolver=resolvers[0],
            timeout=timeout,
        ).collect(zone, plan.key_directory)
        delegation = DnssecDsChecker(
            local_server=local_server,
            timeout=timeout,
        ).collect(plan.zone, resolvers)
        return DnssecWithdrawalBackup(
            Path("/var/backups/zonectl-dnssec-withdrawal")
        ).create(
            plan,
            commit=commit,
            dnssec_report=report.to_dict(),
            ds_check=delegation.to_dict(),
        )

    @staticmethod
    def _dnssec_backup_result_lines(result) -> list[str]:
        lines = [
            f"Status: {result.status}",
            f"Commit: {'TAK' if result.committed else 'NIE'}",
        ]
        if result.package:
            lines.append(f"Pakiet: {result.package}")
        if result.manifest:
            lines.append(f"Manifest: {result.manifest}")
        lines.extend(
            f"[{'OK' if step.ok else 'BŁĄD'}] {step.name}: {step.message}"
            for step in result.steps
        )
        return lines

    @staticmethod
    def _dnssec_enable_result_lines(result) -> list[str]:
        lines = [
            f"Status: {result.status}",
            f"Commit: {'TAK' if result.committed else 'NIE'}",
            f"Rollback: {'TAK' if result.rolled_back else 'NIE'}",
        ]
        lines.extend(
            f"[{'OK' if step.ok else 'BŁĄD'}] {step.name}: {step.message}"
            for step in result.steps
        )
        return lines

    @staticmethod
    def _dnssec_confirm_result_lines(result) -> list[str]:
        lines = [
            f"Status: {result.status}",
            f"Commit: {'TAK' if result.committed else 'NIE'}",
        ]
        if result.manifest:
            lines.append(f"Manifest: {result.manifest}")
        lines.extend(
            f"[{'OK' if step.ok else 'BŁĄD'}] {step.name}: {step.message}"
            for step in result.steps
        )
        return lines

    @staticmethod
    def _dnssec_disable_result_lines(result) -> list[str]:
        lines = [
            f"Etap: {result.stage}",
            f"Status: {result.status}",
            f"Commit: {'TAK' if result.committed else 'NIE'}",
        ]
        if result.kasp_states:
            lines.append("Stany KASP: " + ", ".join(result.kasp_states))
        lines.extend(
            f"[{'OK' if step.ok else 'BŁĄD'}] {step.name}: {step.message}"
            for step in result.steps
        )
        return lines

    def _dnssec_status_view(self, win: curses.window, zone: Zone) -> None:
        """Read-only DNSSEC workflow status with explicit operator guidance."""
        offset = 0
        view: DnssecStatusView | None = None
        error: str | None = None
        refresh = True

        try:
            win.timeout(-1)
            while True:
                if refresh:
                    win.erase()
                    height, width = win.getmaxyx()
                    win.addnstr(
                        0,
                        0,
                        f" DNSSEC: {zone.name} ".ljust(width),
                        max(0, width - 1),
                        curses.A_REVERSE | curses.A_BOLD,
                    )
                    win.addnstr(
                        2,
                        2,
                        "Pobieranie stanu KASP, DS i serwerów autorytatywnych...",
                        max(0, width - 4),
                        curses.A_BOLD,
                    )
                    win.refresh()
                    try:
                        view = self._collect_dnssec_status(zone)
                        error = None
                    except Exception as exc:
                        view = None
                        error = str(exc)
                    offset = 0
                    refresh = False

                win.erase()
                height, width = win.getmaxyx()
                title = f" DNSSEC: {zone.name} "
                win.addnstr(
                    0,
                    0,
                    title.ljust(width),
                    max(0, width - 1),
                    curses.A_REVERSE | curses.A_BOLD,
                )

                if error is not None:
                    lines = ("BŁĄD ODCZYTU", error)
                    stage = "ERROR"
                elif view is not None:
                    lines = view.lines
                    stage = view.stage
                    stage_attr = (
                        self._color(Health.PASS)
                        if stage in {"READY_FOR_DS", "ACTIVE"}
                        else self._color(Health.FAIL)
                        if stage == "ERROR"
                        else self._color(Health.WARN)
                    ) | curses.A_BOLD
                    win.addnstr(
                        1,
                        2,
                        f"Etap: {stage} — {view.title}",
                        max(0, width - 4),
                        stage_attr,
                    )
                else:
                    lines = ("Brak danych.",)
                    stage = "ERROR"

                visible = max(1, height - 5)
                offset = min(offset, max(0, len(lines) - visible))
                for row, line in enumerate(lines[offset : offset + visible], start=3):
                    attr = curses.A_NORMAL
                    if "JESZCZE ZABLOKOWANA" in line or line.startswith("BŁĄD"):
                        attr = self._color(Health.FAIL) | curses.A_BOLD
                    elif "DOZWOLONA" in line or "[MATCH]" in line:
                        attr = self._color(Health.PASS)
                    win.addnstr(row, 2, line, max(0, width - 4), attr)

                footer = (
                    " ↑/↓ przewiń  PgUp/PgDn strona  F3 plan  "
                    f"F4 {view.operation_label if view else 'wskazówki'}  "
                    "r odśwież  q/Esc powrót "
                )
                win.addnstr(
                    height - 1,
                    0,
                    footer.ljust(width),
                    max(0, width - 1),
                    curses.A_REVERSE,
                )
                win.refresh()
                key = self._get_key(win)
                if key in (ord("q"), ord("Q"), 27, curses.KEY_BACKSPACE, 127, 8):
                    return
                if key in (ord("r"), ord("R")):
                    refresh = True
                elif key == curses.KEY_F3:
                    try:
                        if view is not None and view.operation == "CONFIRM_DS":
                            checked = self._collect_dnssec_status(zone)
                            self._message_view(
                                win,
                                title=f"Kontrola DS przed potwierdzeniem: {zone.name}",
                                lines=checked.lines,
                                error=checked.operation != "CONFIRM_DS",
                            )
                        elif view is not None and view.operation == "ENABLE":
                            plan = self._dnssec_enable_plan(zone)
                            self._message_view(
                                win,
                                title=f"Plan włączenia DNSSEC: {zone.name}",
                                lines=(
                                    [
                                        f"Plik źródłowy: {plan.source_zone_file}",
                                        f"Plik docelowy: {plan.target_zone_file}",
                                        "Migracja pliku: "
                                        + ("TAK" if plan.migration_required else "NIE"),
                                        f"Polityka: {plan.policy}",
                                        "",
                                        "Planowany diff:",
                                    ]
                                    + (plan.unified_diff.splitlines() or ["Brak zmian"])
                                    + ["", "Planowane etapy:"]
                                    + [f"- {action}" for action in plan.actions]
                                ),
                            )
                        else:
                            plan = self._dnssec_disable_plan(zone)
                            self._message_view(
                                win,
                                title=f"Plan wycofania DNSSEC: {zone.name}",
                                lines=(
                                    ["Etap insecure:"]
                                    + (
                                        plan.insecure_diff.splitlines()
                                        or ["Brak zmian"]
                                    )
                                    + ["", "Etap finalize:"]
                                    + (
                                        plan.unified_diff.splitlines()
                                        or ["Brak zmian"]
                                    )
                                ),
                            )
                    except Exception as exc:
                        self._message_view(
                            win,
                            title="Błąd planu DNSSEC",
                            lines=[str(exc)],
                            error=True,
                        )
                    refresh = True
                elif key == curses.KEY_F4:
                    if view is None:
                        refresh = True
                        continue
                    if view.operation == "WITHDRAWAL":
                        try:
                            result = self._dnssec_withdrawal_backup(zone)
                            self._message_view(
                                win,
                                title=f"Dry-run backupu DNSSEC: {zone.name}",
                                lines=self._dnssec_backup_result_lines(result),
                                error=result.status != "DRY-RUN",
                            )
                            if result.status == "DRY-RUN":
                                if self.config is not None and self.config.read_only:
                                    self._read_only_message(win, zone)
                                else:
                                    confirmation = CursesDialogs.text_input(
                                        win,
                                        " Wpisz pełną nazwę strefy, aby utworzyć backup: ",
                                    )
                                    expected = zone.name.rstrip(".").casefold()
                                    supplied = (confirmation or "").rstrip(".").casefold()
                                    if supplied != expected:
                                        self._message_view(
                                            win,
                                            title="Backup anulowany",
                                            lines=[
                                                "Nie utworzono pakietu i nie zmieniono BIND."
                                            ],
                                        )
                                    elif CursesDialogs.confirm(
                                        win,
                                        f"Utworzyć backup wycofania DNSSEC dla {zone.name}?",
                                        key_reader=self._get_key,
                                    ):
                                        committed = self._dnssec_withdrawal_backup(
                                            zone, commit=True
                                        )
                                        self._message_view(
                                            win,
                                            title=f"Backup wycofania DNSSEC: {zone.name}",
                                            lines=self._dnssec_backup_result_lines(
                                                committed
                                            ),
                                            error=committed.status != "BACKUP-CREATED",
                                        )
                        except Exception as exc:
                            self._message_view(
                                win,
                                title="Błąd backupu DNSSEC",
                                lines=[str(exc)],
                                error=True,
                            )
                        refresh = True
                        continue
                    if view.operation == "CONFIRM_DS":
                        try:
                            result = self._dnssec_confirm_ds(zone)
                            self._message_view(
                                win,
                                title=f"Dry-run potwierdzenia DS: {zone.name}",
                                lines=self._dnssec_confirm_result_lines(result),
                                error=result.status != "DRY-RUN",
                            )
                            if result.status == "DRY-RUN":
                                if self.config is not None and self.config.read_only:
                                    self._read_only_message(win, zone)
                                else:
                                    confirmation = CursesDialogs.text_input(
                                        win,
                                        " Wpisz pełną nazwę strefy, aby potwierdzić DS: ",
                                    )
                                    expected = zone.name.rstrip(".").casefold()
                                    supplied = (confirmation or "").rstrip(".").casefold()
                                    if supplied != expected:
                                        self._message_view(
                                            win,
                                            title="Potwierdzenie DS anulowane",
                                            lines=["Nie zmieniono stanu KASP."],
                                        )
                                    elif CursesDialogs.confirm(
                                        win,
                                        f"Potwierdzić opublikowany DS dla {zone.name}?",
                                        key_reader=self._get_key,
                                    ):
                                        committed = self._dnssec_confirm_ds(
                                            zone, commit=True
                                        )
                                        self._message_view(
                                            win,
                                            title=f"Wynik potwierdzenia DS: {zone.name}",
                                            lines=self._dnssec_confirm_result_lines(
                                                committed
                                            ),
                                            error=committed.status != "CONFIRMED",
                                        )
                        except Exception as exc:
                            self._message_view(
                                win,
                                title="Błąd potwierdzenia DS",
                                lines=[str(exc)],
                                error=True,
                            )
                        refresh = True
                        continue
                    if view.operation != "FINALIZE":
                        if view.operation == "ENABLE":
                            try:
                                result = self._dnssec_enable_dry_run(zone)
                                self._message_view(
                                    win,
                                    title=f"Dry-run włączenia DNSSEC: {zone.name}",
                                    lines=self._dnssec_enable_result_lines(result),
                                    error=result.status != "DRY-RUN",
                                )
                                if result.status == "DRY-RUN":
                                    if self.config is not None and self.config.read_only:
                                        self._read_only_message(win, zone)
                                    else:
                                        confirmation = CursesDialogs.text_input(
                                            win,
                                            " Wpisz pełną nazwę strefy, aby włączyć DNSSEC: ",
                                        )
                                        expected = zone.name.rstrip(".").casefold()
                                        supplied = (
                                            (confirmation or "")
                                            .rstrip(".")
                                            .casefold()
                                        )
                                        if supplied != expected:
                                            self._message_view(
                                                win,
                                                title="Włączenie DNSSEC anulowane",
                                                lines=["Nie zmieniono BIND."],
                                            )
                                        elif CursesDialogs.confirm(
                                            win,
                                            f"Włączyć i aktywować DNSSEC dla {zone.name}?",
                                            key_reader=self._get_key,
                                        ):
                                            committed = self._dnssec_enable_commit(zone)
                                            self._message_view(
                                                win,
                                                title=(
                                                    "Wynik włączenia DNSSEC: "
                                                    f"{zone.name}"
                                                ),
                                                lines=self._dnssec_enable_result_lines(
                                                    committed
                                                ),
                                                error=not committed.ok,
                                            )
                            except Exception as exc:
                                self._message_view(
                                    win,
                                    title="Błąd dry-runu DNSSEC",
                                    lines=[str(exc)],
                                    error=True,
                                )
                            refresh = True
                            continue
                        else:
                            action_lines = [
                                "Na tym etapie nie ma bezpiecznej operacji zapisu.",
                                "Odśwież status po terminie wskazanym na ekranie.",
                            ]
                        self._message_view(
                            win,
                            title=f"Następna operacja DNSSEC: {zone.name}",
                            lines=action_lines,
                        )
                        refresh = True
                        continue
                    try:
                        result = self._dnssec_finalize_dry_run(zone)
                        self._message_view(
                            win,
                            title=f"Dry-run finalizacji: {zone.name}",
                            lines=self._dnssec_disable_result_lines(result),
                            error=result.status not in {"DRY-RUN"},
                        )
                        if (
                            result.status == "DRY-RUN"
                            and view is not None
                            and view.stage == "READY_TO_FINALIZE"
                        ):
                            if self.config is not None and self.config.read_only:
                                self._read_only_message(win, zone)
                            else:
                                confirmation = CursesDialogs.text_input(
                                    win,
                                    " Wpisz pełną nazwę strefy, aby finalizować: ",
                                )
                                expected = zone.name.rstrip(".").casefold()
                                supplied = (confirmation or "").rstrip(".").casefold()
                                if supplied != expected:
                                    self._message_view(
                                        win,
                                        title="Finalizacja anulowana",
                                        lines=[
                                            "Nie podano dokładnej nazwy strefy. "
                                            "Nie zmieniono BIND."
                                        ],
                                    )
                                elif not CursesDialogs.confirm(
                                    win,
                                    f"Finalizować DNSSEC dla {zone.name}?",
                                    key_reader=self._get_key,
                                ):
                                    self._message_view(
                                        win,
                                        title="Finalizacja anulowana",
                                        lines=["Nie zmieniono BIND."],
                                    )
                                else:
                                    committed = self._dnssec_finalize_commit(zone)
                                    self._message_view(
                                        win,
                                        title=(
                                            "Wynik finalizacji DNSSEC: "
                                            f"{zone.name}"
                                        ),
                                        lines=self._dnssec_disable_result_lines(
                                            committed
                                        ),
                                        error=not committed.ok,
                                    )
                    except Exception as exc:
                        self._message_view(
                            win,
                            title="Błąd dry-runu DNSSEC",
                            lines=[str(exc)],
                            error=True,
                        )
                    refresh = True
                elif key in (curses.KEY_DOWN, ord("j")):
                    offset = min(offset + 1, max(0, len(lines) - visible))
                elif key in (curses.KEY_UP, ord("k")):
                    offset = max(0, offset - 1)
                elif key == curses.KEY_NPAGE:
                    offset = min(offset + visible, max(0, len(lines) - visible))
                elif key == curses.KEY_PPAGE:
                    offset = max(0, offset - visible)
        finally:
            try:
                win.timeout(150)
            except curses.error:
                pass

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

                key = self._get_key(win)
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
                " F3 rekordy"
                "   F6 migracja"
                "   d DNSSEC"
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
            key = self._get_key(win)

            if key in (
                ord("q"),
                27,
                curses.KEY_BACKSPACE,
                127,
                8,
            ):
                return

            if key == curses.KEY_F3:
                self._records_view(win, zone)
                continue

            if key == curses.KEY_F6:
                self._zone_migration_view(win, zone)
                continue

            if key in (ord("d"), ord("D")):
                self._dnssec_status_view(win, zone)
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
    def _bind_root_config(self) -> Path:
        toolkit = self.config.toolkit if self.config is not None else {}
        return Path(toolkit.get("bind_root_config", "/etc/bind/named.conf"))

    def _bind_access_view(self, win: curses.window) -> None:
        """F9 browser for named ACLs and secondary groups."""
        selected = 0
        while True:
            try:
                inventory = BindAccessInventoryReader(
                    self._bind_root_config()
                ).collect()
                report = BindSecondaryReporter().build(inventory)
            except (BindAccessInventoryError, OSError) as exc:
                self._message_view(
                    win, title="ACL i secondary", lines=[str(exc)], error=True
                )
                return
            secondary_names = {item.name.casefold() for item in report.groups}
            items = [
                ("secondary" if item.name.casefold() in secondary_names else "acl", item)
                for item in inventory.definitions
            ]
            if not items:
                self._message_view(
                    win, title="ACL i secondary", lines=["Brak definicji."]
                )
                return
            selected = min(selected, len(items) - 1)
            height, width = win.getmaxyx()
            visible = max(1, height - 5)
            offset = max(0, min(selected, len(items) - visible))
            win.erase()
            win.addnstr(
                0, 0, " ACL i grupy secondary ".ljust(width), max(0, width - 1),
                curses.A_REVERSE | curses.A_BOLD,
            )
            win.addnstr(2, 1, "Typ        Nazwa                    Adresy", max(0, width - 2), curses.A_BOLD)
            for row, (kind, item) in enumerate(items[offset:offset + visible], 3):
                index = offset + row - 3
                line = f"{kind:<10} {item.name:<24} {', '.join(item.entries)}"
                attr = curses.A_REVERSE if index == selected else curses.A_NORMAL
                win.addnstr(row, 1, line, max(0, width - 2), attr)
            footer = " F3 podgląd   F4 edycja secondary   q/Esc/F10 powrót "
            win.addnstr(height - 1, 0, footer.ljust(width), max(0, width - 1), curses.A_REVERSE)
            win.refresh()
            key = self._get_key(win)
            if key in (ord("q"), ord("Q"), 27, curses.KEY_F10):
                return
            if key in (curses.KEY_DOWN, ord("j")):
                selected = min(selected + 1, len(items) - 1)
            elif key in (curses.KEY_UP, ord("k")):
                selected = max(0, selected - 1)
            elif key == curses.KEY_F3:
                self._show_bind_access_item(win, items[selected], report)
            elif key == curses.KEY_F4:
                kind, item = items[selected]
                if kind != "secondary":
                    self._message_view(
                        win,
                        title=f"ACL: {item.name}",
                        lines=[
                            "Pełna edycja ACL będzie dodana w następnym etapie.",
                            "Obecnie dostępne są raport, acl-plan i acl-apply.",
                        ],
                    )
                elif self.read_only:
                    self._message_view(
                        win, title="Tryb tylko do odczytu",
                        lines=["Zmiana grupy secondary jest zablokowana."], error=True,
                    )
                else:
                    self._edit_secondary_group(win, item.name, item.entries)

    def _show_bind_access_item(self, win, selected_item, report) -> None:
        kind, item = selected_item
        lines = [
            f"Typ: {kind}", f"Nazwa: {item.name}",
            f"Źródło: {item.source}:{item.line}", "", "Adresy:",
        ] + [f"  {value}" for value in item.entries]
        group = next(
            (entry for entry in report.groups if entry.name.casefold() == item.name.casefold()),
            None,
        )
        if group is not None:
            lines += ["", f"Role: {', '.join(group.roles)}", f"Użycia: {group.usage_count}", "Strefy:"]
            lines += [f"  {zone}" for zone in group.zones]
        self._message_view(win, title=f"{kind}: {item.name}", lines=lines)

    @staticmethod
    def _secondary_result_lines(result) -> list[str]:
        lines = [
            f"Transakcja: {result.transaction_id}", f"Status: {result.status}",
            f"Commit: {'TAK' if result.committed else 'NIE'}",
            f"Rollback: {'TAK' if result.rolled_back else 'NIE'}", "",
        ]
        lines.extend(
            f"[{'OK' if step.ok else 'BŁĄD'}] {step.name}: {step.message}"
            for step in result.steps
        )
        return lines

    def _edit_secondary_group(self, win, name: str, current: tuple[str, ...]) -> None:
        addresses = self._secondary_address_editor(win, name, current)
        if addresses is None:
            return
        try:
            planner = BindSecondaryPlanner(self._bind_root_config())
            plan = planner.plan(name, addresses)
        except (BindSecondaryPlanError, OSError) as exc:
            self._message_view(win, title="Zmiana zablokowana", lines=[str(exc)], error=True)
            return
        self._message_view(
            win, title=f"Plan secondary: {name}",
            lines=(plan.diff or "Brak zmian.").splitlines()
            + ["", f"Dotknięte strefy: {len(plan.zones)}"],
        )
        transaction = BindSecondaryTransaction(
            Path("/var/backups/zonectl-bind-secondary/backups"),
            Path("/var/backups/zonectl-bind-secondary/manifests"),
            root_config=self._bind_root_config(),
        )
        dry_run = transaction.apply(plan)
        self._message_view(
            win, title=f"Dry-run secondary: {name}",
            lines=self._secondary_result_lines(dry_run),
            error=dry_run.status != "DRY-RUN",
        )
        if dry_run.status != "DRY-RUN" or not plan.diff:
            return
        confirmation = CursesDialogs.text_input(
            win, " Wpisz pełną nazwę grupy: "
        )
        if (confirmation or "").casefold() != name.casefold():
            self._message_view(
                win, title="Anulowano", lines=["Nazwa grupy nie jest zgodna."]
            )
            return
        if not CursesDialogs.confirm(win, f"Zastosować zmianę grupy {name}"):
            return
        result = transaction.apply(plan, commit=True, activate=True)
        self._message_view(
            win, title=f"Transakcja secondary: {name}",
            lines=self._secondary_result_lines(result),
            error=result.status != "COMMIT",
        )

    def _secondary_address_editor(
        self, win: curses.window, name: str, current: tuple[str, ...]
    ) -> list[str] | None:
        """Full-screen MC-style editor for a secondary address list."""
        addresses = list(current)
        selected = 0
        while True:
            height, width = win.getmaxyx()
            visible = max(1, height - 7)
            if addresses:
                selected = min(selected, len(addresses) - 1)
            else:
                selected = 0
            offset = max(0, min(selected, len(addresses) - visible))
            win.erase()
            win.addnstr(
                0, 0, f" Edycja secondary: {name} ".ljust(width),
                max(0, width - 1), curses.A_REVERSE | curses.A_BOLD,
            )
            win.addnstr(2, 2, "Adres IP serwera", max(0, width - 4), curses.A_BOLD)
            for row, address in enumerate(addresses[offset:offset + visible], 4):
                index = offset + row - 4
                attr = curses.A_REVERSE if index == selected else curses.A_NORMAL
                win.addnstr(row, 2, f"{index + 1:>3}. {address}", max(0, width - 4), attr)
            if not addresses:
                win.addnstr(4, 2, "(lista pusta — Insert dodaje adres)", max(0, width - 4), curses.A_DIM)
            footer = " Ins dodaj   F4 edytuj   F8/Del usuń   F2 plan/dry-run   Esc/F10 anuluj "
            win.addnstr(height - 1, 0, footer.ljust(width), max(0, width - 1), curses.A_REVERSE)
            win.refresh()
            key = self._get_key(win)
            if key in (27, curses.KEY_F10, ord("q"), ord("Q")):
                if addresses != list(current) and not CursesDialogs.confirm(
                    win, "Porzucić zmiany listy secondary"
                ):
                    continue
                return None
            if key in (curses.KEY_DOWN, ord("j")) and addresses:
                selected = min(selected + 1, len(addresses) - 1)
            elif key in (curses.KEY_UP, ord("k")) and addresses:
                selected = max(0, selected - 1)
            elif key == curses.KEY_IC:
                value = CursesDialogs.text_input(
                    win, " Nowy adres: ", row=2
                )
                if value is not None and value.strip():
                    addresses.append(value.strip())
                    selected = len(addresses) - 1
            elif key == curses.KEY_F4 and addresses:
                value = CursesDialogs.text_input(
                    win, " Edytuj adres: ", initial=addresses[selected], row=2
                )
                if value is not None and value.strip():
                    addresses[selected] = value.strip()
            elif key in (curses.KEY_F8, curses.KEY_DC) and addresses:
                if CursesDialogs.confirm(win, f"Usunąć {addresses[selected]}"):
                    addresses.pop(selected)
                    selected = min(selected, max(0, len(addresses) - 1))
            elif key in (curses.KEY_F2, 19):
                if addresses == list(current):
                    self._message_view(
                        win, title=f"Secondary: {name}",
                        lines=["Brak zmian do zaplanowania."],
                    )
                    continue
                return addresses

    def _zone_migration_planner(self) -> ManagedZoneMigrationPlanner:
        toolkit = self.config.toolkit if self.config is not None else {}
        return ManagedZoneMigrationPlanner(
            root_config=Path(
                toolkit.get("bind_root_config", "/etc/bind/named.conf")
            ),
            local_config=Path(
                toolkit.get("bind_local_config", "/etc/bind/named.conf.local")
            ),
            managed_config=Path(
                toolkit.get("managed_config", "/etc/bind/zonectl-zones.conf")
            ),
            managed_zone_directory=Path(
                toolkit.get("managed_zone_dir", "/etc/bind/zonectl-zones.d")
            ),
        )

    @staticmethod
    def _migration_result_lines(result) -> list[str]:
        lines = [
            f"Transakcja: {result.transaction_id}",
            f"Status: {result.status}",
            f"Commit: {'TAK' if result.committed else 'NIE'}",
            f"Rollback: {'TAK' if result.rolled_back else 'NIE'}",
        ]
        if result.backup_directory:
            lines.append(f"Backup: {result.backup_directory}")
        if result.manifest:
            lines.append(f"Manifest: {result.manifest}")
        lines.append("")
        lines.extend(
            f"[{'OK' if step.ok else 'BŁĄD'}] {step.name}: {step.message}"
            for step in result.steps
        )
        return lines

    def _zone_migration_view(self, win: curses.window, zone: Zone) -> None:
        """F3 shows a plan; F4 runs dry-run and guarded migration."""
        planner = self._zone_migration_planner()
        try:
            item = next(
                entry
                for entry in planner.inventory()
                if entry.name.rstrip(".").casefold()
                == zone.name.rstrip(".").casefold()
            )
        except (ManagedZoneMigrationError, OSError, StopIteration) as exc:
            self._message_view(
                win,
                title=f"Migracja strefy: {zone.name}",
                lines=[f"Nie można odczytać stanu migracji: {exc}"],
                error=True,
            )
            return

        while True:
            height, width = win.getmaxyx()
            win.erase()
            win.addnstr(
                0,
                0,
                f" Migracja strefy: {zone.name} ".ljust(width),
                max(0, width - 1),
                curses.A_REVERSE | curses.A_BOLD,
            )
            lines = [
                f"Stan:       {item.state}",
                f"Typ:        {item.zone_type}",
                f"Deklaracja: {item.config_file}",
                f"Powód:      {item.reason}",
                "",
                "Migracja obejmuje wyłącznie deklarację BIND.",
                "Plik strefy i serial SOA nie zostaną zmienione.",
            ]
            for row, line in enumerate(lines, start=2):
                if row < height - 2:
                    win.addnstr(row, 2, line, max(0, width - 4))
            footer = " F3 plan   F4 dry-run/migracja   q/Esc powrót "
            win.addnstr(
                height - 1,
                0,
                footer.ljust(width),
                max(0, width - 1),
                curses.A_REVERSE,
            )
            win.refresh()
            key = self._get_key(win)
            if key in (ord("q"), ord("Q"), 27, curses.KEY_BACKSPACE, 127, 8):
                return
            if key == curses.KEY_F3:
                self._show_zone_migration_plan(win, zone, planner)
                continue
            if key == curses.KEY_F4:
                if self.read_only:
                    self._message_view(
                        win,
                        title="Tryb tylko do odczytu",
                        lines=["Migracja strefy jest zablokowana."],
                        error=True,
                    )
                    continue
                if self._apply_zone_migration(win, zone, planner):
                    return

    def _show_zone_migration_plan(self, win, zone, planner) -> None:
        try:
            plan = planner.plan(zone.name)
            lines = [
                f"Źródło: {plan.source_config}",
                f"Deklaracja: {plan.declaration_file}",
                f"Indeks: {plan.managed_config}",
                "",
            ]
            lines += (
                plan.source_diff + plan.declaration_diff + plan.managed_diff
            ).splitlines()
            lines += ["", "Planowane etapy:"]
            lines += [f"- {action}" for action in plan.actions]
            self._message_view(
                win, title=f"Plan migracji: {zone.name}", lines=lines
            )
        except (ManagedZoneMigrationError, OSError) as exc:
            self._message_view(
                win,
                title="Migracja zablokowana",
                lines=[str(exc)],
                error=True,
            )

    def _apply_zone_migration(self, win, zone, planner) -> bool:
        try:
            plan = planner.plan(zone.name)
            toolkit = self.config.toolkit if self.config is not None else {}
            transaction = ManagedZoneMigrationTransaction(
                Path(
                    toolkit.get(
                        "zone_migration_backup_root",
                        "/var/backups/zonectl-zone-migration/backups",
                    )
                ),
                Path(
                    toolkit.get(
                        "zone_migration_manifest_dir",
                        "/var/backups/zonectl-zone-migration/manifests",
                    )
                ),
                root_config=planner.root_config,
            )
            dry_run = transaction.apply(plan)
            self._message_view(
                win,
                title=f"Dry-run migracji: {zone.name}",
                lines=self._migration_result_lines(dry_run),
            )
            confirmation = CursesDialogs.text_input(
                win,
                " Wpisz pełną nazwę strefy, aby migrować: ",
                initial="",
            )
            expected = zone.name.rstrip(".").casefold()
            received = (confirmation or "").strip().rstrip(".").casefold()
            if received != expected:
                self._message_view(
                    win,
                    title="Migracja anulowana",
                    lines=["Potwierdzenie nie odpowiada nazwie strefy."],
                )
                return False
            if not CursesDialogs.confirm(
                win, f"Migrować i przeładować BIND dla {zone.name}?"
            ):
                return False
            result = transaction.apply(plan, commit=True, activate=True)
            self._message_view(
                win,
                title=f"Wynik migracji: {zone.name}",
                lines=self._migration_result_lines(result),
                error=result.status != "COMMIT",
            )
            return result.status == "COMMIT"
        except (ManagedZoneMigrationError, OSError) as exc:
            self._message_view(
                win, title="Błąd migracji", lines=[str(exc)], error=True
            )
            return False

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
