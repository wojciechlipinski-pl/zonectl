"""Adapter from base zone transactions to the audit v1 registry."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .audit_store import (
    AuditActor,
    AuditRecord,
    AuditResource,
    AuditRollback,
    AuditStore,
    AuditSummary,
    Outcome,
    RecordKind,
    ResourceKind,
    Risk,
)


_OUTCOMES = {
    "PASS": Outcome.PASS,
    "VERIFY": Outcome.PASS,
    "NO-CHANGE": Outcome.NO_CHANGE,
    "DRY-RUN": Outcome.DRY_RUN,
    "COMMIT": Outcome.COMMITTED,
    "ROLLBACK-COMMIT": Outcome.COMMITTED,
    "ROLLED-BACK": Outcome.ROLLED_BACK,
    "ROLLBACK-FAILED": Outcome.ROLLBACK_FAILED,
    "READ-ONLY": Outcome.READ_ONLY,
    "FAIL": Outcome.FAILED,
    "FAILED": Outcome.FAILED,
}
_VALIDATION_GATES = {
    "named-checkzone",
    "named-checkconf",
    "rndc-reload",
    "verify-soa",
    "atomic-install",
    "atomic-restore",
    "rollback",
}


@dataclass(frozen=True, slots=True)
class PendingAudit:
    """In-memory timing context between START and RESULT records."""

    operation: str
    risk: Risk
    started_at: str
    started_monotonic: float


class TransactionAuditAdapter:
    """Write privacy-safe audit envelopes for the base transaction engine."""

    def __init__(self, store: AuditStore, backup_dir: Path):
        self.store = store
        self.backup_dir = backup_dir
        self._pending: dict[str, PendingAudit] = {}

    def start(
        self,
        transaction_id: str,
        zone: str,
        operation: str,
        *,
        risk: Risk,
    ) -> None:
        """Persist START and retain only non-sensitive timing context."""
        started_at = _now()
        pending = PendingAudit(operation, risk, started_at, time.monotonic())
        self.store.append(
            AuditRecord(
                record_id=str(uuid4()),
                transaction_id=transaction_id,
                recorded_at=started_at,
                record_kind=RecordKind.START,
                operation=operation,
                resource=AuditResource(ResourceKind.ZONE, zone),
                outcome=Outcome.STARTED,
                committed=False,
                rollback=AuditRollback(),
                actor=AuditActor(_uid()),
                risk=risk,
            )
        )
        self._pending[transaction_id] = pending

    def finish(self, result: object, outcome: str) -> None:
        """Map a transaction result to one canonical, allowlisted RESULT."""
        transaction_id = str(getattr(result, "transaction_id"))
        pending = self._pending.get(transaction_id)
        if pending is None:
            raise RuntimeError(f"Brak rekordu START audytu: {transaction_id}")
        canonical = _OUTCOMES.get(outcome)
        if canonical is None:
            raise RuntimeError(f"Nieobsługiwany wynik audytu: {outcome}")
        rolled_back = bool(getattr(result, "rolled_back", False))
        rollback_attempted = outcome in {"ROLLED-BACK", "ROLLBACK-FAILED"}
        backup_ref = self._backup_ref(getattr(result, "backup", None))
        steps = tuple(getattr(result, "steps", ()))
        metadata = getattr(result, "metadata", {})
        changed_records = (
            metadata.get("change_count") if isinstance(metadata, dict) else None
        )
        if (
            not isinstance(changed_records, int)
            or isinstance(changed_records, bool)
            or changed_records < 0
        ):
            changed_records = None
        self.store.append(
            AuditRecord(
                record_id=str(uuid4()),
                transaction_id=transaction_id,
                recorded_at=_now(),
                record_kind=RecordKind.RESULT,
                operation=pending.operation,
                resource=AuditResource(ResourceKind.ZONE, str(getattr(result, "zone"))),
                outcome=canonical,
                committed=bool(getattr(result, "committed", False)),
                rollback=AuditRollback(
                    rollback_attempted,
                    Outcome.PASS
                    if rollback_attempted and rolled_back
                    else Outcome.FAILED
                    if rollback_attempted
                    else None,
                ),
                started_at=pending.started_at,
                duration_ms=max(
                    0, int((time.monotonic() - pending.started_monotonic) * 1000)
                ),
                actor=AuditActor(_uid()),
                risk=pending.risk,
                summary=AuditSummary(
                    changed_file_count=1
                    if bool(getattr(result, "committed", False))
                    else 0,
                    changed_record_count=changed_records,
                    resource_count=1,
                    validation_gates=tuple(
                        str(getattr(step, "name"))
                        for step in steps
                        if str(getattr(step, "name", "")) in _VALIDATION_GATES
                    ),
                ),
                manifest_ref=f"{transaction_id}.json",
                backup_ref=backup_ref,
            )
        )
        self._pending.pop(transaction_id, None)

    def _backup_ref(self, value: object) -> str | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            return (
                Path(value).resolve().relative_to(self.backup_dir.resolve()).as_posix()
            )
        except ValueError:
            return None


def _now() -> str:
    return (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )


def _uid() -> int:
    getuid = getattr(os, "getuid", None)
    return int(getuid()) if getuid is not None else 0
