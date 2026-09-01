"""Shared audit v1 adapter for specialized ZoneCTL transaction families."""

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
from .paths import AUDIT_V1_LOG


_OUTCOMES = {
    "PASS": Outcome.PASS,
    "COMMIT": Outcome.COMMITTED,
    "COMMITTED": Outcome.COMMITTED,
    "CONFIRMED": Outcome.COMMITTED,
    "DISABLED": Outcome.COMMITTED,
    "RESTORED": Outcome.COMMITTED,
    "QUARANTINED": Outcome.COMMITTED,
    "PURGED": Outcome.COMMITTED,
    "NO-CHANGE": Outcome.NO_CHANGE,
    "DRY-RUN": Outcome.DRY_RUN,
    "ROLLED-BACK": Outcome.ROLLED_BACK,
    "ROLLBACK-FAILED": Outcome.ROLLBACK_FAILED,
    "BLOCKED": Outcome.BLOCKED,
    "REJECTED": Outcome.BLOCKED,
    "CONFLICT": Outcome.BLOCKED,
    "CONFIRMATION-REQUIRED": Outcome.BLOCKED,
    "READ-ONLY": Outcome.READ_ONLY,
    "FAIL": Outcome.FAILED,
    "FAILED": Outcome.FAILED,
    "PURGE-FAILED": Outcome.FAILED,
    "VERIFY-FAILED": Outcome.FAILED,
}


@dataclass(frozen=True, slots=True)
class FamilyAuditContext:
    """Non-sensitive state retained between a family's START and RESULT."""

    transaction_id: str
    operation: str
    resource: AuditResource
    risk: Risk
    reason: str | None
    started_at: str
    started_monotonic: float


class FamilyAuditAdapter:
    """Record canonical envelopes for one specialized transaction family."""

    def __init__(
        self,
        store: AuditStore,
        *,
        manifest_directory: Path,
        backup_root: Path | None = None,
    ) -> None:
        self.store = store
        self.manifest_directory = manifest_directory
        self.backup_root = backup_root
        self._pending: dict[str, FamilyAuditContext] = {}

    def start(
        self,
        transaction_id: str,
        operation: str,
        resource_kind: ResourceKind,
        resource_name: str,
        *,
        risk: Risk,
        reason: str | None = None,
    ) -> FamilyAuditContext:
        """Persist START before a specialized transaction crosses any gate."""
        now = _now()
        context = FamilyAuditContext(
            transaction_id,
            operation,
            AuditResource(resource_kind, resource_name),
            risk,
            reason,
            now,
            time.monotonic(),
        )
        self.store.append(
            AuditRecord(
                record_id=str(uuid4()),
                transaction_id=transaction_id,
                recorded_at=now,
                record_kind=RecordKind.START,
                operation=operation,
                resource=context.resource,
                outcome=Outcome.STARTED,
                committed=False,
                rollback=AuditRollback(),
                actor=AuditActor(_uid()),
                risk=risk,
                reason=reason,
            )
        )
        self._pending[transaction_id] = context
        return context

    def finish(self, context: FamilyAuditContext, result: object) -> None:
        """Persist a canonical RESULT using only allowlisted aggregate fields."""
        status = str(getattr(result, "status"))
        outcome = _OUTCOMES.get(status)
        if outcome is None:
            raise RuntimeError(f"Nieobsługiwany wynik audytu: {status}")
        rolled_back = bool(getattr(result, "rolled_back", False))
        rollback_attempted = status in {"ROLLED-BACK", "ROLLBACK-FAILED"}
        steps = tuple(getattr(result, "steps", ()))
        self.store.append(
            AuditRecord(
                record_id=str(uuid4()),
                transaction_id=context.transaction_id,
                recorded_at=_now(),
                record_kind=RecordKind.RESULT,
                operation=context.operation,
                resource=context.resource,
                outcome=outcome,
                committed=bool(getattr(result, "committed", False)),
                rollback=AuditRollback(
                    rollback_attempted,
                    Outcome.PASS
                    if rollback_attempted and rolled_back
                    else Outcome.FAILED
                    if rollback_attempted
                    else None,
                ),
                started_at=context.started_at,
                duration_ms=max(
                    0, int((time.monotonic() - context.started_monotonic) * 1000)
                ),
                actor=AuditActor(_uid()),
                risk=context.risk,
                reason=context.reason,
                summary=AuditSummary(
                    changed_file_count=1
                    if bool(getattr(result, "committed", False))
                    else 0,
                    resource_count=1,
                    validation_gates=tuple(
                        str(getattr(step, "name"))
                        for step in steps
                        if _safe_gate(str(getattr(step, "name", "")))
                    )[:32],
                ),
                manifest_ref=self._relative_ref(
                    getattr(result, "manifest", None), self.manifest_directory
                ),
                backup_ref=self._relative_ref(
                    getattr(
                        result,
                        "backup",
                        getattr(
                            result,
                            "backup_directory",
                            getattr(result, "package_directory", None),
                        ),
                    ),
                    self.backup_root,
                ),
            )
        )
        self._pending.pop(context.transaction_id, None)

    def finish_result(self, result: object) -> None:
        """Finish a result using the START context retained by transaction id."""
        transaction_id = str(getattr(result, "transaction_id"))
        context = self._pending.get(transaction_id)
        if context is None:
            raise RuntimeError(f"Brak rekordu START audytu: {transaction_id}")
        self.finish(context, result)

    @staticmethod
    def default_store(
        manifest_directory: Path, *, system_anchor: Path | None = None
    ) -> AuditStore:
        """Use the central registry or an isolated sibling for fixture roots."""
        path = (system_anchor or manifest_directory).resolve()
        if system_anchor is not None:
            for root in (Path("/etc").resolve(), Path("/var").resolve()):
                try:
                    path.relative_to(root)
                    return AuditStore(AUDIT_V1_LOG)
                except ValueError:
                    continue
            return AuditStore(path.parent / "audit-v1.jsonl")
        try:
            path.relative_to(Path("/var").resolve())
        except ValueError:
            return AuditStore(path.parent / "audit-v1.jsonl")
        return AuditStore(AUDIT_V1_LOG)

    @staticmethod
    def _relative_ref(value: object, root: Path | None) -> str | None:
        if not isinstance(value, str) or not value or root is None:
            return None
        try:
            return Path(value).resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return None


def risk_from_text(value: str) -> Risk:
    """Map legacy risk labels conservatively to the canonical vocabulary."""
    try:
        return Risk(value.upper())
    except ValueError:
        return Risk.HIGH


def _safe_gate(value: str) -> bool:
    return (
        bool(value)
        and len(value) <= 80
        and all(character.isalnum() or character in "._:-" for character in value)
    )


def _now() -> str:
    return (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )


def _uid() -> int:
    getuid = getattr(os, "getuid", None)
    return int(getuid()) if getuid is not None else 0
