from __future__ import annotations

from dataclasses import replace
import inspect
from pathlib import Path

from zonectl.core.dnssec_ds_check import (
    DnskeyAuthorityCheck,
    DnssecDsCheck,
    DsResolverCheck,
)
from zonectl.core.dnssec_report import DnssecReport
from zonectl.ui.dnssec_status_view import DnssecStatusView
from zonectl.ui.curses_app import CursesApp
from zonectl.core.models import Zone


def test_domain_view_uses_terminal_key_decoder() -> None:
    source = inspect.getsource(CursesApp._domain_view)

    assert "key = self._get_key(win)" in source
    assert "key = win.getch()" not in source


def report(*, zone_rrsig: str = "rumoured") -> DnssecReport:
    return DnssecReport(
        zone="example.pl",
        status="WARN",
        configured=True,
        dnssec_policy="default",
        inline_signing=True,
        loaded=True,
        signing=True,
        rndc_status=(
            "dnssec-policy: default",
            "- dnskey: omnipresent",
            "- ds: hidden",
            f"- zone rrsig: {zone_rrsig}",
            "- key rrsig: omnipresent",
        ),
        key_directory="/keys",
        key_files=(),
        dnskey_records=("257 3 13 key",),
        rrsig_records=("DNSKEY signature",),
        calculated_ds=("12345 13 2 ABCD",),
        parent_ds_records=(),
        parent_ds_matches=False,
        warnings=("Brak DS",),
        errors=(),
        next_key_event="Wed, 05 Aug 2026 07:41:35 GMT",
    )


def delegation() -> DnssecDsCheck:
    return DnssecDsCheck(
        zone="example.pl",
        status="NOT_READY",
        kasp_ready=False,
        expected_ds=("12345 13 2 ABCD",),
        resolver_checks=(
            DsResolverCheck("1.1.1.1", "MISSING", (), "DS nie jest widoczny"),
        ),
        authority_checks=(
            DnskeyAuthorityCheck(
                "ns1.example.pl", "MATCH", True, ("key",), ("sig",), "OK"
            ),
            DnskeyAuthorityCheck(
                "ns2.example.pl", "MATCH", True, ("key",), ("sig",), "OK"
            ),
        ),
        next_action="Nie publikuj DS.",
        errors=(),
    )


def test_view_shows_stage_time_delegation_and_block() -> None:
    view = DnssecStatusView.build(report(), delegation())
    text = "\n".join(view.lines)

    assert view.stage == "PROPAGATING"
    assert view.publication_allowed is False
    assert "2026-08-05" in text
    assert "[MATCH] ns1.example.pl" in text
    assert "[MATCH] ns2.example.pl" in text
    assert "JESZCZE ZABLOKOWANA" in text


def test_view_allows_ds_when_kasp_is_ready() -> None:
    ready_delegation = delegation()
    ready_delegation = DnssecDsCheck(
        zone=ready_delegation.zone,
        status="NOT_PUBLISHED",
        kasp_ready=True,
        expected_ds=ready_delegation.expected_ds,
        resolver_checks=ready_delegation.resolver_checks,
        authority_checks=ready_delegation.authority_checks,
        next_action=ready_delegation.next_action,
        errors=(),
    )
    view = DnssecStatusView.build(
        report(zone_rrsig="omnipresent"), ready_delegation
    )

    assert view.stage == "READY_FOR_DS"
    assert view.publication_allowed is True
    assert "DOZWOLONA" in "\n".join(view.lines)


def test_active_report_waits_when_ds_is_only_partially_visible() -> None:
    active_report = replace(
        report(zone_rrsig="omnipresent"),
        status="PASS",
        parent_ds_records=("12345 13 2 ABCD",),
        parent_ds_matches=True,
        warnings=(),
    )
    partial = replace(delegation(), status="PROPAGATING", kasp_ready=True)

    view = DnssecStatusView.build(active_report, partial)

    assert view.stage == "DS_PROPAGATING"
    assert view.publication_allowed is False


def test_tui_collects_report_and_delegation_with_configured_resolvers(
    monkeypatch,
) -> None:
    calls = []

    class FakeReporter:
        def __init__(self, **kwargs):
            calls.append(("reporter-init", kwargs))

        def collect(self, zone, key_directory):
            calls.append(("report", zone.name, key_directory))
            return report()

    class FakeChecker:
        def __init__(self, **kwargs):
            calls.append(("checker-init", kwargs))

        def collect(self, zone, resolvers):
            calls.append(("check", zone, resolvers))
            return delegation()

    monkeypatch.setattr("zonectl.ui.curses_app.DnssecReporter", FakeReporter)
    monkeypatch.setattr("zonectl.ui.curses_app.DnssecDsChecker", FakeChecker)

    app = CursesApp.__new__(CursesApp)
    app.config = type(
        "Config",
        (),
        {
            "toolkit": {
                "local_server": "127.0.0.53",
                "dig_timeout": "5",
                "dnssec_resolvers": "r1, r2",
                "dnssec_key_directory": "/test/keys",
            }
        },
    )()

    view = app._collect_dnssec_status(Zone("example.pl", None))

    assert view.stage == "PROPAGATING"
    assert ("check", "example.pl", ("r1", "r2")) in calls
    assert ("report", "example.pl", Path("/test/keys")) in calls


def test_view_labels_insecure_policy_as_withdrawing() -> None:
    withdrawing = replace(
        report(),
        dnssec_policy="insecure",
        rndc_status=(
            "dnssec-policy: insecure",
            "- dnskey: omnipresent",
            "- ds: unretentive",
            "- zone rrsig: omnipresent",
            "- key rrsig: omnipresent",
        ),
    )

    view = DnssecStatusView.build(withdrawing)
    text = "\n".join(view.lines)

    assert view.stage == "WITHDRAWING"
    assert "Finalizacja         ZABLOKOWANA" in text
    assert "Publikacja DS" not in text
