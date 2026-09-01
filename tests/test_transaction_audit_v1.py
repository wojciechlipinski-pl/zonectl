from __future__ import annotations

import json
from pathlib import Path

import pytest

import zonectl.core.transaction as transaction_module
from zonectl.core.audit_store import AuditStorageError, Outcome, RecordKind
from zonectl.core.models import Zone
from zonectl.core.runner import CommandResult
from zonectl.core.transaction import TransactionEngine


class FakeConfig:
    def __init__(self, root: Path, zone: Zone):
        self.toolkit = {
            "state_dir": str(root / "state"),
            "transaction_backup_dir": str(root / "backups"),
            "transaction_dir": str(root / "transactions"),
            "lock_dir": str(root / "locks"),
            "audit_log": str(root / "audit.jsonl"),
            "audit_v1_log": str(root / "audit-v1.jsonl"),
        }
        self._zone = zone

    def zones(self) -> list[Zone]:
        return [self._zone]


def engine(tmp_path: Path) -> tuple[TransactionEngine, Path, Path]:
    target = tmp_path / "example.test.db"
    source = tmp_path / "candidate.db"
    target.write_text("active\n", encoding="utf-8")
    source.write_text("candidate\n", encoding="utf-8")
    return (
        TransactionEngine(FakeConfig(tmp_path, Zone("example.test", file=target))),
        source,
        target,
    )


def successful_validation(command: list[str], _timeout: int) -> CommandResult:
    if command[0] in {"named-checkzone", "named-checkconf"}:
        return CommandResult(0, "zone example.test/IN: loaded serial 2\n", "")
    raise AssertionError(f"Nieoczekiwane polecenie: {command}")


def test_dry_run_writes_start_and_canonical_result_without_raw_metadata(
    tmp_path: Path, monkeypatch
) -> None:
    tx, source, _target = engine(tmp_path)
    monkeypatch.setattr(transaction_module, "run", successful_validation)

    result = tx.apply(
        "example.test",
        source,
        commit=False,
        metadata={"change_count": 2, "token": "production-secret"},
    )

    audit = tx.audit_v1.store.read()
    assert result.status == "DRY-RUN"
    assert audit.issues == ()
    assert {item.record_kind for item in audit.records} == {
        RecordKind.RESULT,
        RecordKind.START,
    }
    final = next(
        item for item in audit.records if item.record_kind is RecordKind.RESULT
    )
    assert final.operation == "zone.records.apply"
    assert final.outcome is Outcome.DRY_RUN
    assert final.committed is False
    assert final.summary is not None
    assert final.summary.changed_record_count == 2
    assert final.summary.validation_gates == ("named-checkzone", "named-checkconf")
    raw = tx.audit_v1.store.path.read_text(encoding="utf-8")
    assert "production-secret" not in raw
    assert '"token"' not in raw
    assert str(source) not in raw


def test_failed_validation_still_has_manifest_and_terminal_audit_record(
    tmp_path: Path,
) -> None:
    tx, _source, _target = engine(tmp_path)
    missing = tmp_path / "missing.db"

    result = tx.validate("example.test", missing)

    audit = tx.audit_v1.store.read()
    assert result.status == "FAIL"
    final = next(
        item for item in audit.records if item.record_kind is RecordKind.RESULT
    )
    assert final.outcome is Outcome.FAILED
    assert final.manifest_ref == f"{result.transaction_id}.json"
    assert (tmp_path / "transactions" / f"{result.transaction_id}.json").is_file()


def test_audit_start_failure_blocks_commit_before_commands_or_file_change(
    tmp_path: Path, monkeypatch
) -> None:
    tx, source, target = engine(tmp_path)
    protected = tmp_path / "protected"
    protected.write_text("do-not-change", encoding="utf-8")
    tx.audit_v1.store.path.symlink_to(protected)
    original = target.read_bytes()
    commands: list[list[str]] = []
    monkeypatch.setattr(
        transaction_module,
        "run",
        lambda command, _timeout: commands.append(command),
    )

    with pytest.raises(AuditStorageError, match="non-symlink"):
        tx.apply("example.test", source, commit=True)

    assert commands == []
    assert target.read_bytes() == original
    assert protected.read_text(encoding="utf-8") == "do-not-change"


def test_rollback_result_maps_attempt_and_safe_relative_backup(
    tmp_path: Path, monkeypatch
) -> None:
    tx, source, target = engine(tmp_path)
    original = target.read_bytes()
    reload_calls = 0

    def fake_run(command: list[str], _timeout: int) -> CommandResult:
        nonlocal reload_calls
        if command[0] == "named-checkzone":
            return CommandResult(0, "zone example.test/IN: loaded serial 2\n", "")
        if command[0] == "named-checkconf":
            return CommandResult(0, "", "")
        if command[0] == "dig":
            return CommandResult(0, "ns hostmaster 1 3600 600 86400 300\n", "")
        if command[:2] == ["rndc", "reload"]:
            reload_calls += 1
            return CommandResult(1 if reload_calls == 1 else 0, "", "failure")
        raise AssertionError(command)

    monkeypatch.setattr(transaction_module, "run", fake_run)

    result = tx.apply("example.test", source, commit=True)

    assert result.status == "ROLLED-BACK"
    assert target.read_bytes() == original
    final = next(
        item
        for item in tx.audit_v1.store.read().records
        if item.record_kind is RecordKind.RESULT
    )
    assert final.outcome is Outcome.ROLLED_BACK
    assert final.rollback.attempted is True
    assert final.rollback.outcome is Outcome.PASS
    assert final.backup_ref is not None
    assert not Path(final.backup_ref).is_absolute()
    payload = json.loads(
        tx.audit_v1.store.path.read_text(encoding="utf-8").splitlines()[-1]
    )
    assert "stdout" not in payload
    assert "stderr" not in payload
    assert "command" not in payload
