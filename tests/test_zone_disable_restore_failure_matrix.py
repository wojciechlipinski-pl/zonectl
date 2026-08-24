from __future__ import annotations

import os
from pathlib import Path

import pytest

from zonectl.core.zone_disable_transaction import (
    ZoneDisableStep,
    ZoneDisableTransaction,
)
from zonectl.core.zone_restore_transaction import (
    ZoneRestoreStep,
    ZoneRestoreTransaction,
)
from tests.test_zone_disable_transaction import setup as disable_setup
from tests.test_zone_restore_transaction import setup as restore_setup


def _metadata(path: Path) -> tuple[int, int, int]:
    stat = path.stat()
    return stat.st_uid, stat.st_gid, stat.st_mode & 0o777


def _disable_engine(
    tmp_path: Path,
    *,
    validator=None,
    activator=None,
    verifier=None,
) -> ZoneDisableTransaction:
    return ZoneDisableTransaction(
        tmp_path / "manifests",
        config_validator=validator
        or (lambda _path: ZoneDisableStep("named-checkconf", True, "OK")),
        activator=activator
        or (lambda _name: ZoneDisableStep("rndc-reconfig", True, "OK")),
        unavailable_verifier=verifier
        or (lambda _name: ZoneDisableStep("unavailable", True, "OK")),
    )


def _restore_engine(
    tmp_path: Path,
    *,
    zone_validator=None,
    config_validator=None,
    activator=None,
    loaded=None,
) -> ZoneRestoreTransaction:
    return ZoneRestoreTransaction(
        tmp_path / "manifests",
        zone_validator=zone_validator
        or (lambda _name, _path: ZoneRestoreStep("named-checkzone", True, "OK")),
        config_validator=config_validator
        or (lambda _path: ZoneRestoreStep("named-checkconf", True, "OK")),
        activator=activator
        or (lambda _name: ZoneRestoreStep("rndc-reconfig", True, "OK")),
        loaded_verifier=loaded
        or (lambda _name: ZoneRestoreStep("loaded", True, "OK")),
    )


@pytest.mark.parametrize("failed_replace", (1, 2))
def test_disable_write_failures_restore_active_state(
    tmp_path: Path,
    monkeypatch,
    failed_replace: int,
) -> None:
    _zone, declaration, index, plan = disable_setup(tmp_path)
    original_declaration = declaration.read_bytes()
    original_index = index.read_bytes()
    real_replace = os.replace
    calls = 0

    def fail_once(source, destination):
        nonlocal calls
        calls += 1
        if calls == failed_replace:
            raise OSError(f"forced replace failure {failed_replace}")
        return real_replace(source, destination)

    monkeypatch.setattr(os, "replace", fail_once)
    result = _disable_engine(tmp_path).apply(plan, commit=True)

    assert result.status == "ROLLED-BACK"
    assert declaration.read_bytes() == original_declaration
    assert index.read_bytes() == original_index
    assert not plan.archived_declaration.exists()


def test_disable_preserves_declaration_and_index_metadata(tmp_path: Path) -> None:
    _zone, declaration, index, plan = disable_setup(tmp_path)
    declaration.chmod(0o600)
    index.chmod(0o644)
    declaration_metadata = _metadata(declaration)
    index_metadata = _metadata(index)

    result = _disable_engine(tmp_path).apply(plan, commit=True)

    assert result.status == "DISABLED"
    assert _metadata(plan.archived_declaration) == declaration_metadata
    assert _metadata(index) == index_metadata


def test_disable_activation_failure_rolls_back_and_reconfigures(tmp_path: Path) -> None:
    _zone, declaration, index, plan = disable_setup(tmp_path)
    original_index = index.read_bytes()
    calls = 0

    def activate(_name: str) -> ZoneDisableStep:
        nonlocal calls
        calls += 1
        return ZoneDisableStep("rndc-reconfig", calls == 2, f"call {calls}")

    result = _disable_engine(tmp_path, activator=activate).apply(plan, commit=True)

    assert result.status == "ROLLED-BACK"
    assert calls == 2
    assert declaration.exists()
    assert index.read_bytes() == original_index


def test_disable_failed_rollback_is_reported(tmp_path: Path) -> None:
    _zone, declaration, _index, plan = disable_setup(tmp_path)

    def activate(_name: str) -> ZoneDisableStep:
        return ZoneDisableStep("rndc-reconfig", False, "BIND unavailable")

    result = _disable_engine(tmp_path, activator=activate).apply(plan, commit=True)

    assert result.status == "ROLLBACK-FAILED"
    assert result.rolled_back is False
    assert declaration.exists()
    assert any(step.name == "rollback" and not step.ok for step in result.steps)


@pytest.mark.parametrize("failed_replace", (1, 2))
def test_restore_write_failures_keep_disabled_state(
    tmp_path: Path,
    monkeypatch,
    failed_replace: int,
) -> None:
    _zone, declaration, archived, index, plan = restore_setup(tmp_path)
    original_index = index.read_bytes()
    real_replace = os.replace
    calls = 0

    def fail_once(source, destination):
        nonlocal calls
        calls += 1
        if calls == failed_replace:
            raise OSError(f"forced replace failure {failed_replace}")
        return real_replace(source, destination)

    monkeypatch.setattr(os, "replace", fail_once)
    result = _restore_engine(tmp_path).apply(plan, commit=True)

    assert result.status == "ROLLED-BACK"
    assert archived.exists()
    assert not declaration.exists()
    assert index.read_bytes() == original_index


def test_restore_preserves_archive_and_index_metadata(tmp_path: Path) -> None:
    _zone, declaration, archived, index, plan = restore_setup(tmp_path)
    archived.chmod(0o600)
    index.chmod(0o644)
    declaration_metadata = _metadata(archived)
    index_metadata = _metadata(index)

    result = _restore_engine(tmp_path).apply(plan, commit=True)

    assert result.status == "RESTORED"
    assert _metadata(declaration) == declaration_metadata
    assert _metadata(index) == index_metadata


def test_restore_config_failure_returns_to_disabled_state(tmp_path: Path) -> None:
    _zone, declaration, archived, index, plan = restore_setup(tmp_path)
    original_index = index.read_bytes()
    result = _restore_engine(
        tmp_path,
        config_validator=lambda _path: ZoneRestoreStep(
            "named-checkconf", False, "invalid config"
        ),
    ).apply(plan, commit=True)

    assert result.status == "ROLLED-BACK"
    assert archived.exists()
    assert not declaration.exists()
    assert index.read_bytes() == original_index


def test_restore_failed_rollback_is_reported(tmp_path: Path) -> None:
    _zone, declaration, archived, _index, plan = restore_setup(tmp_path)

    def activate(_name: str) -> ZoneRestoreStep:
        return ZoneRestoreStep("rndc-reconfig", False, "BIND unavailable")

    result = _restore_engine(tmp_path, activator=activate).apply(plan, commit=True)

    assert result.status == "ROLLBACK-FAILED"
    assert result.rolled_back is False
    assert archived.exists()
    assert not declaration.exists()
    assert any(step.name == "rollback" and not step.ok for step in result.steps)
