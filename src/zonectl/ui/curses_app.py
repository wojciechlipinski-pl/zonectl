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
from zonectl.ui.rpz_status_view import RpzStatusView
from zonectl.ui.bind_onboarding_view import BindOnboardingView
from zonectl.ui.about_view import AboutView
from zonectl.ui.zone_details_view import ZoneDetailsView

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
from ..core.bind_acl_plan import BindAclPlanError, BindAclPlanner
from ..core.bind_acl_transaction import BindAclTransaction
from ..core.bind_environment_report import BindEnvironmentReporter
from ..core.bind_onboarding_report import BindOnboardingReporter
from ..core.bind_secondary_plan import BindSecondaryPlanError, BindSecondaryPlanner
from ..core.bind_secondary_report import BindSecondaryReporter
from ..core.bind_secondary_transaction import BindSecondaryTransaction
from ..core.bind_zone_secondary import BindZoneSecondaryError, BindZoneSecondaryPlanner
from ..core.bulk_operations import BulkOperation, BulkOperationError
from ..core.config import ToolkitConfig
from ..core.dnssec_ds_check import DnssecDsChecker
from ..core.dnssec_confirm_ds import DnssecConfirmDsTransaction
from ..core.dnssec_disable_plan import DnssecDisablePlanner
from ..core.dnssec_disable_transaction import DnssecDisableTransaction
from ..core.dnssec_enable_plan import DnssecEnablePlanner
from ..core.dnssec_enable_transaction import DnssecEnableTransaction
from ..core.dnssec_report import DnssecReporter
from ..core.dnssec_onboarding_audit import DnssecOnboardingAuditor
from ..core.dnssec_withdrawal_backup import DnssecWithdrawalBackup
from ..core.managed_zone_migration import (
    ManagedZoneMigrationError,
    ManagedZoneMigrationPlanner,
)
from ..core.managed_zone_migration_transaction import (
    ManagedZoneMigrationStep,
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
            if key == curses.KEY_F1:
                self._about_view(stdscr)
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
            elif key == curses.KEY_F2:
                self._bind_onboarding_view(stdscr)
            elif key == curses.KEY_F9:
                self._bind_access_view(stdscr)
            elif key == curses.KEY_F3:
                self._selected_zone_preview(stdscr)
            elif key == curses.KEY_F4:
                self._selected_zone_edit(stdscr)
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
        # Ciemny turkus z opublikowanej koncepcji 4.8. W palecie xterm-256
        # indeks 30 odpowiada #008787. Przy ograniczonej palecie używamy
        # podstawowego cyan i przyciemniamy go atrybutem A_DIM w rendererze.
        footer_key_color = curses.COLOR_CYAN
        if curses.COLORS >= 256:
            footer_key_color = 30
        elif curses.COLORS >= 16 and curses.can_change_color():
            footer_key_color = 8
            curses.init_color(footer_key_color, 0, 430, 470)
        curses.init_pair(6, footer_key_color, curses.COLOR_WHITE)

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
        heading = "Zarządzanie strefami DNS"
        title_line = title + heading.center(max(0, width - len(title)))
        win.addnstr(0, 0, title_line.ljust(width), width, curses.A_REVERSE | curses.A_BOLD)
        checked = len(self.statuses)
        subtitle = (
            f" Domeny: {len(self.all_zones)}  Sprawdzone: {checked}/{len(self.all_zones)}  "
            f"Zaznaczone: {len(self.multi_selected)}  "
            f"Widok: {'grupy' if self.grouped else 'lista'}  Sort: {self.SORTS[self.sort_index]}  "
            f"Szukaj: {self.query or '-'}"
        )
        win.addnstr(2, 0, subtitle, max(0, width - 1), curses.A_BOLD)
        list_header = 4
        list_top = 6
        panel_enabled = width >= 118 and height >= 28
        list_width = width
        footer_lines = 3
        content_height = max(1, height - list_top - footer_lines)
        details_height = max(10, content_height // 3) if panel_enabled else 0
        visible = content_height - details_height - 1 if panel_enabled else content_height
        if panel_enabled:
            header_attr = curses.A_BOLD | (
                curses.color_pair(4) if curses.has_colors() else curses.A_NORMAL
            )
            columns = (
                f" {'Strefa':<45} {'Status':<7} "
                f"{'Profil':<10} {'SOA / wiek'}"
            )
            win.addnstr(list_header, 0, columns, max(0, width - 1), header_attr)
            try:
                for column in range(0, width - 1):
                    win.addch(list_header + 1, column, curses.ACS_HLINE, curses.A_DIM)
            except curses.error:
                pass
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
                attr = (
                    curses.color_pair(5) | curses.A_BOLD
                    if curses.has_colors()
                    else attr | curses.A_REVERSE
                )
            win.addnstr(
                screen_row,
                0,
                line.ljust(list_width),
                max(0, list_width - 1),
                attr,
            )

        if panel_enabled:
            self._draw_zone_details_panel(
                win,
                top=list_top + visible + 1,
                left=0,
                height=details_height,
                width=width,
            )

        self._draw_main_footer(win, height - 2, width)
        if not panel_enabled:
            draw_project_credits(win)
        win.refresh()

    def _draw_main_footer(self, win: curses.window, row: int, width: int) -> None:
        """Rysuje pasek MC, wyróżniając klawisze zgodnie z koncepcją 4.8."""
        actions = (
            ("F1", "O programie"),
            ("Enter", "Otwórz"),
            ("F2", "Środowisko"),
            ("F3", "Podgląd"),
            ("F4", "Edycja"),
            ("Insert", "Dodaj"),
            ("F9", "ACL/secondary"),
            ("F10", "Wyjście"),
        )
        try:
            win.addnstr(row, 0, " " * width, max(0, width - 1), curses.A_REVERSE)
            column = 1
            key_attr = (
                curses.color_pair(6) | curses.A_DIM
                if curses.has_colors()
                else curses.A_REVERSE | curses.A_BOLD
            )
            for key, label in actions:
                segment = f"{key} {label}  "
                if column + len(segment) >= width:
                    break
                win.addnstr(row, column, key, len(key), key_attr)
                column += len(key)
                text = f" {label}  "
                win.addnstr(row, column, text, len(text), curses.A_REVERSE)
                column += len(text)
        except curses.error:
            return

    def _draw_zone_details_panel(
        self,
        win: curses.window,
        *,
        top: int,
        left: int,
        height: int,
        width: int,
    ) -> None:
        """Rysuje dolny panel zgodny z opublikowaną koncepcją TUI 4.8."""
        if width < 20 or height < 4:
            return
        try:
            for column in range(left, left + width - 1):
                win.addch(top - 1, column, curses.ACS_HLINE, curses.A_DIM)
        except (curses.error, AttributeError):
            pass
        zone = (
            self.rows[self.selected].zone
            if self.rows and 0 <= self.selected < len(self.rows)
            else None
        )
        if zone is None:
            title = " Szczegóły strefy "
            lines = ("Wybierz strefę z listy.",)
            summary_title = " Stan operacyjny "
            summary_lines = ("-",)
        else:
            status = self.statuses.get(zone.name, ZoneStatus(zone=zone))
            details = ZoneDetailsView.build(zone, status)
            title = f" Szczegóły strefy: {details.title} "
            lines = details.lines
            summary_title = f" {details.summary_title} "
            summary_lines = details.summary_lines
        try:
            divider = left + max(42, width * 2 // 3)
            divider = min(divider, left + width - 25)
            heading_attr = curses.A_BOLD | (
                curses.color_pair(4) if curses.has_colors() else curses.A_NORMAL
            )
            win.addnstr(top, left + 2, title, divider - left - 3, heading_attr)
            win.addnstr(
                top,
                divider + 2,
                summary_title,
                left + width - divider - 4,
                heading_attr,
            )
            for row_index in range(top + 1, top + height):
                win.addch(row_index, divider, curses.ACS_VLINE, curses.A_DIM)
            available = max(0, height - 2)
            row = top + 2
            for line in lines:
                wrapped = self._wrap_message_lines(
                    [line], max(1, divider - left - 4)
                )
                for part in wrapped:
                    if row >= top + 2 + available:
                        break
                    win.addnstr(row, left + 2, part, divider - left - 4)
                    row += 1
            row = top + 2
            for line in summary_lines:
                wrapped = self._wrap_message_lines(
                    [line], max(1, left + width - divider - 4)
                )
                for part in wrapped:
                    if row >= top + 2 + available:
                        break
                    attributes = curses.A_NORMAL
                    if line.startswith("Status") and zone is not None:
                        attributes = self._color(status.health) | curses.A_BOLD
                    win.addnstr(
                        row,
                        divider + 2,
                        part,
                        left + width - divider - 4,
                        attributes,
                    )
                    row += 1
        except curses.error:
            return

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

    def _selected_zone_preview(self, win: curses.window) -> None:
        """Otwiera kontekstowy podgląd F3; dla RPZ pokazuje stan integracji."""
        if not self.rows:
            return
        zone = self.rows[self.selected].zone
        if zone is None:
            return
        if zone.health_profile.casefold() != "rpz":
            self._domain_view(win, zone)
            return
        self._rpz_status_view(win, zone)

    def _selected_zone_edit(self, win: curses.window) -> None:
        """Otwiera ekran strefy, zachowując RPZ jako zasób tylko do odczytu."""
        if not self.rows:
            return
        zone = self.rows[self.selected].zone
        if zone is None:
            return
        if zone.health_profile.casefold() == "rpz":
            self._message_view(
                win,
                title="Strefa RPZ — tylko odczyt",
                lines=[
                    "Automatycznie aktualizowana strefa RPZ nie może być edytowana",
                    "jak zwykła strefa autorytatywna.",
                    "Użyj F3, aby sprawdzić stan integracji.",
                ],
                error=True,
            )
            return
        self._domain_view(win, zone)

    def _rpz_status_view(self, win: curses.window, zone: Zone) -> None:
        """Pokazuje odczytowy panel RPZ, łącząc wiek pliku z systemd i BIND."""
        root_config = (
            self.config.bind_config_path
            if self.config is not None
            else Path("/etc/bind/named.conf")
        )
        try:
            report = BindEnvironmentReporter(
                root_config,
                rpz_max_age=zone.rpz_max_age,
            ).collect()
            environment = next(
                item
                for item in report.rpz
                if item.zone.rstrip(".").casefold()
                == zone.name.rstrip(".").casefold()
            )
            view = RpzStatusView.build(environment)
        except (OSError, RuntimeError, StopIteration) as exc:
            self._message_view(
                win,
                title=f"RPZ: {zone.name} — błąd raportu",
                lines=[str(exc)],
                error=True,
            )
            return
        self._message_view(
            win,
            title=view.title,
            lines=list(view.lines),
            error=view.health in {"FAILED", "STALE"},
        )

    def _bind_onboarding_view(self, win: curses.window) -> None:
        """Pokazuje gotowość istniejącego BIND bez wykonywania importu."""
        root_config = (
            self.config.bind_config_path
            if self.config is not None
            else Path("/etc/bind/named.conf")
        )
        try:
            report = BindOnboardingReporter(root_config).collect()
            view = BindOnboardingView.build(report)
        except (OSError, RuntimeError) as exc:
            self._message_view(
                win,
                title="Pierwsze uruchomienie — błąd rozpoznania BIND",
                lines=[str(exc)],
                error=True,
            )
            return
        self._onboarding_summary_view(win, view, report)

    def _about_view(self, win: curses.window) -> None:
        """Pokazuje koncepcyjny ekran autorstwa zgodny wizualnie z TUI 4.8."""
        view = AboutView.build(__version__)
        heading_attr = curses.A_BOLD | (
            curses.color_pair(4) if curses.has_colors() else curses.A_NORMAL
        )
        try:
            win.timeout(-1)
            while True:
                win.erase()
                height, width = win.getmaxyx()
                win.addnstr(
                    0, 0, f" {view.title} ".ljust(width),
                    max(0, width - 1), curses.A_REVERSE | curses.A_BOLD,
                )
                subtitle = " Autorstwo • historia • informacje o projekcie "
                win.addnstr(2, 2, subtitle, max(0, width - 4), heading_attr)
                try:
                    for column in range(2, max(2, width - 2)):
                        win.addch(3, column, curses.ACS_HLINE, curses.A_DIM)
                except curses.error:
                    pass

                split = max(48, width // 2)
                split = min(split, max(48, width - 42))
                if width >= 100:
                    for row in range(5, max(5, height - 3)):
                        win.addch(row, split, curses.ACS_VLINE, curses.A_DIM)
                    self._draw_about_identity(win, 5, 4, split - 7, heading_attr)
                    self._draw_about_history(
                        win, 5, split + 3, width - split - 6, heading_attr
                    )
                else:
                    self._draw_about_compact(
                        win, 5, 3, max(1, width - 6), heading_attr
                    )
                footer = " F1 O programie   q/Esc/F10 Powrót "
                win.addnstr(
                    height - 1, 0, footer.ljust(width),
                    max(0, width - 1), curses.A_REVERSE,
                )
                win.refresh()
                key = self._get_key(win)
                if key in (
                    curses.KEY_F1, curses.KEY_F10, ord("q"), ord("Q"), 27,
                    curses.KEY_BACKSPACE, 127, 8,
                ):
                    return
        except curses.error:
            return
        finally:
            win.timeout(150)

    def _draw_about_identity(self, win, top, left, width, heading_attr) -> None:
        """Lewa kolumna ekranu F1: człowiek, AI i charakter projektu."""
        sections = (
            ("AUTOR I WŁAŚCICIEL PROJEKTU", ("Wojciech Lipiński", "Domain Expert • QA • Product Design")),
            ("ROZWÓJ WSPOMAGANY PRZEZ AI", ("OpenAI ChatGPT", "Architecture • Development • Documentation")),
            ("PROJEKT", ("ZoneCTL", "Transactional DNS Management Toolkit", "for BIND 9")),
        )
        row = top
        for title, lines in sections:
            win.addnstr(row, left, title, width, heading_attr)
            row += 2
            for line in lines:
                win.addnstr(row, left, line, width)
                row += 1
            row += 2

    def _draw_about_history(self, win, top, left, width, heading_attr) -> None:
        """Prawa kolumna ekranu F1: historia i repozytorium."""
        win.addnstr(top, left, "HISTORIA PROJEKTU", width, heading_attr)
        history = (
            "ZoneCTL rozpoczął się od prostego skryptu Python, który miał uporządkować pliki konfiguracyjne domen.",
            "Z czasem rozwinął się w transakcyjne narzędzie CLI i TUI do zarządzania BIND, DNSSEC, ACL, secondary i RPZ.",
            "Projekt łączy wieloletnie doświadczenie infrastrukturalne autora z architekturą i rozwojem wspomaganym przez AI.",
        )
        row = top + 2
        for paragraph in history:
            for line in self._wrap_message_lines([paragraph], width):
                win.addnstr(row, left, line, width)
                row += 1
            row += 1
        row += 1
        win.addnstr(row, left, "REPOZYTORIUM", width, heading_attr)
        row += 2
        win.addnstr(
            row, left, "github.com/wojciechlipinski-pl/zonectl", width
        )

    def _draw_about_compact(self, win, top, left, width, heading_attr) -> None:
        """Jednokolumnowy wariant F1 dla węższych terminali."""
        lines = (
            ("AUTOR", heading_attr),
            ("Wojciech Lipiński — Domain Expert • QA • Product Design", 0),
            ("", 0),
            ("ROZWÓJ WSPOMAGANY PRZEZ AI", heading_attr),
            ("OpenAI ChatGPT — Architecture • Development • Documentation", 0),
            ("", 0),
            ("HISTORIA", heading_attr),
            ("Od skryptu Python porządkującego konfigurację domen do transakcyjnego CLI i TUI dla BIND 9.", 0),
            ("", 0),
            ("REPOZYTORIUM", heading_attr),
            ("github.com/wojciechlipinski-pl/zonectl", 0),
        )
        row = top
        for text, attr in lines:
            for line in self._wrap_message_lines([text], width):
                win.addnstr(row, left, line, width, attr)
                row += 1

    def _onboarding_summary_view(self, win, view, report) -> None:
        """Raport F2 z przejściem do listy kandydatów klawiszem Enter."""
        offset = 0
        try:
            win.timeout(-1)
            while True:
                win.erase()
                height, width = win.getmaxyx()
                wrapped = self._wrap_message_lines(
                    list(view.lines), max(1, width - 4)
                )
                visible = max(1, height - 4)
                maximum = max(0, len(wrapped) - visible)
                offset = min(offset, maximum)
                win.addnstr(
                    0, 0, f" {view.title} ".ljust(width),
                    max(0, width - 1), curses.A_REVERSE | curses.A_BOLD,
                )
                for row, line in enumerate(
                    wrapped[offset : offset + visible], start=2
                ):
                    win.addnstr(row, 2, line, max(0, width - 4))
                if width >= 100 and height >= 24:
                    self._draw_onboarding_summary_48(win, report)
                footer = self._onboarding_footer(report)
                win.addnstr(
                    height - 1, 0, footer.ljust(width),
                    max(0, width - 1), curses.A_REVERSE,
                )
                win.refresh()
                key = self._get_key(win)
                if key in (10, 13, curses.KEY_ENTER) and report.candidates:
                    self._onboarding_candidates_view(win, report.candidates)
                    report, view = self._refresh_onboarding_report(report.root_config)
                elif key == curses.KEY_F5:
                    dnssec = tuple(
                        item for item in report.blockers
                        if item.category == "DNSSEC"
                    )
                    if dnssec:
                        self._onboarding_dnssec_view(win, dnssec)
                        report, view = self._refresh_onboarding_report(
                            report.root_config
                        )
                elif key in (curses.KEY_DOWN, ord("j")):
                    offset = min(offset + 1, maximum)
                elif key in (curses.KEY_UP, ord("k")):
                    offset = max(0, offset - 1)
                elif key == curses.KEY_NPAGE:
                    offset = min(offset + visible, maximum)
                elif key == curses.KEY_PPAGE:
                    offset = max(0, offset - visible)
                elif key in (ord("q"), ord("Q"), 27, curses.KEY_F10):
                    return
        finally:
            win.timeout(150)

    @staticmethod
    def _onboarding_footer(report) -> str:
        """Pokazuje wyłącznie akcje mające dostępne elementy docelowe."""
        actions: list[str] = []
        if report.candidates:
            actions.append("Enter LEGACY")
        if any(item.category == "DNSSEC" for item in report.blockers):
            actions.append("F5 DNSSEC")
        actions.extend(("↑/↓ PgUp/PgDn", "F10 Powrót"))
        return " " + "   ".join(actions) + " "

    def _draw_onboarding_summary_48(self, win, report) -> None:
        """Rysuje raport środowiska w dwukolumnowym układzie ZoneCTL 4.8."""
        height, width = win.getmaxyx()
        heading_attr = curses.A_BOLD | (
            curses.color_pair(4) if curses.has_colors() else curses.A_NORMAL
        )
        win.erase()
        win.addnstr(
            0, 0, " Środowisko BIND ".ljust(width), max(0, width - 1),
            curses.A_REVERSE | curses.A_BOLD,
        )
        win.addnstr(
            2, 2, "Odkrywanie konfiguracji • gotowość importu • tylko odczyt",
            max(0, width - 4), heading_attr,
        )
        try:
            for column in range(2, width - 2):
                win.addch(3, column, curses.ACS_HLINE, curses.A_DIM)
        except (curses.error, AttributeError):
            pass

        split = max(62, min(width - 42, int(width * 0.67)))
        try:
            for row in range(5, height - 2):
                win.addch(row, split, curses.ACS_VLINE, curses.A_DIM)
        except curses.error:
            pass

        left = 4
        value = 25
        left_width = max(1, split - left - 2)
        win.addnstr(5, left, "WYKRYTE ŚRODOWISKO", left_width, heading_attr)
        environment_rows = (
            ("Konfiguracja", report.root_config),
            ("Pliki konfiguracji", str(report.config_files)),
            ("Strefy", str(report.zones)),
            ("Strefy DNSSEC", str(report.dnssec_zones)),
        )
        row = 7
        for label, content in environment_rows:
            win.addnstr(row, left, label, value - left - 1)
            win.addnstr(row, value, content, max(1, split - value - 2))
            row += 1

        row += 1
        win.addnstr(row, left, "KLASYFIKACJA", left_width, heading_attr)
        row += 2
        for item in report.classes:
            if row >= height - 3:
                break
            state_attr = heading_attr if item.count else curses.A_DIM
            win.addnstr(row, left, f"{item.state:<10}", 10, state_attr)
            win.addnstr(row, left + 12, f"{item.count:>3}", 3)
            win.addnstr(
                row, left + 18, item.description,
                max(1, split - left - 20), curses.A_DIM,
            )
            row += 1

        right = split + 3
        right_width = max(1, width - right - 3)
        win.addnstr(5, right, "STAN OPERACYJNY", right_width, heading_attr)
        managed = next(
            (item.count for item in report.classes if item.state == "MANAGED"), 0
        )
        state_rows = (
            ("Status", "GOTOWY" if not report.blocked else "UWAGA"),
            ("Managed", str(managed)),
            ("Kandydaci", str(report.import_candidates)),
            ("Zablokowane", str(report.blocked)),
        )
        row = 7
        for label, content in state_rows:
            win.addnstr(row, right, label, 14)
            attr = heading_attr if label == "Status" else curses.A_NORMAL
            win.addnstr(row, right + 15, content, max(1, right_width - 15), attr)
            row += 1

        row += 1
        win.addnstr(
            row, right, "KONFIGURACJA WSPÓŁDZIELONA", right_width, heading_attr
        )
        row += 2
        shared_rows = (
            ("ACL", str(report.acl_definitions)),
            ("Secondary", str(report.secondary_groups)),
            ("Integracje RPZ", str(report.rpz_integrations)),
            ("Tryb RPZ", ", ".join(report.rpz_modes) or "-"),
        )
        for label, content in shared_rows:
            win.addnstr(row, right, label, 14)
            win.addnstr(row, right + 15, content, max(1, right_width - 15))
            row += 1

        row += 1
        if row < height - 4:
            win.addnstr(row, right, "NASTĘPNY KROK", right_width, heading_attr)
            row += 2
            for line in self._wrap_message_lines([report.next_action], right_width):
                if row >= height - 2:
                    break
                win.addnstr(row, right, line, right_width)
                row += 1

    @staticmethod
    def _refresh_onboarding_report(root_config):
        """Ponownie odkrywa BIND po wyjściu z listy importu."""
        report = BindOnboardingReporter(Path(root_config)).collect()
        return report, BindOnboardingView.build(report)

    def _onboarding_candidates_view(self, win, candidates) -> None:
        """Lista legacy: plan, dry-run i jawnie potwierdzony import."""
        selected = 0
        planner = self._zone_migration_planner()
        while True:
            win.erase()
            height, width = win.getmaxyx()
            win.addnstr(
                0, 0, " Kandydaci do importu ZoneCTL ".ljust(width),
                max(0, width - 1), curses.A_REVERSE | curses.A_BOLD,
            )
            win.addnstr(
                2, 2, f"{'Strefa':<38} {'Typ':<10} Deklaracja",
                max(0, width - 4), curses.A_BOLD,
            )
            visible = max(1, height - 7)
            offset = max(0, min(selected, len(candidates) - visible))
            for screen_row, item in enumerate(
                candidates[offset : offset + visible], start=4
            ):
                index = offset + screen_row - 4
                line = f"{item.name:<38} {item.zone_type:<10} {item.declaration}"
                attr = curses.A_REVERSE if index == selected else curses.A_NORMAL
                win.addnstr(screen_row, 2, line, max(0, width - 4), attr)
            current = candidates[selected]
            self._draw_context_panel_48(
                win, "SZCZEGÓŁY KANDYDATA",
                (
                    ("Strefa", current.name),
                    ("Typ", current.zone_type),
                    ("Deklaracja", current.declaration),
                    ("Plik strefy", current.zone_file or "-"),
                    ("Tryb", "PLANOWANY IMPORT"),
                ),
            )
            footer = (
                " F3 plan   F4 dry-run   F6 importuj   "
                "↑/↓ wybór   q/Esc powrót "
            )
            win.addnstr(
                height - 1, 0, footer.ljust(width),
                max(0, width - 1), curses.A_REVERSE,
            )
            win.refresh()
            key = self._get_key(win)
            if key in (ord("q"), ord("Q"), 27, curses.KEY_F10):
                return
            if key in (curses.KEY_DOWN, ord("j")):
                selected = min(selected + 1, len(candidates) - 1)
            elif key in (curses.KEY_UP, ord("k")):
                selected = max(0, selected - 1)
            elif key in (curses.KEY_F3, 10, 13, curses.KEY_ENTER):
                self._show_bind_onboarding_plan(
                    win, candidates[selected].name, planner
                )
            elif key == curses.KEY_F4:
                self._dry_run_bind_onboarding_import(
                    win, candidates[selected].name, planner
                )
            elif key == curses.KEY_F6:
                if self._commit_bind_onboarding_import(
                    win, candidates[selected].name, planner
                ):
                    return

    def _show_bind_onboarding_plan(self, win, zone_name, planner) -> None:
        """Wyświetla diff kandydata; ten przepływ nie ma ścieżki zapisu."""
        try:
            plan = planner.plan(zone_name)
            lines = [
                f"Źródło:     {plan.source_config}",
                f"Deklaracja: {plan.declaration_file}",
                f"Indeks:     {plan.managed_config}",
                "",
                "PLANOWANE DIFFY",
                *(plan.source_diff + plan.declaration_diff + plan.managed_diff).splitlines(),
                "",
                "Plan tylko do odczytu — nie zmieniono konfiguracji BIND.",
            ]
            self._message_view(
                win, title=f"Plan importu: {zone_name}", lines=lines
            )
        except (ManagedZoneMigrationError, OSError) as exc:
            self._message_view(
                win, title="Plan importu zablokowany", lines=[str(exc)], error=True
            )

    def _onboarding_dnssec_view(self, win, blockers) -> None:
        """Koncepcyjny ekran stref DNSSEC: wyłącznie plan i dry-run."""
        selected = 0
        planner = self._zone_migration_planner()
        while True:
            win.erase()
            height, width = win.getmaxyx()
            win.addnstr(
                0, 0, " Import deklaracji DNSSEC — tryb ostrożny ".ljust(width),
                max(0, width - 1), curses.A_REVERSE | curses.A_BOLD,
            )
            heading_attr = curses.A_BOLD | (
                curses.color_pair(4) if curses.has_colors() else curses.A_NORMAL
            )
            win.addnstr(2, 2, "STREFY DNSSEC", max(0, width - 4), heading_attr)
            win.addnstr(
                3, 2,
                "Przenoszona jest tylko deklaracja BIND; klucze, KASP i DS pozostają bez zmian.",
                max(0, width - 4),
            )
            try:
                for column in range(2, max(2, width - 2)):
                    win.addch(4, column, curses.ACS_HLINE, curses.A_DIM)
            except curses.error:
                pass
            visible = max(1, height - 10)
            offset = max(0, min(selected, len(blockers) - visible))
            for screen_row, item in enumerate(
                blockers[offset : offset + visible], start=6
            ):
                index = offset + screen_row - 6
                line = f"{item.name:<38} {item.reason}"
                attr = curses.A_REVERSE if index == selected else curses.A_NORMAL
                win.addnstr(screen_row, 2, line, max(0, width - 4), attr)
            if width >= 100 and height >= 24:
                self._draw_dnssec_onboarding_48(
                    win, blockers, selected, offset, visible
                )
            footer = " F3 plan   F4 dry-run   F6 importuj   F7 audyt   ↑/↓ wybór   q/Esc/F10 powrót "
            win.addnstr(
                height - 1, 0, footer.ljust(width),
                max(0, width - 1), curses.A_REVERSE,
            )
            win.refresh()
            key = self._get_key(win)
            if key in (ord("q"), ord("Q"), 27, curses.KEY_F10):
                return
            if key in (curses.KEY_DOWN, ord("j")):
                selected = min(selected + 1, len(blockers) - 1)
            elif key in (curses.KEY_UP, ord("k")):
                selected = max(0, selected - 1)
            elif key in (curses.KEY_F3, 10, 13, curses.KEY_ENTER):
                self._show_dnssec_onboarding_plan(
                    win, blockers[selected].name, planner
                )
            elif key == curses.KEY_F4:
                self._dry_run_dnssec_onboarding_import(
                    win, blockers[selected].name, planner
                )
            elif key == curses.KEY_F6:
                if self._commit_dnssec_onboarding_import(
                    win, blockers[selected].name, planner
                ):
                    return
            elif key == curses.KEY_F7:
                self._dnssec_onboarding_audit_view(win, blockers)

    def _draw_dnssec_onboarding_48(
        self, win, blockers, selected, offset, visible
    ) -> None:
        """Rysuje listę importu DNSSEC zgodnie z wizualnym kontraktem 4.8."""
        height, width = win.getmaxyx()
        heading_attr = curses.A_BOLD | (
            curses.color_pair(4) if curses.has_colors() else curses.A_NORMAL
        )
        win.erase()
        win.addnstr(
            0, 0, " Import deklaracji DNSSEC ".ljust(width),
            max(0, width - 1), curses.A_REVERSE | curses.A_BOLD,
        )
        win.addnstr(
            2, 2, "Bezpieczny onboarding • deklaracja BIND • KASP i DS bez zmian",
            max(0, width - 4), heading_attr,
        )
        try:
            for column in range(2, width - 2):
                win.addch(3, column, curses.ACS_HLINE, curses.A_DIM)
        except curses.error:
            pass
        split = max(64, min(width - 40, int(width * 0.68)))
        try:
            for row in range(5, height - 2):
                win.addch(row, split, curses.ACS_VLINE, curses.A_DIM)
        except curses.error:
            pass

        win.addnstr(5, 3, "STREFA", 38, heading_attr)
        win.addnstr(5, 43, "PROFIL", 10, heading_attr)
        win.addnstr(5, 55, "STAN", max(1, split - 57), heading_attr)
        list_visible = max(1, min(visible, height - 9))
        for screen_row, item in enumerate(
            blockers[offset : offset + list_visible], start=7
        ):
            index = offset + screen_row - 7
            attr = curses.A_REVERSE if index == selected else curses.A_NORMAL
            line = f"{item.name:<38} {'DNSSEC':<10} {'DO AUDYTU':<12}"
            win.addnstr(screen_row, 3, line, max(1, split - 5), attr)

        current = blockers[selected]
        right = split + 3
        right_width = max(1, width - right - 3)
        win.addnstr(5, right, "STAN OPERACYJNY", right_width, heading_attr)
        details = (
            ("Strefa", current.name),
            ("Profil", "DNSSEC"),
            ("Operacja", "IMPORT DEKLARACJI"),
            ("Klucze", "BEZ ZMIAN"),
            ("KASP", "BEZ ZMIAN"),
            ("DS", "BEZ ZMIAN"),
        )
        row = 7
        for label, content in details:
            win.addnstr(row, right, label, 12)
            win.addnstr(row, right + 13, content, max(1, right_width - 13))
            row += 1
        row += 1
        win.addnstr(row, right, "POWÓD KLASYFIKACJI", right_width, heading_attr)
        row += 2
        for line in self._wrap_message_lines([current.reason], right_width):
            if row >= height - 3:
                break
            win.addnstr(row, right, line, right_width)
            row += 1

    def _show_dnssec_onboarding_plan(self, win, zone_name, planner) -> None:
        """Pokazuje deklaracyjny plan DNSSEC bez operacji na kluczach."""
        try:
            plan = planner.plan(zone_name, allow_dnssec=True)
            lines = [
                "PROFIL DNSSEC — TYLKO DEKLARACJA",
                f"Źródło:     {plan.source_config}",
                f"Deklaracja: {plan.declaration_file}",
                f"Indeks:     {plan.managed_config}",
                "",
                *(plan.source_diff + plan.declaration_diff + plan.managed_diff).splitlines(),
                "",
                "Klucze, dnssec-policy, KASP i DS nie zostaną zmienione.",
            ]
            self._message_view(
                win, title=f"Plan importu DNSSEC: {zone_name}", lines=lines
            )
        except (ManagedZoneMigrationError, OSError) as exc:
            self._message_view(
                win, title="Plan DNSSEC zablokowany", lines=[str(exc)], error=True
            )

    def _dnssec_onboarding_audit_view(self, win, blockers) -> None:
        """Pokazuje zbiorczą gotowość DNSSEC w koncepcyjnym układzie 4.8."""
        toolkit = self.config.toolkit if self.config is not None else {}
        wanted = {item.name.rstrip(".").casefold() for item in blockers}
        zones = tuple(
            zone for zone in self.all_zones
            if zone.name.rstrip(".").casefold() in wanted
        )
        resolvers = tuple(
            item.strip() for item in toolkit.get(
                "dnssec_resolvers", "1.1.1.1,8.8.8.8,9.9.9.9"
            ).split(",") if item.strip()
        )
        try:
            results = DnssecOnboardingAuditor(
                local_server=toolkit.get("dnssec_local_server", "127.0.0.1"),
                resolvers=resolvers,
                timeout=int(toolkit.get("dnssec_timeout", "3")),
            ).audit(
                zones,
                Path(toolkit.get("dnssec_key_directory", "/var/lib/bind/keys")),
            )
        except (OSError, RuntimeError, ValueError) as exc:
            self._message_view(
                win, title="Audyt DNSSEC — błąd", lines=[str(exc)], error=True
            )
            return
        ready = sum(item.status == "READY" for item in results)
        lines = [
            "ZBIORCZY AUDYT GOTOWOŚCI DNSSEC — TYLKO ODCZYT",
            f"Strefy: {len(results)}   Gotowe: {ready}   Zablokowane: {len(results) - ready}",
            "",
            f"{'Strefa':<36} {'Stan':<9} {'Raport':<8} Delegacja",
            "-" * 72,
        ]
        lines.extend(
            f"{item.zone:<36} {item.status:<9} {item.report_status:<8} {item.delegation_status}"
            for item in results
        )
        lines.extend(("", "Audyt nie zmienił BIND, kluczy, KASP ani DS."))
        self._dnssec_onboarding_audit_result_view(win, results, ready)

    def _dnssec_onboarding_audit_result_view(self, win, results, ready) -> None:
        """Pokazuje zbiorczy audyt DNSSEC w układzie ZoneCTL 4.8."""
        selected = 0
        try:
            win.timeout(-1)
            while True:
                win.erase()
                height, width = win.getmaxyx()
                heading_attr = curses.A_BOLD | (
                    curses.color_pair(4)
                    if curses.has_colors() else curses.A_NORMAL
                )
                win.addnstr(
                    0, 0, " Audyt gotowości importu DNSSEC ".ljust(width),
                    max(0, width - 1), curses.A_REVERSE | curses.A_BOLD,
                )
                blocked = len(results) - ready
                win.addnstr(
                    2, 2,
                    f"Strefy {len(results)}   Gotowe {ready}   Zablokowane {blocked}",
                    max(0, width - 4), heading_attr,
                )
                try:
                    for column in range(2, width - 2):
                        win.addch(3, column, curses.ACS_HLINE, curses.A_DIM)
                except curses.error:
                    pass

                wide = width >= 100 and height >= 20
                split = (
                    max(66, min(width - 38, int(width * 0.70)))
                    if wide else width
                )
                if wide:
                    try:
                        for row in range(5, height - 2):
                            win.addch(row, split, curses.ACS_VLINE, curses.A_DIM)
                    except curses.error:
                        pass
                win.addnstr(5, 3, "STREFA", 36, heading_attr)
                win.addnstr(5, 41, "STAN", 9, heading_attr)
                win.addnstr(5, 52, "RAPORT", 8, heading_attr)
                win.addnstr(5, 62, "DS", max(1, split - 64), heading_attr)
                visible = max(1, height - 9)
                offset = max(0, min(selected, len(results) - visible))
                for screen_row, item in enumerate(
                    results[offset : offset + visible], start=7
                ):
                    index = offset + screen_row - 7
                    attr = (
                        curses.A_REVERSE if index == selected
                        else curses.A_NORMAL
                    )
                    line = (
                        f"{item.zone:<36} {item.status:<9} "
                        f"{item.report_status:<8} {item.delegation_status}"
                    )
                    win.addnstr(screen_row, 3, line, max(1, split - 5), attr)

                if wide and results:
                    current = results[selected]
                    right = split + 3
                    right_width = max(1, width - right - 3)
                    win.addnstr(
                        5, right, "STAN OPERACYJNY", right_width, heading_attr
                    )
                    details = (
                        ("Strefa", current.zone),
                        ("Gotowość", current.status),
                        ("Raport", current.report_status),
                        ("Delegacja", current.delegation_status),
                    )
                    row = 7
                    for label, content in details:
                        win.addnstr(row, right, label, 12)
                        win.addnstr(
                            row, right + 13, content,
                            max(1, right_width - 13),
                        )
                        row += 1
                    row += 1
                    win.addnstr(
                        row, right, "BEZPIECZEŃSTWO", right_width, heading_attr
                    )
                    row += 2
                    for text in (
                        "BIND bez zmian", "Klucze bez zmian",
                        "KASP bez zmian", "DS bez zmian",
                    ):
                        win.addnstr(row, right, text, right_width)
                        row += 1

                footer = " ↑/↓ wybór   F10 Powrót "
                win.addnstr(
                    height - 1, 0, footer.ljust(width), max(0, width - 1),
                    curses.A_REVERSE,
                )
                win.refresh()
                key = self._get_key(win)
                if key in (ord("q"), ord("Q"), 27, curses.KEY_F10):
                    return
                if key in (curses.KEY_DOWN, ord("j")) and results:
                    selected = min(selected + 1, len(results) - 1)
                elif key in (curses.KEY_UP, ord("k")) and results:
                    selected = max(0, selected - 1)
        finally:
            win.timeout(150)

    def _dry_run_dnssec_onboarding_import(self, win, zone_name, planner) -> None:
        """Uruchamia transakcyjny dry-run profilu DNSSEC bez aktywacji."""
        try:
            plan = planner.plan(zone_name, allow_dnssec=True)
            toolkit = self.config.toolkit if self.config is not None else {}
            transaction = ManagedZoneMigrationTransaction(
                Path(toolkit.get("zone_migration_backup_root", "/var/backups/zonectl-zone-migration/backups")),
                Path(toolkit.get("zone_migration_manifest_dir", "/var/backups/zonectl-zone-migration/manifests")),
                root_config=planner.root_config,
            )
            result = transaction.apply(plan)
            lines = self._migration_result_lines(result) + [
                "", "Dry-run DNSSEC — nie zapisano konfiguracji, kluczy ani stanu KASP."
            ]
            self._onboarding_result_view(
                win, title=f"Dry-run importu DNSSEC: {zone_name}",
                result=result, profile="DNSSEC", note=lines[-1],
            )
        except (ManagedZoneMigrationError, OSError) as exc:
            self._message_view(
                win, title="Dry-run DNSSEC zablokowany", lines=[str(exc)], error=True
            )

    def _dnssec_import_gate(self, zone_name):
        """Wymaga aktywnego, w pełni zgodnego łańcucha DNSSEC."""
        zone = next(
            item for item in self.all_zones
            if item.name.rstrip(".").casefold() == zone_name.rstrip(".").casefold()
        )
        toolkit = self.config.toolkit if self.config is not None else {}
        local_server = toolkit.get("dnssec_local_server", "127.0.0.1")
        timeout = int(toolkit.get("dnssec_timeout", "3"))
        resolvers = tuple(
            item.strip()
            for item in toolkit.get(
                "dnssec_resolvers", "1.1.1.1,8.8.8.8,9.9.9.9"
            ).split(",")
            if item.strip()
        )
        key_directory = zone.key_directory or Path(
            toolkit.get("dnssec_key_directory", "/var/lib/bind/keys")
        )
        report = DnssecReporter(
            local_server=local_server,
            resolver=resolvers[0],
            timeout=timeout,
        ).collect(zone, key_directory)
        delegation = DnssecDsChecker(
            local_server=local_server, timeout=timeout
        ).collect(zone.name, resolvers)
        if report.status != "PASS" or delegation.status != "PASS":
            raise RuntimeError(
                "Bramka DNSSEC wymaga raportu PASS i delegacji PASS: "
                f"raport={report.status}, delegacja={delegation.status}"
            )
        if not report.parent_ds_matches or not delegation.kasp_ready:
            raise RuntimeError("DS lub KASP nie są gotowe do bezpiecznego importu")
        fingerprint = (
            report.dnssec_policy,
            report.inline_signing,
            report.dnskey_records,
            report.calculated_ds,
            report.parent_ds_records,
        )
        return zone, resolvers, key_directory, fingerprint

    def _commit_dnssec_onboarding_import(self, win, zone_name, planner) -> bool:
        """Importuje deklarację DNSSEC z bramką przed i po rndc reconfig."""
        if self.read_only:
            self._message_view(
                win, title="Tryb tylko do odczytu",
                lines=["Import DNSSEC jest zablokowany."], error=True,
            )
            return False
        try:
            zone, resolvers, key_directory, before = self._dnssec_import_gate(zone_name)
            plan = planner.plan(zone_name, allow_dnssec=True)
            toolkit = self.config.toolkit if self.config is not None else {}

            def verify_dnssec(_zone_name):
                report = DnssecReporter(
                    local_server=toolkit.get("dnssec_local_server", "127.0.0.1"),
                    resolver=resolvers[0],
                    timeout=int(toolkit.get("dnssec_timeout", "3")),
                ).collect(zone, key_directory)
                delegation = DnssecDsChecker(
                    local_server=toolkit.get("dnssec_local_server", "127.0.0.1"),
                    timeout=int(toolkit.get("dnssec_timeout", "3")),
                ).collect(zone.name, resolvers)
                after = (
                    report.dnssec_policy,
                    report.inline_signing,
                    report.dnskey_records,
                    report.calculated_ds,
                    report.parent_ds_records,
                )
                ok = report.status == "PASS" and delegation.status == "PASS" and after == before
                detail = (
                    "Raport PASS, delegacja PASS, DNSKEY/DS/polityka bez zmian"
                    if ok else
                    f"Niezgodność po reconfig: raport={report.status}, delegacja={delegation.status}"
                )
                return ManagedZoneMigrationStep("dnssec-post-gate", ok, detail)

            transaction = ManagedZoneMigrationTransaction(
                Path(toolkit.get("zone_migration_backup_root", "/var/backups/zonectl-zone-migration/backups")),
                Path(toolkit.get("zone_migration_manifest_dir", "/var/backups/zonectl-zone-migration/manifests")),
                root_config=planner.root_config,
                loaded_verifier=verify_dnssec,
            )
            dry_run = transaction.apply(plan)
            self._onboarding_result_view(
                win, title=f"Kontrola DNSSEC przed importem: {zone_name}",
                result=dry_run, profile="DNSSEC",
                note="Dry-run wykonany przed potwierdzeniem; BIND i KASP bez zmian.",
            )
            if dry_run.status not in {"DRY-RUN", "DRY_RUN"}:
                return False
            confirmation = CursesDialogs.text_input(
                win, " Wpisz pełną nazwę strefy DNSSEC: ", initial=""
            )
            if (confirmation or "").strip().rstrip(".").casefold() != zone_name.rstrip(".").casefold():
                self._message_view(
                    win, title="Import DNSSEC anulowany",
                    lines=["Potwierdzenie nie odpowiada nazwie strefy."],
                )
                return False
            if not CursesDialogs.confirm(
                win, f"Importować deklarację DNSSEC {zone_name} i przeładować BIND?"
            ):
                return False
            result = transaction.apply(plan, commit=True, activate=True)
            self._onboarding_result_view(
                win, title=f"Wynik importu DNSSEC: {zone_name}",
                result=result, profile="DNSSEC",
                note="Klucze, DS i stan KASP pozostały niezmienione.",
            )
            return result.status == "COMMIT"
        except (ManagedZoneMigrationError, OSError, RuntimeError, StopIteration) as exc:
            self._message_view(
                win, title="Import DNSSEC zablokowany", lines=[str(exc)], error=True
            )
            return False

    def _dry_run_bind_onboarding_import(self, win, zone_name, planner) -> None:
        """Waliduje transakcję importu bez zapisu plików i aktywacji BIND."""
        try:
            plan = planner.plan(zone_name)
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
            result = transaction.apply(plan)
            lines = self._migration_result_lines(result)
            lines.extend(
                (
                    "",
                    "Dry-run — nie zapisano konfiguracji i nie przeładowano BIND.",
                )
            )
            self._onboarding_result_view(
                win, title=f"Dry-run importu: {zone_name}",
                result=result, profile="PRIMARY", note=lines[-1],
            )
        except (ManagedZoneMigrationError, OSError) as exc:
            self._message_view(
                win,
                title="Dry-run importu zablokowany",
                lines=[str(exc)],
                error=True,
            )

    def _commit_bind_onboarding_import(self, win, zone_name, planner) -> bool:
        """Importuje jedną deklarację po dwóch niezależnych potwierdzeniach."""
        if self.read_only:
            self._message_view(
                win,
                title="Tryb tylko do odczytu",
                lines=["Import środowiska jest zablokowany."],
                error=True,
            )
            return False
        try:
            plan = planner.plan(zone_name)
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
            self._onboarding_result_view(
                win, title=f"Kontrola przed importem: {zone_name}",
                result=dry_run, profile="PRIMARY",
                note="Dry-run wykonany przed potwierdzeniem; konfiguracja bez zmian.",
            )
            if dry_run.status not in {"DRY-RUN", "DRY_RUN"}:
                return False
            confirmation = CursesDialogs.text_input(
                win,
                " Wpisz pełną nazwę strefy, aby importować: ",
                initial="",
            )
            expected = zone_name.rstrip(".").casefold()
            received = (confirmation or "").strip().rstrip(".").casefold()
            if received != expected:
                self._message_view(
                    win,
                    title="Import anulowany",
                    lines=["Potwierdzenie nie odpowiada nazwie strefy."],
                )
                return False
            if not CursesDialogs.confirm(
                win,
                f"Importować deklarację {zone_name} i przeładować BIND?",
            ):
                return False
            result = transaction.apply(plan, commit=True, activate=True)
            self._onboarding_result_view(
                win, title=f"Wynik importu: {zone_name}",
                result=result, profile="PRIMARY",
                note="Deklaracja jest teraz zarządzana przez ZoneCTL.",
            )
            return result.status == "COMMIT"
        except (ManagedZoneMigrationError, OSError) as exc:
            self._message_view(
                win,
                title="Import środowiska zablokowany",
                lines=[str(exc)],
                error=True,
            )
            return False

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
            "primary_ns": toolkit.get("default_primary_ns", "ns1.example.pl."),
            "admin": toolkit.get("default_soa_admin", "hostmaster.example.pl."),
            "nameservers": toolkit.get(
                "default_nameservers",
                "ns1.example.pl., ns2.example.pl.",
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
            visible = RecordRenderer.visible_rows(height, width)

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
                    # TransactionEngine może podmienić plik i przeładować
                    # BIND poza bieżącym modelem TUI. Zawsze czytamy ponownie
                    # aktywny plik, także po COMMIT, aby usunięte rekordy nie
                    # pozostawały w widoku do restartu aplikacji.
                    session.reload()

                    model = session.model
                    visible_records = ordered_records()
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

            if key in (curses.KEY_F8, curses.KEY_DC):
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
                wide = width >= 100 and height >= 20
                divider = max(62, min(width - 38, int(width * 0.70)))
                content_width = divider - 7 if wide else width - 4
                wrapped = self._wrap_message_lines(lines, max(1, content_width))
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
                if wide:
                    self._draw_message_view_48(
                        win, title, wrapped, offset, visible, error, divider
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

    def _draw_message_view_48(
        self, win, title, wrapped, offset, visible, error, divider
    ) -> None:
        """Wspólny renderer komunikatów, planów i wyników w układzie 4.8."""
        height, width = win.getmaxyx()
        try:
            has_colors = curses.has_colors()
        except curses.error:
            has_colors = False
        heading_attr = curses.A_BOLD | (
            curses.color_pair(4) if has_colors else curses.A_NORMAL
        )
        status_attr = (
            self._color(Health.FAIL if error else Health.PASS)
            if has_colors else curses.A_NORMAL
        ) | curses.A_BOLD
        win.erase()
        win.addnstr(
            0, 0, f" {title} ".ljust(width), max(0, width - 1),
            curses.A_REVERSE | curses.A_BOLD,
        )
        win.addnstr(2, 3, "SZCZEGÓŁY", max(1, divider - 6), heading_attr)
        try:
            for column in range(2, width - 2):
                win.addch(3, column, curses.ACS_HLINE, curses.A_DIM)
            for row in range(5, height - 2):
                win.addch(row, divider, curses.ACS_VLINE, curses.A_DIM)
        except (curses.error, AttributeError):
            pass
        for row, line in enumerate(
            wrapped[offset : offset + visible], start=5
        ):
            if row >= height - 2:
                break
            attr = curses.A_NORMAL
            stripped = line.strip()
            if stripped.isupper() and len(stripped) < 54:
                attr = heading_attr
            elif (
                stripped.startswith("[OK]") or "Status: PASS" in line
                or "Status: COMMIT" in line or "Status: DRY-RUN" in line
            ):
                attr = self._color(Health.PASS) if has_colors else curses.A_NORMAL
            elif (
                stripped.startswith("[BŁĄD]") or stripped.startswith("BŁĄD")
                or "Status: BLOCKED" in line or "Status: FAIL" in line
            ):
                attr = (
                    self._color(Health.FAIL) if has_colors else curses.A_NORMAL
                ) | curses.A_BOLD
            win.addnstr(row, 3, line, max(1, divider - 6), attr)

        right = divider + 3
        right_width = max(1, width - right - 3)
        win.addnstr(2, right, "STAN OPERACYJNY", right_width, heading_attr)
        win.addnstr(
            5, right, "BŁĄD" if error else "INFORMACJA", right_width,
            status_attr,
        )
        win.addnstr(7, right, "Tryb", 14)
        win.addnstr(7, right + 15, "TYLKO PODGLĄD", max(1, right_width - 15))
        win.addnstr(9, right, "STEROWANIE", right_width, heading_attr)
        hints = (
            "↑/↓ przewijanie", "PgUp/PgDn strona",
            "Home/End początek/koniec", "F10 powrót",
        )
        for row, text in enumerate(hints, start=11):
            win.addnstr(row, right, text, right_width)

    def _draw_context_panel_48(self, win, heading, details) -> None:
        """Dodaje panel kontekstowy 4.8 do starszych ekranów listowych."""
        height, width = win.getmaxyx()
        if width < 100 or height < 20:
            return
        split = max(62, min(width - 38, int(width * 0.68)))
        try:
            has_colors = curses.has_colors()
        except curses.error:
            has_colors = False
        heading_attr = curses.A_BOLD | (
            curses.color_pair(4) if has_colors else curses.A_NORMAL
        )
        try:
            for row in range(2, height - 2):
                win.addnstr(row, split + 1, " " * (width - split - 2), width - split - 2)
                win.addch(row, split, curses.ACS_VLINE, curses.A_DIM)
        except (curses.error, AttributeError):
            pass
        right = split + 3
        right_width = max(1, width - right - 3)
        win.addnstr(2, right, heading, right_width, heading_attr)
        row = 4
        for label, content in details:
            if row >= height - 3:
                break
            win.addnstr(row, right, str(label), 14)
            parts = self._wrap_message_lines([str(content)], max(1, right_width - 15))
            for index, part in enumerate(parts):
                if row >= height - 3:
                    break
                column = right + 15 if index == 0 else right
                limit = max(1, right_width - 15) if index == 0 else right_width
                win.addnstr(row, column, part, limit)
                row += 1
            row += 1

    def _onboarding_result_view(
        self,
        win: curses.window,
        *,
        title: str,
        result,
        profile: str,
        note: str = "",
    ) -> None:
        """Renderuje wynik importu w dwukolumnowym układzie TUI 4.8."""
        status = str(result.status).replace("_", "-")
        ok = status in {"COMMIT", "DRY-RUN"}
        status_attr = self._color(Health.PASS if ok else Health.FAIL) | curses.A_BOLD
        heading_attr = curses.A_BOLD | (
            curses.color_pair(4) if curses.has_colors() else curses.A_NORMAL
        )
        steps = tuple(getattr(result, "steps", ()))
        try:
            win.timeout(-1)
            while True:
                win.erase()
                height, width = win.getmaxyx()
                win.addnstr(
                    0, 0, f" {title} ".ljust(width), max(0, width - 1),
                    curses.A_REVERSE | curses.A_BOLD,
                )
                wide = width >= 100 and height >= 20
                divider = max(58, width * 2 // 3) if wide else width
                left_width = max(1, divider - 5)
                win.addnstr(2, 3, "TRANSAKCJA", left_width, heading_attr)
                details = (
                    f"Id             {result.transaction_id}",
                    f"Strefa         {result.zone}",
                    f"Profil         {profile}",
                    f"Commit         {'TAK' if result.committed else 'NIE'}",
                    f"Rollback       {'TAK' if result.rolled_back else 'NIE'}",
                )
                row = 4
                for line in details:
                    win.addnstr(row, 3, line, left_width)
                    row += 1
                row += 1
                win.addnstr(row, 3, "ETAPY", left_width, heading_attr)
                row += 2
                for step in steps:
                    marker = "OK" if step.ok else "BŁĄD"
                    line = f"[{marker}] {step.name}: {step.message}"
                    for part in self._wrap_message_lines([line], left_width):
                        if row >= height - 2:
                            break
                        attr = self._color(Health.PASS if step.ok else Health.FAIL)
                        win.addnstr(row, 3, part, left_width, attr)
                        row += 1
                if wide:
                    try:
                        for line_row in range(2, height - 2):
                            win.addch(line_row, divider, curses.ACS_VLINE, curses.A_DIM)
                    except curses.error:
                        pass
                    right = divider + 3
                    right_width = max(1, width - right - 2)
                    win.addnstr(2, right, "STAN OPERACYJNY", right_width, heading_attr)
                    win.addnstr(5, right, status, right_width, status_attr)
                    summary = (
                        "OPERACJA ZAKOŃCZONA" if status == "COMMIT"
                        else "KONTROLA BEZ ZMIAN" if status == "DRY-RUN"
                        else "OPERACJA ZABLOKOWANA"
                    )
                    win.addnstr(7, right, summary, right_width, status_attr)
                    if note:
                        note_row = 10
                        for part in self._wrap_message_lines([note], right_width):
                            if note_row >= height - 2:
                                break
                            win.addnstr(note_row, right, part, right_width)
                            note_row += 1
                elif note and row < height - 2:
                    row += 1
                    for part in self._wrap_message_lines([note], max(1, width - 6)):
                        if row >= height - 2:
                            break
                        win.addnstr(row, 3, part, max(1, width - 6))
                        row += 1
                footer = " q/Esc/F10 Powrót "
                win.addnstr(
                    height - 1, 0, footer.ljust(width), max(0, width - 1),
                    curses.A_REVERSE,
                )
                win.refresh()
                key = self._get_key(win)
                if key in (ord("q"), ord("Q"), 27, curses.KEY_F10, 10, 13):
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

            if changes:
                current = changes[selected]
                record = current.record
                self._draw_context_panel_48(
                    win, "SZCZEGÓŁY ZMIANY",
                    (
                        ("Operacja", labels[current.kind][1]),
                        ("Nazwa", record.relative_owner(zone.name)),
                        ("Typ", record.rtype),
                        ("TTL", record.ttl if record.ttl is not None else "-"),
                        ("Wartość", record.rdata),
                    ),
                )
            else:
                self._draw_context_panel_48(
                    win, "STAN OPERACYJNY", (("Zmiany", "BRAK"),)
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

                self._draw_context_panel_48(
                    win, "STAN OPERACYJNY",
                    (
                        ("Strefa", session.zone.name),
                        ("Tryb", "UNIFIED DIFF"),
                        ("Linie", len(lines)),
                        ("Zapis", "NIE"),
                    ),
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

            self._draw_context_panel_48(
                win, "STAN OPERACYJNY",
                (
                    ("Tryb", "PODGLĄD"),
                    ("Zapis", "NIE"),
                    ("Następny krok", "ENTER — POTWIERDZENIE"),
                    ("Anulowanie", "ESC / F10"),
                ),
            )

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
                current_zone = selected_zones[selected]
                current_session = multi.open(current_zone.name)
                self._draw_context_panel_48(
                    win, "STAN WYBRANEJ STREFY",
                    (
                        ("Strefa", current_zone.name),
                        ("Zmiany", current_session.change_count),
                        ("Stan", "ZMIENIONA" if current_session.dirty else "BEZ ZMIAN"),
                        ("Sesja", "WIELE STREF"),
                    ),
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
        # Operacje DNSSEC zmieniają deklarację BIND w czasie działania TUI.
        # Odśwież autodetekcję, aby raport nie korzystał ze starego obiektu
        # Zone i nie pokazywał UNSIGNED po poprawnym włączeniu polityki.
        if self.config is not None and hasattr(
            self.config, "_discover_bind_zones"
        ):
            self.config._discover_bind_zones()
            current = next(
                (
                    item
                    for item in self.config.zones()
                    if item.name.rstrip(".").casefold()
                    == zone.name.rstrip(".").casefold()
                ),
                None,
            )
            if current is not None:
                zone = current
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

                if width >= 100 and height >= 28:
                    self._draw_dnssec_status_48(
                        win, zone, view, error, stage
                    )
                footer = (
                    f" Enter {view.operation_label if view else 'odśwież'}  "
                    "↑/↓ przewiń  PgUp/PgDn strona  F3 plan  "
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
                if key in (10, 13, curses.KEY_ENTER) and view is not None:
                    if view.operation in {"REFRESH", "CHECK_DS", "STATUS"}:
                        refresh = True
                        continue
                    if view.operation in {"ENABLE", "CONFIRM_DS", "FINALIZE"}:
                        key = curses.KEY_F4
                    else:
                        refresh = True
                        continue
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
                    if view.operation in {"REFRESH", "CHECK_DS", "STATUS"}:
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

    def _draw_dnssec_status_48(self, win, zone, view, error, stage) -> None:
        """Rysuje status strefy DNSSEC w dwukolumnowym układzie 4.8."""
        height, width = win.getmaxyx()

        def put(row, column, text, attr=curses.A_NORMAL, limit=None):
            if 0 <= row < height and 0 <= column < width:
                try:
                    available = max(0, width - column - 1)
                    win.addnstr(
                        row, column, str(text),
                        min(available, limit) if limit is not None else available,
                        attr,
                    )
                except curses.error:
                    pass

        heading_attr = curses.A_BOLD | (
            curses.color_pair(4) if curses.has_colors() else curses.A_NORMAL
        )
        stage_attr = (
            self._color(Health.PASS)
            if stage in {"READY_FOR_DS", "ACTIVE"}
            else self._color(Health.FAIL)
            if stage == "ERROR"
            else self._color(Health.WARN)
        ) | curses.A_BOLD
        win.erase()
        put(
            0, 0, f" DNSSEC: {zone.name} ".ljust(width),
            curses.A_REVERSE | curses.A_BOLD,
        )
        subtitle = view.title if view is not None else (error or "Brak danych")
        put(2, 3, f"Etap {stage} • {subtitle}", stage_attr)
        try:
            for column in range(2, width - 2):
                win.addch(3, column, curses.ACS_HLINE, curses.A_DIM)
        except curses.error:
            pass

        split = max(68, min(width - 54, int(width * 0.60)))
        try:
            for row in range(5, height - 2):
                win.addch(row, split, curses.ACS_VLINE, curses.A_DIM)
        except curses.error:
            pass
        left = 4
        right = split + 3
        left_width = max(1, split - left - 3)
        right_width = max(1, width - right - 3)
        put(5, left, "POLITYKA, KASP I DS", heading_attr, left_width)
        put(5, right, "DELEGACJA I STAN OPERACYJNY", heading_attr, right_width)

        raw_lines = list(view.lines) if view is not None else ["BŁĄD ODCZYTU", error or "-"]
        delegation_at = next(
            (
                index for index, line in enumerate(raw_lines)
                if line.startswith("KONTROLA DELEGACJI")
            ),
            len(raw_lines),
        )
        left_lines = raw_lines[:delegation_at]
        right_lines = raw_lines[delegation_at:]

        def draw_lines(lines, top, column, column_width):
            row = top
            for text in lines:
                if row >= height - 3:
                    break
                stripped = text.strip()
                attr = curses.A_NORMAL
                if stripped in {
                    "STAN KASP", "DS OCZEKIWANY", "DS PUBLICZNY",
                    "Resolvery:", "Serwery autorytatywne:",
                } or stripped.startswith("KONTROLA DELEGACJI"):
                    attr = heading_attr
                elif "[MATCH]" in text or "DOZWOLONA" in text:
                    attr = self._color(Health.PASS)
                elif (
                    "JESZCZE ZABLOKOWANA" in text
                    or "[MISMATCH]" in text
                    or "[NOT-AUTH]" in text
                    or stripped.startswith("BŁĄD")
                ):
                    attr = self._color(Health.FAIL) | curses.A_BOLD
                wrapped = self._wrap_message_lines([text], column_width) or [""]
                for wrapped_line in wrapped:
                    if row >= height - 3:
                        break
                    put(row, column, wrapped_line, attr, column_width)
                    row += 1
            return row

        draw_lines(left_lines, 7, left, left_width)
        if right_lines:
            draw_lines(right_lines, 7, right, right_width)
        else:
            put(7, right, "Brak danych delegacji.", curses.A_DIM, right_width)

    def _draw_domain_view_48(
        self,
        win: curses.window,
        zone: Zone,
        status: ZoneStatus,
        notice: str,
    ) -> None:
        """Rysuje szczegóły strefy zgodnie z opublikowanym układem 4.8."""
        win.erase()
        height, width = win.getmaxyx()

        def put(row, column, text, attr=curses.A_NORMAL):
            if 0 <= row < height and 0 <= column < width:
                try:
                    win.addnstr(
                        row, column, str(text), max(0, width - column - 1), attr
                    )
                except curses.error:
                    pass

        put(
            0, 0, f" Strefa DNS: {zone.name} ".ljust(width),
            curses.A_REVERSE | curses.A_BOLD,
        )
        heading = curses.A_BOLD | (
            curses.color_pair(4) if curses.has_colors() else curses.A_NORMAL
        )
        health_attr = self._color(status.health) | curses.A_BOLD
        wide = width >= 100 and height >= 22
        divider = min(max(58, width * 2 // 3), width - 30) if wide else width
        left_value = 21
        if wide:
            put(2, 2, " Szczegóły strefy ", heading)
            put(2, divider + 2, " Stan operacyjny ", heading)
            try:
                for column in range(width - 1):
                    win.addch(3, column, curses.ACS_HLINE, curses.A_DIM)
                for row in range(4, height - 2):
                    win.addch(row, divider, curses.ACS_VLINE, curses.A_DIM)
            except curses.error:
                pass
        else:
            put(2, 2, "SZCZEGÓŁY STREFY", heading)

        transfers = []
        if zone.dns2:
            transfers.append("DNS2")
        if zone.he:
            transfers.append("HE")
        dnssec = (
            "WŁĄCZONY" if status.dnssec is True
            else "WYŁĄCZONY" if status.dnssec is False
            else "NIEZNANY"
        )
        details = (
            ("Grupa", zone.group),
            ("Plik strefy", str(zone.file) if zone.file else "-"),
            ("Plik istnieje", self._bool_text(status.file_exists)),
            ("Notify", self._bool_text(zone.notify)),
            ("Reload", self._bool_text(zone.reload)),
            ("Transfer", ", ".join(transfers) or "brak"),
            ("", ""),
            ("SOA primary", status.local_serial or "-"),
            ("SOA dns2", status.dns2_serial or "-" if zone.dns2 else "nieużywany"),
            ("SOA HE", status.he_serial or "-" if zone.he else "nieużywany"),
            ("DNSSEC", dnssec),
        )
        row = 5 if wide else 4
        for label, value in details:
            if not label:
                row += 1
                continue
            put(row, 2, label)
            put(row, left_value, value)
            row += 1
        if zone.file:
            try:
                put(row + 1, 2, "Rozmiar pliku")
                put(row + 1, left_value, f"{zone.file.stat().st_size} B")
            except OSError:
                pass

        status_column = divider + 2 if wide else 2
        status_row = 5 if wide else min(row + 3, height - 7)
        put(
            status_row, status_column,
            f"{self._symbol(status.health)} {status.health.value}", health_attr,
        )
        put(status_row + 2, status_column, "KOMUNIKAT", heading)
        message_width = max(1, width - status_column - 3)
        for index, line in enumerate(
            self._wrap_message_lines([status.message or "-"], message_width),
            start=status_row + 3,
        ):
            if index >= height - 3:
                break
            put(index, status_column, line)
        if notice:
            put(height - 4, status_column, notice, curses.A_BOLD)

        actions = (
            ("F3", "Rekordy"), ("F5", "Secondary"),
            ("F6", "Migracja"), ("d", "DNSSEC"),
            ("r", "Odśwież"), ("F10", "Powrót"),
        )
        put(height - 2, 0, " " * width, curses.A_REVERSE)
        column = 1
        key_attr = (
            curses.color_pair(6) | curses.A_DIM
            if curses.has_colors() else curses.A_REVERSE | curses.A_BOLD
        )
        for key, label in actions:
            if column + len(key) + len(label) + 3 >= width:
                break
            put(height - 2, column, key, key_attr)
            column += len(key)
            text = f" {label}  "
            put(height - 2, column, text, curses.A_REVERSE)
            column += len(text)

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
                "   F5 secondary"
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

            self._draw_domain_view_48(win, zone, status, notice)
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

            if key == curses.KEY_F5:
                self._zone_secondary_view(win, zone)
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
    def _zone_secondary_view(self, win: curses.window, zone: Zone) -> None:
        planner = BindZoneSecondaryPlanner(self._bind_root_config())
        try:
            pairs = planner.available_pairs()
            current = set(planner.plan(zone.name, []).old_pairs)
        except (BindZoneSecondaryError, OSError) as exc:
            self._message_view(win, title="Secondary strefy", lines=[str(exc)], error=True)
            return
        selected = 0
        chosen = set(current)
        while True:
            height, width = win.getmaxyx()
            win.erase()
            win.addnstr(0, 0, f" Secondary strefy: {zone.name} ".ljust(width), max(0, width - 1), curses.A_REVERSE | curses.A_BOLD)
            for row, pair in enumerate(pairs, 3):
                marker = "[x]" if pair.name.casefold() in chosen else "[ ]"
                line = f"{marker} {pair.name:<18} notify={','.join(pair.notify_addresses)} transfer={','.join(pair.transfer_addresses)}"
                attr = curses.A_REVERSE if row - 3 == selected else curses.A_NORMAL
                win.addnstr(row, 2, line, max(0, width - 4), attr)
            if pairs:
                current_pair = pairs[selected]
                self._draw_context_panel_48(
                    win, "SZCZEGÓŁY SECONDARY",
                    (
                        ("Strefa", zone.name),
                        ("Grupa", current_pair.name),
                        ("Wybrana", "TAK" if current_pair.name.casefold() in chosen else "NIE"),
                        ("Notify", ", ".join(current_pair.notify_addresses)),
                        ("Transfer", ", ".join(current_pair.transfer_addresses)),
                    ),
                )
            footer = " Spacja wybierz   F3 plan   F4 dry-run/zastosuj   Esc/F10 powrót "
            win.addnstr(height - 1, 0, footer.ljust(width), max(0, width - 1), curses.A_REVERSE)
            win.refresh()
            key = self._get_key(win)
            if key in (27, curses.KEY_F10, ord("q"), ord("Q")):
                return
            if key in (curses.KEY_DOWN, ord("j")):
                selected = min(selected + 1, max(0, len(pairs) - 1))
            elif key in (curses.KEY_UP, ord("k")):
                selected = max(0, selected - 1)
            elif key == ord(" ") and pairs:
                name = pairs[selected].name.casefold()
                chosen.remove(name) if name in chosen else chosen.add(name)
            elif key in (curses.KEY_F3, curses.KEY_F4):
                try:
                    plan = planner.plan(zone.name, sorted(chosen))
                except (BindZoneSecondaryError, OSError) as exc:
                    self._message_view(win, title="Plan zablokowany", lines=[str(exc)], error=True)
                    continue
                self._message_view(win, title=f"Plan secondary: {zone.name}", lines=(plan.diff or "Brak zmian.").splitlines())
                if key == curses.KEY_F3 or not plan.diff:
                    continue
                if self.read_only:
                    self._read_only_message(win, zone)
                    continue
                transaction = BindSecondaryTransaction(
                    Path("/var/backups/zonectl-bind-secondary/backups"),
                    Path("/var/backups/zonectl-bind-secondary/manifests"),
                    root_config=self._bind_root_config(),
                )
                dry_run = transaction.apply(plan.transaction_plan())
                self._message_view(win, title="Dry-run przypisania", lines=self._secondary_result_lines(dry_run))
                confirmation = CursesDialogs.text_input(win, " Wpisz pełną nazwę strefy: ")
                if (confirmation or "").rstrip(".").casefold() != zone.name.rstrip(".").casefold():
                    self._message_view(win, title="Anulowano", lines=["Nazwa strefy nie jest zgodna."])
                    continue
                if CursesDialogs.confirm(win, f"Zastosować przypisania dla {zone.name}"):
                    result = transaction.apply(plan.transaction_plan(), commit=True, activate=True)
                    self._message_view(win, title="Transakcja przypisania", lines=self._secondary_result_lines(result), error=result.status != "COMMIT")
                    if result.status == "COMMIT":
                        return

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
            current_kind, current_item = items[selected]
            self._draw_context_panel_48(
                win, "SZCZEGÓŁY DEFINICJI",
                (
                    ("Typ", current_kind.upper()),
                    ("Nazwa", current_item.name),
                    ("Elementy", len(current_item.entries)),
                    ("Źródło", f"{current_item.source}:{current_item.line}"),
                ),
            )
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
                if self.read_only:
                    self._message_view(
                        win, title="Tryb tylko do odczytu",
                        lines=["Zmiana konfiguracji BIND jest zablokowana."], error=True,
                    )
                elif kind == "acl":
                    self._edit_acl(win, item.name, item.entries)
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

    def _edit_acl(self, win, name: str, current: tuple[str, ...]) -> None:
        entries = self._acl_entry_editor(win, name, current)
        if entries is None:
            return
        try:
            plan = BindAclPlanner(self._bind_root_config()).plan(name, entries=entries)
        except (BindAclPlanError, OSError) as exc:
            self._message_view(win, title="Zmiana ACL zablokowana", lines=[str(exc)], error=True)
            return
        self._message_view(
            win, title=f"Plan ACL: {name}",
            lines=(plan.diff or "Brak zmian.").splitlines(),
        )
        transaction = BindAclTransaction(
            Path("/var/backups/zonectl-bind-acl/backups"),
            Path("/var/backups/zonectl-bind-acl/manifests"),
            root_config=self._bind_root_config(),
        )
        dry_run = transaction.apply(plan)
        self._message_view(
            win, title=f"Dry-run ACL: {name}",
            lines=self._secondary_result_lines(dry_run),
            error=dry_run.status != "DRY-RUN",
        )
        if dry_run.status != "DRY-RUN" or not plan.diff:
            return
        confirmation = CursesDialogs.text_input(win, " Wpisz pełną nazwę ACL: ")
        if (confirmation or "").casefold() != name.casefold():
            self._message_view(win, title="Anulowano", lines=["Nazwa ACL nie jest zgodna."])
            return
        if not CursesDialogs.confirm(win, f"Zastosować zmianę ACL {name}"):
            return
        result = transaction.apply(plan, commit=True, activate=True)
        self._message_view(
            win, title=f"Transakcja ACL: {name}",
            lines=self._secondary_result_lines(result),
            error=result.status != "COMMIT",
        )

    def _acl_entry_editor(
        self, win: curses.window, name: str, current: tuple[str, ...]
    ) -> list[str] | None:
        """Full-screen editor for hosts, networks and named ACL elements."""
        entries = list(current)
        selected = 0
        while True:
            height, width = win.getmaxyx()
            visible = max(1, height - 7)
            selected = min(selected, max(0, len(entries) - 1))
            offset = max(0, min(selected, len(entries) - visible))
            win.erase()
            win.addnstr(
                0, 0, f" Edycja ACL: {name} ".ljust(width), max(0, width - 1),
                curses.A_REVERSE | curses.A_BOLD,
            )
            win.addnstr(2, 2, "Host, sieć CIDR, negacja lub nazwana ACL", max(0, width - 4), curses.A_BOLD)
            for row, value in enumerate(entries[offset:offset + visible], 4):
                index = offset + row - 4
                attr = curses.A_REVERSE if index == selected else curses.A_NORMAL
                win.addnstr(row, 2, f"{index + 1:>3}. {value}", max(0, width - 4), attr)
            self._draw_context_panel_48(
                win, "EDYCJA ACL",
                (
                    ("Nazwa", name),
                    ("Elementy", len(entries)),
                    ("Wybrany", entries[selected] if entries else "-"),
                    ("Zmiany", "TAK" if entries != list(current) else "NIE"),
                    ("Walidacja", "PRZY PLANOWANIU"),
                ),
            )
            footer = " Ins dodaj   F4 edytuj   F8/Del usuń   F2 plan/dry-run   Esc/F10 anuluj "
            win.addnstr(height - 1, 0, footer.ljust(width), max(0, width - 1), curses.A_REVERSE)
            win.refresh()
            key = self._get_key(win)
            if key in (27, curses.KEY_F10, ord("q"), ord("Q")):
                if entries != list(current) and not CursesDialogs.confirm(win, "Porzucić zmiany ACL"):
                    continue
                return None
            if key in (curses.KEY_DOWN, ord("j")) and entries:
                selected = min(selected + 1, len(entries) - 1)
            elif key in (curses.KEY_UP, ord("k")) and entries:
                selected = max(0, selected - 1)
            elif key == curses.KEY_IC:
                value = CursesDialogs.text_input(win, " Nowy element ACL: ", row=2)
                if value is not None and value.strip():
                    entries.append(value.strip())
                    selected = len(entries) - 1
            elif key == curses.KEY_F4 and entries:
                value = CursesDialogs.text_input(
                    win, " Edytuj element ACL: ", initial=entries[selected], row=2
                )
                if value is not None and value.strip():
                    entries[selected] = value.strip()
            elif key in (curses.KEY_F8, curses.KEY_DC) and entries:
                if CursesDialogs.confirm(win, f"Usunąć {entries[selected]}"):
                    entries.pop(selected)
                    selected = min(selected, max(0, len(entries) - 1))
            elif key in (curses.KEY_F2, 19):
                if entries == list(current):
                    self._message_view(win, title=f"ACL: {name}", lines=["Brak zmian do zaplanowania."])
                    continue
                return entries

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
            self._draw_context_panel_48(
                win, "EDYCJA SECONDARY",
                (
                    ("Grupa", name),
                    ("Adresy", len(addresses)),
                    ("Wybrany", addresses[selected] if addresses else "-"),
                    ("Zmiany", "TAK" if addresses != list(current) else "NIE"),
                    ("Walidacja", "PRZY PLANOWANIU"),
                ),
            )
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
            self._draw_context_panel_48(
                win, "STAN OPERACYJNY",
                (
                    ("Strefa", zone.name),
                    ("Stan", item.state),
                    ("Typ", item.zone_type),
                    ("Zakres", "DEKLARACJA BIND"),
                    ("Plik strefy", "BEZ ZMIAN"),
                    ("Serial SOA", "BEZ ZMIAN"),
                ),
            )
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
