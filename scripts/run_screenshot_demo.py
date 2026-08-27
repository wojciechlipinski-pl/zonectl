#!/usr/bin/env python3
"""Run an isolated ZoneCTL TUI suitable for public screenshots.

The demo deliberately exposes only the main read-only view.  All displayed
state is deterministic and held in memory; no system configuration, zone file,
network service or host-specific context is consulted.
"""

from __future__ import annotations

import curses
import time

from zonectl.core.models import Health, Zone, ZoneStatus
from zonectl.core.zone_parser import DNSRecord
from zonectl.ui.curses_app import CursesApp
from zonectl.ui.dnssec_status_view import DnssecStatusView
from zonectl.ui.records.new_record import NewRecordDialog
from zonectl.ui.zone_create_dialog import ZoneCreateDialog, ZoneCreateForm


DEMO_ZONES = [
    Zone("alpha.example.test", None, group="Examples", dnssec_policy="default"),
    Zone("bravo.example.test", None, group="Examples", dnssec_policy="default"),
    Zone("mail.demo.example", None, group="Services"),
    Zone("sample.invalid", None, group="Services", dnssec_policy="default"),
    Zone("2.0.192.in-addr.arpa", None, group="Reverse"),
]


class MemoryHealthProvider:
    """Return synthetic health without touching BIND or the network."""

    def quick_status(self, zone: Zone) -> ZoneStatus:
        """Build a stable status and briefly expose the real wait overlay."""
        time.sleep(0.35)
        warning = zone.name == "sample.invalid"
        return ZoneStatus(
            zone=zone,
            health=Health.WARN if warning else Health.PASS,
            local_serial="2026082701",
            dns2_serial="2026082701",
            dnssec=zone.dnssec_policy is not None,
            file_exists=True,
            message="Kontrola demonstracyjna" if not warning else "Przykładowe ostrzeżenie",
        )


class ScreenshotDemoApp(CursesApp):
    """Restricted main-screen renderer for isolated screenshot sessions."""

    def __init__(self) -> None:
        super().__init__(  # type: ignore[arg-type]
            DEMO_ZONES,
            MemoryHealthProvider(),
            ["Examples", "Services", "Reverse"],
        )

    def _main(self, stdscr: curses.window) -> None:
        curses.curs_set(0)
        stdscr.keypad(True)
        stdscr.timeout(150)
        self._init_colors()
        self._start_refresh()
        while not self.stop_event.is_set():
            self._consume_results()
            self._draw(stdscr)
            stdscr.timeout(150)
            key = stdscr.getch()
            if self.refresh_indicator is not None:
                continue
            if key in (ord("q"), 27, curses.KEY_F10):
                break
            if key == ord("r"):
                self._start_refresh(force=True)
            elif key == ord("a"):
                self._show_add_record(stdscr)
            elif key == ord("z"):
                self._show_create_zone(stdscr)
            elif key == ord("b"):
                self._show_bind_report(stdscr)
            elif key == ord("d"):
                self._show_dnssec_report(stdscr)
            elif key == ord("l"):
                self._show_record_list(stdscr)
        self.stop_event.set()

    def _show_bind_report(self, win: curses.window) -> None:
        self._message_view(
            win,
            title="Środowisko BIND — demonstracja",
            lines=[
                "WYKRYTE ŚRODOWISKO",
                "Konfiguracja        /tmp/zonectl-demo/named.conf",
                "Pliki konfiguracji  8",
                "Strefy              5",
                "Strefy DNSSEC       3",
                "",
                "KLASYFIKACJA",
                "MANAGED             5  demonstracyjne strefy ZoneCTL",
                "LEGACY              0",
                "EXTERNAL            0",
                "RPZ                 0",
                "",
                "Wynik: raport syntetyczny — niczego nie zmieniono",
            ],
        )

    def _show_dnssec_report(self, win: curses.window) -> None:
        view = DnssecStatusView(
            zone="alpha.example.test",
            stage="ACTIVE",
            title="łańcuch zaufania DNSSEC jest aktywny",
            lines=(
                "Status raportu       PASS",
                "dnssec-policy        default",
                "inline-signing       TAK",
                "Podpisywanie BIND    TAK",
                "",
                "STAN KASP",
                "- goal:           omnipresent",
                "- dnskey:         omnipresent",
                "- ds:             omnipresent",
                "- zone rrsig:     omnipresent",
                "- key rrsig:      omnipresent",
                "",
                "DS DO PUBLIKACJI U REJESTRATORA",
                "  12345 13 2 " + "A1" * 32,
                "",
                "DS PUBLICZNY",
                "  12345 13 2 " + "A1" * 32,
                "",
                "KONTROLA DELEGACJI: PASS",
                "Resolvery:",
                "  [MATCH] 192.0.2.53 — DS jest zgodny",
                "Serwery autorytatywne:",
                "  [MATCH] ns1.example.test — DNSKEY i RRSIG są zgodne",
                "",
                "Postęp              4/4 warunków gotowych",
                "Następny krok        Monitoruj DNSSEC",
                "Publikacja DS        DOZWOLONA",
            ),
            publication_allowed=True,
            operation="WITHDRAWAL",
            operation_label="wycofanie",
        )
        win.erase()
        height, width = win.getmaxyx()
        win.addnstr(0, 0, " DNSSEC: alpha.example.test ".ljust(width), width - 1, curses.A_REVERSE | curses.A_BOLD)
        self._draw_dnssec_status_48(win, DEMO_ZONES[0], view, None, view.stage)
        win.addnstr(height - 1, 0, " q/Esc/F10 Powrót ".ljust(width), width - 1, curses.A_REVERSE)
        win.refresh()
        while win.getch() not in (ord("q"), ord("Q"), 27, curses.KEY_F10):
            pass

    def _show_record_list(self, win: curses.window) -> None:
        self._message_view(
            win,
            title="Rekordy DNS: alpha.example.test",
            lines=[
                "NAZWA                 TYP    TTL    WARTOŚĆ",
                "@                     A      3600   192.0.2.10",
                "@                     AAAA   3600   2001:db8::10",
                "@                     MX     3600   10 mail.demo.example.",
                "@                     NS     3600   ns1.example.test.",
                "@                     NS     3600   ns2.example.test.",
                "www                   CNAME  3600   alpha.example.test.",
                "_service              TXT    3600   \"synthetic fixture\"",
                "",
                "Status: BEZ ZMIAN — dane wyłącznie demonstracyjne",
            ],
        )

    @staticmethod
    def _show_add_record(win: curses.window) -> None:
        zone = Zone("alpha.example.test", None, group="Examples")
        records = (
            DNSRecord(
                owner="alpha.example.test.", ttl=3600, rrclass="IN",
                rtype="SOA", rdata="ns1.example.test. hostmaster.example.test. 2026082701 3600 900 1209600 3600",
                raw="",
            ),
        )
        NewRecordDialog().create_record_dialog(win, zone, records)

    @staticmethod
    def _show_create_zone(win: curses.window) -> None:
        initial = ZoneCreateForm(
            name="new-zone.example.test",
            primary_ns="ns1.example.test.",
            admin="hostmaster.example.test.",
            nameservers="ns1.example.test., ns2.example.test.",
            ipv4="192.0.2.10",
            group="Examples",
        )
        ZoneCreateDialog().collect(
            win,
            primary_ns=initial.primary_ns,
            admin=initial.admin,
            nameservers=initial.nameservers,
            groups=("Examples", "Services", "Reverse"),
            initial=initial,
        )


def main() -> None:
    """Launch the isolated documentation renderer."""
    ScreenshotDemoApp().run()


if __name__ == "__main__":
    main()
