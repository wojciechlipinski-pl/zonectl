from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from zonectl import cli
from zonectl.core.zone_quarantine_purge import (
    QuarantinePurgeError,
    QuarantinePurgeTransaction,
)


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


class _EmptyConfig:
    def zones(self):
        return []


def make_package(root: Path, created: str = "2026-05-01T12:00:00+00:00") -> Path:
    package = root / "example.invalid/tx-old"
    package.mkdir(parents=True)
    files = {"zone.db": b"zone\n", "zone.conf": b"declaration\n"}
    for name, content in files.items():
        (package / name).write_bytes(content)
    manifest = {
        "transaction_id": "tx-old",
        "zone": "example.invalid",
        "status": "QUARANTINED",
        "created_at": created,
        "files": {
            name: hashlib.sha256(content).hexdigest()
            for name, content in files.items()
        },
    }
    (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return package


def transaction(tmp_path: Path) -> QuarantinePurgeTransaction:
    return QuarantinePurgeTransaction(
        quarantine_root=tmp_path / "quarantine",
        audit_directory=tmp_path / "audit",
        staging_root=tmp_path / "staging",
        retention_days=90,
        now=lambda: NOW,
    )


def test_plan_accepts_only_verified_package_after_retention(tmp_path: Path) -> None:
    package = make_package(tmp_path / "quarantine")
    plan = transaction(tmp_path).plan(
        "example.invalid", package, reason="zatwierdzone sprzątanie"
    )
    assert plan.package_id == "tx-old"
    assert plan.age_days == 115


def test_plan_rejects_package_still_in_retention(tmp_path: Path) -> None:
    package = make_package(
        tmp_path / "quarantine", "2026-08-20T12:00:00+00:00"
    )
    with pytest.raises(QuarantinePurgeError, match="RETAIN"):
        transaction(tmp_path).plan("example.invalid", package, reason="test")


def test_plan_rejects_unexpected_package_content(tmp_path: Path) -> None:
    package = make_package(tmp_path / "quarantine")
    (package / "extra").write_text("do not delete", encoding="utf-8")
    with pytest.raises(QuarantinePurgeError, match="nieoczekiwaną"):
        transaction(tmp_path).plan("example.invalid", package, reason="test")


def test_dry_run_does_not_delete_or_write_audit(tmp_path: Path) -> None:
    package = make_package(tmp_path / "quarantine")
    tx = transaction(tmp_path)
    plan = tx.plan("example.invalid", package, reason="test")
    result = tx.apply(plan)
    assert result.status == "DRY-RUN"
    assert package.is_dir()
    assert not (tmp_path / "audit").exists()


def test_commit_requires_zone_and_package_confirmations(tmp_path: Path) -> None:
    package = make_package(tmp_path / "quarantine")
    tx = transaction(tmp_path)
    plan = tx.plan("example.invalid", package, reason="test")
    result = tx.apply(plan, commit=True, confirmation="example.invalid")
    assert result.status == "CONFIRMATION-REQUIRED"
    assert package.is_dir()


def test_preflight_blocks_changed_package_after_plan(tmp_path: Path) -> None:
    package = make_package(tmp_path / "quarantine")
    tx = transaction(tmp_path)
    plan = tx.plan("example.invalid", package, reason="test")
    (package / "zone.db").write_text("changed", encoding="utf-8")
    result = tx.apply(
        plan,
        commit=True,
        confirmation="example.invalid",
        package_confirmation="tx-old",
    )
    assert result.status == "BLOCKED"
    assert package.is_dir()


def test_verified_commit_purges_package_and_keeps_external_audit(tmp_path: Path) -> None:
    package = make_package(tmp_path / "quarantine")
    tx = transaction(tmp_path)
    plan = tx.plan("example.invalid", package, reason="koniec retencji")
    result = tx.apply(
        plan,
        commit=True,
        confirmation="example.invalid",
        package_confirmation="tx-old",
    )
    assert result.status == "PURGED"
    assert result.committed is True
    assert not package.exists()
    manifest = Path(result.manifest or "")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["status"] == "PURGED"
    assert payload["reason"] == "koniec retencji"
    assert payload["package_id"] == "tx-old"
    assert payload["recovery_archive_removed"] is True
    assert list((tmp_path / "staging").glob("*.recovery.tar")) == []


def test_archive_failure_restores_atomically_staged_package(
    monkeypatch, tmp_path: Path
) -> None:
    package = make_package(tmp_path / "quarantine")
    tx = transaction(tmp_path)
    plan = tx.plan("example.invalid", package, reason="test")
    monkeypatch.setattr(
        tx, "_create_recovery_archive",
        lambda source, target: (_ for _ in ()).throw(OSError("archive failure")),
    )
    result = tx.apply(
        plan, commit=True, confirmation="example.invalid",
        package_confirmation="tx-old",
    )
    assert result.status == "PURGE-FAILED"
    assert result.rolled_back is True
    assert package.is_dir()


def test_delete_failure_preserves_verified_recovery_archive(
    monkeypatch, tmp_path: Path
) -> None:
    package = make_package(tmp_path / "quarantine")
    tx = transaction(tmp_path)
    plan = tx.plan("example.invalid", package, reason="test")
    monkeypatch.setattr(
        tx, "_remove_staged_package",
        lambda target: (_ for _ in ()).throw(OSError("delete failure")),
    )
    result = tx.apply(
        plan, commit=True, confirmation="example.invalid",
        package_confirmation="tx-old",
    )
    assert result.status == "PURGE-FAILED"
    payload = json.loads(Path(result.manifest or "").read_text(encoding="utf-8"))
    recovery = Path(payload["recovery_archive"])
    assert payload["recovery_available"] is True
    assert recovery.is_file()
    assert hashlib.sha256(recovery.read_bytes()).hexdigest() == payload["recovery_sha256"]


def test_initial_audit_failure_leaves_package_untouched(
    monkeypatch, tmp_path: Path
) -> None:
    package = make_package(tmp_path / "quarantine")
    tx = transaction(tmp_path)
    plan = tx.plan("example.invalid", package, reason="test")
    monkeypatch.setattr(
        tx, "_write_manifest",
        lambda path, payload: (_ for _ in ()).throw(OSError("audit failure")),
    )
    result = tx.apply(
        plan, commit=True, confirmation="example.invalid",
        package_confirmation="tx-old",
    )
    assert result.status == "PURGE-FAILED"
    assert package.is_dir()
    assert list((tmp_path / "staging").glob("*")) == []


def test_commit_audit_failure_keeps_recovery_after_source_removal(
    monkeypatch, tmp_path: Path
) -> None:
    package = make_package(tmp_path / "quarantine")
    tx = transaction(tmp_path)
    plan = tx.plan("example.invalid", package, reason="test")
    original = tx._write_manifest
    calls = 0

    def fail_fourth(path, payload):
        nonlocal calls
        calls += 1
        if calls == 4:
            raise OSError("commit audit failure")
        return original(path, payload)

    monkeypatch.setattr(tx, "_write_manifest", fail_fourth)
    result = tx.apply(
        plan, commit=True, confirmation="example.invalid",
        package_confirmation="tx-old",
    )
    assert result.status == "PURGE-FAILED"
    assert not package.exists()
    payload = json.loads(Path(result.manifest or "").read_text(encoding="utf-8"))
    assert payload["status"] == "PURGE-FAILED"
    assert Path(payload["recovery_archive"]).is_file()


def test_cli_purge_is_dry_run_by_default(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    package = make_package(tmp_path / "quarantine")

    code = cli.main(
        [
            "zone", "quarantine-purge", "example.invalid",
            "--package", str(package),
            "--quarantine-root", str(tmp_path / "quarantine"),
            "--audit-directory", str(tmp_path / "audit"),
            "--staging-root", str(tmp_path / "staging"),
            "--retention-days", "1",
            "--reason", "test CLI",
        ]
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "Status:     DRY-RUN" in output
    assert "Commit:     NIE" in output
    assert package.is_dir()
