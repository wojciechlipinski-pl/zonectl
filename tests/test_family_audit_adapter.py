from dataclasses import dataclass, field
from pathlib import Path

import pytest

from zonectl.core.audit_store import (
    AuditStore,
    AuditValidationError,
    Outcome,
    RecordKind,
    ResourceKind,
    Risk,
)
from zonectl.core.family_audit_adapter import FamilyAuditAdapter


@dataclass
class _Step:
    name: str


@dataclass
class _Result:
    transaction_id: str
    status: str
    committed: bool = False
    rolled_back: bool = False
    manifest: str | None = None
    backup: str | None = None
    steps: list[_Step] = field(default_factory=list)


def _adapter(tmp_path: Path) -> FamilyAuditAdapter:
    manifests = tmp_path / "manifests"
    return FamilyAuditAdapter(
        AuditStore(tmp_path / "audit" / "audit-v1.jsonl"),
        manifest_directory=manifests,
        backup_root=tmp_path / "backups",
    )


def test_adapter_writes_start_and_allowlisted_result(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    transaction_id = "20260901-120000-family-00000001"
    adapter.start(
        transaction_id,
        "zone.disable",
        ResourceKind.ZONE,
        "alpha.example.test",
        risk=Risk.HIGH,
        reason="planned retirement",
    )
    result = _Result(
        transaction_id,
        "DISABLED",
        committed=True,
        manifest=str(tmp_path / "manifests" / "result.json"),
        backup=str(tmp_path / "backups" / "safe-copy"),
        steps=[_Step(f"gate-{index}") for index in range(40)],
    )

    adapter.finish_result(result)

    records = adapter.store.read().records
    assert {record.record_kind for record in records} == {
        RecordKind.START,
        RecordKind.RESULT,
    }
    final = next(
        record for record in records if record.record_kind is RecordKind.RESULT
    )
    assert final.outcome is Outcome.COMMITTED
    assert final.manifest_ref == "result.json"
    assert final.backup_ref == "safe-copy"
    assert final.summary is not None
    assert len(final.summary.validation_gates) == 32


def test_adapter_records_successful_rollback(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    transaction_id = "20260901-120000-family-00000002"
    adapter.start(
        transaction_id,
        "rpz.install",
        ResourceKind.RPZ,
        "cert-rpz.example.test",
        risk=Risk.CRITICAL,
    )
    adapter.finish_result(_Result(transaction_id, "ROLLED-BACK", rolled_back=True))

    final = next(
        record
        for record in adapter.store.read().records
        if record.record_kind is RecordKind.RESULT
    )
    assert final.outcome is Outcome.ROLLED_BACK
    assert final.rollback.attempted
    assert final.rollback.outcome is Outcome.PASS


def test_sensitive_reason_is_rejected_before_start_is_persisted(
    tmp_path: Path,
) -> None:
    adapter = _adapter(tmp_path)
    with pytest.raises(AuditValidationError):
        adapter.start(
            "20260901-120000-family-00000003",
            "zone.disable",
            ResourceKind.ZONE,
            "alpha.example.test",
            risk=Risk.HIGH,
            reason="private key copied here",
        )

    assert not adapter.store.path.exists()
