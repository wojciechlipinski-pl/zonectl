"""Bounded, read-only queries and renderers for the audit v1 registry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from .audit_store import (
    MAX_RESULTS,
    AuditIssue,
    AuditReadResult,
    AuditRecord,
    RecordKind,
)


@dataclass(frozen=True, slots=True)
class AuditFilters:
    """Allowlisted filters accepted by the audit CLI."""

    resource_name: str | None = None
    outcome: str | None = None
    operation: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    transaction_id: str | None = None
    results_only: bool = True


@dataclass(frozen=True, slots=True)
class AuditQueryResult:
    """Filtered records with safe diagnostics from the underlying registry."""

    records: tuple[AuditRecord, ...]
    issues: tuple[AuditIssue, ...]

    def to_dict(self) -> dict[str, object]:
        """Return an allowlisted JSON-ready export envelope."""
        return {
            "schema": "zonectl.audit-query/v1",
            "records": [record.to_dict() for record in self.records],
            "issues": [
                {"line_number": issue.line_number, "reason": issue.reason}
                for issue in self.issues
            ],
        }


def filter_audit(
    source: AuditReadResult,
    filters: AuditFilters,
    *,
    limit: int,
) -> AuditQueryResult:
    """Filter an already bounded registry read without accessing other files."""
    if limit < 1 or limit > MAX_RESULTS:
        raise ValueError(f"limit must be between 1 and {MAX_RESULTS}")
    records = tuple(record for record in source.records if _matches(record, filters))[
        :limit
    ]
    return AuditQueryResult(records, source.issues)


def parse_audit_time(value: str | None) -> datetime | None:
    """Parse an ISO-8601 filter and require an explicit timezone."""
    if value is None:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("audit time requires an explicit timezone")
    return parsed


def render_audit_list(records: Iterable[AuditRecord]) -> str:
    """Render one stable, compact line per audit record."""
    return "\n".join(
        f"{record.recorded_at}  {record.resource.name:<30} "
        f"{record.outcome.value:<16} {record.operation:<28} "
        f"{record.transaction_id}"
        for record in records
    )


def render_audit_details(records: Iterable[AuditRecord]) -> str:
    """Render full allowlisted records as deterministic readable JSON."""
    return "\n\n".join(
        json.dumps(record.to_dict(), ensure_ascii=False, indent=2) for record in records
    )


def _matches(record: AuditRecord, filters: AuditFilters) -> bool:
    if filters.results_only and record.record_kind is not RecordKind.RESULT:
        return False
    if (
        filters.resource_name
        and record.resource.name.casefold() != filters.resource_name.casefold()
    ):
        return False
    if filters.outcome and record.outcome.value != filters.outcome.upper():
        return False
    if filters.operation and record.operation != filters.operation:
        return False
    if filters.transaction_id and record.transaction_id != filters.transaction_id:
        return False
    recorded = parse_audit_time(record.recorded_at)
    if recorded is None:
        return False
    if filters.since and recorded < filters.since:
        return False
    if filters.until and recorded > filters.until:
        return False
    return True
