from __future__ import annotations

import json
import os
import stat
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest

from zonectl.core.audit_store import (
    AUDIT_SCHEMA,
    AuditActor,
    AuditRecord,
    AuditResource,
    AuditRollback,
    AuditStorageError,
    AuditStore,
    AuditSummary,
    AuditValidationError,
    Outcome,
    RecordKind,
    ResourceKind,
    Risk,
)


def record(number: int = 1, *, resource: str = "example.test") -> AuditRecord:
    return AuditRecord(
        record_id=str(UUID(int=number)),
        transaction_id=f"demo-transaction-{number}",
        recorded_at=f"2026-09-01T10:00:{number:02d}Z",
        record_kind=RecordKind.RESULT,
        operation="zone.records.apply",
        resource=AuditResource(ResourceKind.ZONE, resource),
        outcome=Outcome.COMMITTED,
        committed=True,
        rollback=AuditRollback(),
        started_at="2026-09-01T10:00:00Z",
        duration_ms=number * 10,
        actor=AuditActor(1000, "operator"),
        risk=Risk.MEDIUM,
        reason="approved maintenance",
        summary=AuditSummary(1, 2, 1, ("named-checkzone", "rndc-reload")),
        manifest_ref=f"transactions/demo-{number}.json",
        backup_ref=f"backups/example.test/demo-{number}.db",
    )


def test_round_trip_uses_allowlisted_schema_and_stable_order(tmp_path: Path) -> None:
    store = AuditStore(tmp_path / "audit-v1.jsonl")
    expected = record()

    store.append(expected)

    result = store.read()
    assert result.records == (expected,)
    assert result.issues == ()
    payload = json.loads(store.path.read_text(encoding="utf-8"))
    assert payload["schema"] == AUDIT_SCHEMA
    assert "host" not in payload
    assert "details" not in payload
    assert "stdout" not in payload
    assert store.path.read_text(encoding="utf-8").endswith("\n")


def test_store_enforces_directory_file_and_lock_modes(tmp_path: Path) -> None:
    directory = tmp_path / "audit"
    directory.mkdir(mode=0o777)
    store = AuditStore(directory / "audit-v1.jsonl")
    store.append(record())

    assert stat.S_IMODE(directory.stat().st_mode) == 0o750
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o640
    assert stat.S_IMODE(store.lock_path.stat().st_mode) == 0o640


def test_append_rejects_symlink_target(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_text("protected", encoding="utf-8")
    store = AuditStore(tmp_path / "audit-v1.jsonl")
    store.path.symlink_to(target)

    with pytest.raises(AuditStorageError, match="non-symlink"):
        store.append(record())

    assert target.read_text(encoding="utf-8") == "protected"


def test_reader_skips_corrupt_lines_and_reports_safe_diagnostics(
    tmp_path: Path,
) -> None:
    store = AuditStore(tmp_path / "audit-v1.jsonl")
    store.append(record(1))
    with store.path.open("ab") as handle:
        handle.write(b"{private production data\n")
    store.append(record(2))

    result = store.read()

    assert [item.transaction_id for item in result.records] == [
        "demo-transaction-2",
        "demo-transaction-1",
    ]
    assert len(result.issues) == 1
    assert result.issues[0].line_number == 2
    assert result.issues[0].reason == "record is not valid JSON"
    assert "production" not in result.issues[0].reason


def test_reader_reports_truncation_instead_of_silently_hiding_records(
    tmp_path: Path,
) -> None:
    store = AuditStore(tmp_path / "audit-v1.jsonl")
    store.append(record(1))
    store.append(record(2))

    result = store.read(limit=1)

    assert len(result.records) == 1
    assert result.issues[-1].reason == "result limit exceeded"


@pytest.mark.parametrize(
    "changes",
    [
        {"reason": 'secret "top-secret"'},
        {"reason": "-----BEGIN PRIVATE KEY-----"},
        {"manifest_ref": "/etc/bind/named.conf"},
        {"backup_ref": "../production.db"},
    ],
)
def test_validation_rejects_sensitive_material_and_unsafe_paths(
    changes: dict[str, object],
) -> None:
    with pytest.raises(AuditValidationError):
        replace(record(), **changes)


def test_untrusted_payload_cannot_inject_non_allowlisted_fields() -> None:
    payload = record().to_dict()
    payload["private_key"] = "must-not-survive"
    payload["stdout"] = "must-not-survive"

    parsed = AuditRecord.from_dict(payload)

    assert "private_key" not in parsed.to_dict()
    assert "stdout" not in parsed.to_dict()


def test_retention_is_dry_run_by_default_and_preserves_latest_resource_result(
    tmp_path: Path,
) -> None:
    store = AuditStore(tmp_path / "audit-v1.jsonl")
    store.append(record(1, resource="first.example"))
    store.append(record(2, resource="second.example"))
    store.append(record(3, resource="first.example"))
    plan = store.plan_retention(max_records=1)

    assert plan.source_size == 3
    assert set(plan.keep_record_ids) == {record(2).record_id, record(3).record_id}
    assert plan.remove_record_ids == (record(1).record_id,)
    with pytest.raises(AuditStorageError, match="confirmation"):
        store.apply_retention(plan)
    assert len(store.read().records) == 3

    assert store.apply_retention(plan, confirm=True) == 1
    assert {item.record_id for item in store.read().records} == set(
        plan.keep_record_ids
    )


def test_retention_stops_when_registry_is_corrupt_or_changed(tmp_path: Path) -> None:
    store = AuditStore(tmp_path / "audit-v1.jsonl")
    store.append(record(1))
    plan = store.plan_retention(max_records=1)
    store.append(record(2))

    with pytest.raises(AuditStorageError, match="changed"):
        store.apply_retention(plan, confirm=True)

    with store.path.open("ab") as handle:
        handle.write(b"not-json\n")
    with pytest.raises(AuditStorageError, match="invalid"):
        store.plan_retention(max_records=1)


def test_existing_file_mode_is_repaired_without_changing_content(
    tmp_path: Path,
) -> None:
    store = AuditStore(tmp_path / "audit-v1.jsonl")
    store.append(record(1))
    os.chmod(store.path, 0o666)

    store.append(record(2))

    assert stat.S_IMODE(store.path.stat().st_mode) == 0o640
    assert len(store.read().records) == 2
