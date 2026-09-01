"""Pure view model for the read-only audit browser."""

from __future__ import annotations

from dataclasses import dataclass

from ..core.audit_store import AuditIssue, AuditRecord, Outcome, RecordKind
from ..core.zone_model import ChangeKind, ZoneChange


OUTCOME_FILTERS: tuple[Outcome | None, ...] = (
    None,
    Outcome.COMMITTED,
    Outcome.ROLLED_BACK,
    Outcome.FAILED,
    Outcome.BLOCKED,
    Outcome.DRY_RUN,
    Outcome.NO_CHANGE,
    Outcome.PASS,
)


@dataclass(slots=True)
class AuditViewState:
    """Hold allowlisted audit records and interactive browser filters."""

    records: tuple[AuditRecord, ...]
    issues: tuple[AuditIssue, ...] = ()
    zone_filter: str = ""
    operation_filter: str = ""
    outcome_filter: Outcome | None = None
    include_events: bool = False

    @property
    def visible_records(self) -> tuple[AuditRecord, ...]:
        """Return records matching the current case-insensitive filters."""
        zone = self.zone_filter.casefold()
        operation = self.operation_filter.casefold()
        return tuple(
            record
            for record in self.records
            if (self.include_events or record.record_kind is RecordKind.RESULT)
            and (not zone or zone in record.resource.name.casefold())
            and (not operation or operation in record.operation.casefold())
            and (self.outcome_filter is None or record.outcome is self.outcome_filter)
        )

    def cycle_outcome(self) -> None:
        """Select the next bounded status filter."""
        index = OUTCOME_FILTERS.index(self.outcome_filter)
        self.outcome_filter = OUTCOME_FILTERS[(index + 1) % len(OUTCOME_FILTERS)]

    def clear_filters(self) -> None:
        """Restore the default result-only unfiltered view."""
        self.zone_filter = ""
        self.operation_filter = ""
        self.outcome_filter = None
        self.include_events = False

    def filter_summary(self) -> str:
        """Render a compact filter summary suitable for narrow terminals."""
        status = self.outcome_filter.value if self.outcome_filter else "wszystkie"
        kind = "zdarzenia" if self.include_events else "wyniki"
        return (
            f"Strefa: {self.zone_filter or '-'}  Operacja: "
            f"{self.operation_filter or '-'}  Status: {status}  Widok: {kind}"
        )


def audit_list_line(record: AuditRecord, *, compact: bool = False) -> str:
    """Render one stable allowlisted row without leaking record payloads."""
    timestamp = record.recorded_at.replace("T", " ")[:19]
    if compact:
        return (
            f"{timestamp} {record.outcome.value:<12} "
            f"{record.resource.name} {record.operation}"
        )
    return (
        f"{timestamp:<19} {record.outcome.value:<15} "
        f"{record.resource.name:<30} {record.operation:<28} "
        f"{record.transaction_id}"
    )


def audit_detail_lines(record: AuditRecord) -> tuple[str, ...]:
    """Return a readable allowlisted detail view for one audit record."""
    rollback = (
        record.rollback.outcome.value if record.rollback.outcome is not None else "NIE"
    )
    summary = record.summary
    lines = [
        f"Czas             {record.recorded_at}",
        f"Transakcja       {record.transaction_id}",
        f"Rodzaj wpisu     {record.record_kind.value}",
        f"Operacja         {record.operation}",
        f"Zasób            {record.resource.kind.value}: {record.resource.name}",
        f"Status           {record.outcome.value}",
        f"Commit           {'TAK' if record.committed else 'NIE'}",
        f"Rollback         {rollback}",
    ]
    if record.duration_ms is not None:
        lines.append(f"Czas wykonania   {record.duration_ms} ms")
    if record.risk is not None:
        lines.append(f"Ryzyko           {record.risk.value}")
    if record.reason:
        lines.append(f"Uzasadnienie     {record.reason}")
    if summary is not None:
        lines.extend(
            (
                "",
                "PODSUMOWANIE",
                f"Pliki            {summary.changed_file_count if summary.changed_file_count is not None else '-'}",
                f"Rekordy          {summary.changed_record_count if summary.changed_record_count is not None else '-'}",
                f"Zasoby           {summary.resource_count if summary.resource_count is not None else '-'}",
                "Walidacje        " + (", ".join(summary.validation_gates) or "-"),
            )
        )
    if record.manifest_ref:
        lines.append(f"Manifest         {record.manifest_ref}")
    if record.backup_ref:
        lines.append(f"Backup           {record.backup_ref}")
    return tuple(lines)


def pending_change_summary(
    changes: tuple[ZoneChange, ...] | list[ZoneChange], zone_name: str
) -> tuple[str, ...]:
    """Build the mandatory operator summary shown before a record commit."""
    counts = {
        kind: sum(1 for change in changes if change.kind is kind) for kind in ChangeKind
    }
    lines = [
        f"Strefa           {zone_name}",
        f"Łącznie zmian   {len(changes)}",
        f"Dodawane        {counts[ChangeKind.ADD]}",
        f"Modyfikowane    {counts[ChangeKind.MODIFY]}",
        f"Usuwane         {counts[ChangeKind.DELETE]}",
        "Pliki           1 plik strefy",
        "Serial          sprawdzany po aktywacji",
        "Walidacje       named-checkzone, zapis atomowy, kontrola SOA",
        "Backup          tworzony przed zmianą aktywnego pliku",
        "Operacja BIND   rndc reload strefy",
        "",
        "ZMIANY",
    ]
    labels = {
        ChangeKind.ADD: "+",
        ChangeKind.MODIFY: "~",
        ChangeKind.DELETE: "-",
    }
    for change in changes:
        record = change.record
        owner = record.relative_owner(zone_name)
        ttl = record.ttl if record.ttl is not None else "-"
        lines.append(
            f"{labels[change.kind]} {owner}  {record.rtype}  {ttl}  {record.rdata}"
        )
    lines.extend(
        (
            "",
            "Po zatwierdzeniu zostanie wykonana transakcja z backupem i walidacją.",
        )
    )
    return tuple(lines)
