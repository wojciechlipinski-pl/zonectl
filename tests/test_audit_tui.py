from __future__ import annotations

import inspect

from zonectl.core.audit_store import (
    AuditIssue,
    AuditRecord,
    AuditResource,
    AuditRollback,
    Outcome,
    RecordKind,
    ResourceKind,
)
from zonectl.core.zone_model import ChangeKind, ZoneChange
from zonectl.core.zone_parser import DNSRecord
from zonectl.ui.audit_view import (
    AuditViewState,
    audit_detail_lines,
    audit_list_line,
    pending_change_summary,
)
from zonectl.ui.curses_app import CursesApp


def _record(
    *,
    kind: RecordKind = RecordKind.RESULT,
    outcome: Outcome = Outcome.COMMITTED,
    zone: str = "alpha.example.test",
    operation: str = "zone.records.save",
) -> AuditRecord:
    return AuditRecord(
        record_id="11111111-1111-4111-8111-111111111111",
        transaction_id="20260901-100000-alpha-00000001",
        recorded_at="2026-09-01T10:00:02Z",
        record_kind=kind,
        operation=operation,
        resource=AuditResource(ResourceKind.ZONE, zone),
        outcome=outcome,
        committed=outcome is Outcome.COMMITTED,
        rollback=AuditRollback(),
    )


def test_audit_view_filters_results_and_can_include_start_events() -> None:
    committed = _record()
    blocked = _record(
        outcome=Outcome.BLOCKED,
        zone="beta.example.test",
        operation="dnssec.enable",
    )
    started = _record(kind=RecordKind.START, outcome=Outcome.STARTED)
    state = AuditViewState((committed, blocked, started), (AuditIssue(9, "bad"),))

    assert state.visible_records == (committed, blocked)
    state.zone_filter = "BETA"
    assert state.visible_records == (blocked,)
    state.zone_filter = ""
    state.operation_filter = "DNSSEC"
    assert state.visible_records == (blocked,)
    state.operation_filter = ""
    state.cycle_outcome()
    assert state.outcome_filter is Outcome.COMMITTED
    assert state.visible_records == (committed,)
    state.clear_filters()
    state.include_events = True
    assert state.visible_records == (committed, blocked, started)


def test_audit_rows_and_details_are_allowlisted_and_responsive() -> None:
    record = _record()
    assert "alpha.example.test" in audit_list_line(record)
    assert "2026-09-01 10:00:02" in audit_list_line(record, compact=True)
    details = "\n".join(audit_detail_lines(record))
    assert "COMMITTED" in details
    assert record.transaction_id in details
    assert record.record_id not in details


def test_pending_change_summary_counts_each_operation() -> None:
    record = DNSRecord("www", 3600, "IN", "A", "192.0.2.10", "")
    changes = [
        ZoneChange(ChangeKind.ADD, None, record),
        ZoneChange(ChangeKind.MODIFY, record, record),
        ZoneChange(ChangeKind.DELETE, record, None),
    ]
    summary = "\n".join(pending_change_summary(changes, "example.test"))
    assert "Łącznie zmian   3" in summary
    assert "Dodawane        1" in summary
    assert "Modyfikowane    1" in summary
    assert "Usuwane         1" in summary
    assert "backupem i walidacją" in summary


def test_main_tui_routes_f6_to_read_only_audit_browser() -> None:
    main = inspect.getsource(CursesApp._main)
    footer = inspect.getsource(CursesApp._draw_main_footer)
    browser = inspect.getsource(CursesApp._audit_browser_view)
    assert "curses.KEY_F6" in main
    assert '"F6", "Audyt"' in footer
    assert "self.audit_store.read" in browser
    assert ".append(" not in browser
    assert "width < 118 or height < 28" in browser
