from __future__ import annotations

import os
from pathlib import Path

import pytest

from zonectl.core.zone_create_transaction import (
    ZoneCreateStep,
    ZoneCreateTransaction,
)
from tests.test_zone_create_transaction import (
    plan,
    valid_config,
    valid_zone,
)


def _engine(
    tmp_path: Path,
    *,
    activate=None,
    verify=None,
) -> ZoneCreateTransaction:
    return ZoneCreateTransaction(
        tmp_path / "manifests",
        zone_validator=valid_zone,
        config_validator=valid_config,
        activator=activate,
        loaded_verifier=verify,
    )


@pytest.mark.parametrize("failed_replace", (1, 2, 3, 4))
def test_each_atomic_write_failure_restores_pre_transaction_state(
    tmp_path: Path,
    monkeypatch,
    failed_replace: int,
) -> None:
    candidate = plan(tmp_path)
    candidate.managed_config.parent.mkdir(parents=True)
    candidate.managed_config.write_text("// original\n", encoding="utf-8")
    candidate.groups_config.parent.mkdir(parents=True)
    candidate.groups_config.write_text(
        "groups:\n  Klienci:\n",
        encoding="utf-8",
    )
    original_config = candidate.managed_config.read_bytes()
    original_groups = candidate.groups_config.read_bytes()
    real_replace = os.replace
    calls = 0

    def fail_once(source, destination):
        nonlocal calls
        calls += 1
        if calls == failed_replace:
            raise OSError(f"forced replace failure {failed_replace}")
        return real_replace(source, destination)

    monkeypatch.setattr(os, "replace", fail_once)
    result = _engine(tmp_path).apply(candidate, commit=True)

    assert result.status == "ROLLED-BACK"
    assert result.rolled_back is True
    assert not candidate.zone_file.exists()
    assert not candidate.zone_declaration_file.exists()
    assert candidate.managed_config.read_bytes() == original_config
    assert candidate.groups_config.read_bytes() == original_groups


def test_existing_configuration_metadata_survives_commit(
    tmp_path: Path,
) -> None:
    candidate = plan(tmp_path)
    candidate.managed_config.parent.mkdir(parents=True)
    candidate.managed_config.write_text("// original\n", encoding="utf-8")
    candidate.groups_config.parent.mkdir(parents=True)
    candidate.groups_config.write_text(
        "groups:\n  Klienci:\n",
        encoding="utf-8",
    )
    candidate.managed_config.chmod(0o644)
    candidate.groups_config.chmod(0o600)
    before = {
        path: (path.stat().st_uid, path.stat().st_gid, path.stat().st_mode & 0o777)
        for path in (candidate.managed_config, candidate.groups_config)
    }

    result = _engine(tmp_path).apply(candidate, commit=True)

    assert result.status == "COMMIT"
    for path, metadata in before.items():
        assert (
            path.stat().st_uid,
            path.stat().st_gid,
            path.stat().st_mode & 0o777,
        ) == metadata


def test_activation_failure_rolls_back_and_reconfigures(
    tmp_path: Path,
) -> None:
    calls = 0

    def activate(_name: str) -> ZoneCreateStep:
        nonlocal calls
        calls += 1
        return ZoneCreateStep(
            "rndc-reconfig",
            calls == 2,
            "restored" if calls == 2 else "activation failed",
        )

    candidate = plan(tmp_path)
    result = _engine(
        tmp_path,
        activate=activate,
        verify=lambda _name: ZoneCreateStep("verify", True, "OK"),
    ).apply(candidate, commit=True, activate=True)

    assert result.status == "ROLLED-BACK"
    assert result.rolled_back is True
    assert calls == 2
    assert not candidate.zone_file.exists()
    assert not candidate.zone_declaration_file.exists()


def test_failed_rollback_reconfiguration_is_reported_not_raised(
    tmp_path: Path,
) -> None:
    def activate(_name: str) -> ZoneCreateStep:
        return ZoneCreateStep("rndc-reconfig", False, "BIND unavailable")

    candidate = plan(tmp_path)
    result = _engine(
        tmp_path,
        activate=activate,
        verify=lambda _name: ZoneCreateStep("verify", True, "OK"),
    ).apply(candidate, commit=True, activate=True)

    assert result.status == "ROLLBACK-FAILED"
    assert result.rolled_back is False
    assert any(step.name == "rollback" and not step.ok for step in result.steps)
    assert not candidate.zone_file.exists()
    assert not candidate.zone_declaration_file.exists()
