from __future__ import annotations

import json
from pathlib import Path

import pytest

from zonectl.core.dnssec_confirm_ds import (
    DnssecConfirmDsTransaction,
    DnssecConfirmStep,
)
from zonectl.core.dnssec_ds_check import DnssecDsCheck
from zonectl.core.runner import CommandResult


def check(status: str) -> DnssecDsCheck:
    return DnssecDsCheck(
        zone="example.pl",
        status=status,
        kasp_ready=status == "PASS",
        expected_ds=("12345 13 2 ABCD",),
        resolver_checks=(),
        authority_checks=(),
        next_action="next",
        errors=(),
    )


@pytest.mark.parametrize(
    "status",
    ["NOT_READY", "NOT_PUBLISHED", "PROPAGATING", "INDETERMINATE", "FAIL"],
)
def test_every_non_pass_check_is_blocked(tmp_path: Path, status: str) -> None:
    calls = []
    transaction = DnssecConfirmDsTransaction(
        tmp_path,
        checker=lambda zone, resolvers: check(status),
        confirmer=lambda zone: calls.append(zone),
    )

    result = transaction.apply(
        "example.pl", ("r1",), commit=True, acknowledge_published=True
    )

    assert result.status == "BLOCKED"
    assert result.committed is False
    assert result.manifest is None
    assert calls == []


def test_pass_defaults_to_side_effect_free_dry_run(tmp_path: Path) -> None:
    calls = []
    transaction = DnssecConfirmDsTransaction(
        tmp_path,
        checker=lambda zone, resolvers: check("PASS"),
        confirmer=lambda zone: calls.append(zone),
    )

    result = transaction.apply("example.pl", ("r1",))

    assert result.status == "DRY-RUN"
    assert calls == []
    assert list(tmp_path.iterdir()) == []


def test_commit_requires_matching_confirmation_flags(tmp_path: Path) -> None:
    transaction = DnssecConfirmDsTransaction(
        tmp_path, checker=lambda zone, resolvers: check("PASS")
    )

    result = transaction.apply("example.pl", ("r1",), commit=True)

    assert result.status == "CONFIRMATION-REQUIRED"
    assert result.committed is False


def test_success_confirms_kasp_and_writes_manifest(tmp_path: Path) -> None:
    calls = []

    def action(name: str):
        return lambda zone: (
            calls.append((name, zone)) or DnssecConfirmStep(name, True, "OK")
        )

    result = DnssecConfirmDsTransaction(
        tmp_path,
        checker=lambda zone, resolvers: check("PASS"),
        confirmer=action("confirm"),
        verifier=action("verify"),
    ).apply("example.pl", ("r1",), commit=True, acknowledge_published=True)

    assert result.status == "CONFIRMED"
    assert result.committed is True
    assert calls == [("confirm", "example.pl"), ("verify", "example.pl")]
    manifest = Path(result.manifest)
    assert manifest.stat().st_mode & 0o777 == 0o640
    assert json.loads(manifest.read_text())["status"] == "CONFIRMED"


def test_failed_verification_never_withdraws_ds(tmp_path: Path) -> None:
    result = DnssecConfirmDsTransaction(
        tmp_path,
        checker=lambda zone, resolvers: check("PASS"),
        confirmer=lambda zone: DnssecConfirmStep("confirm", True, "OK"),
        verifier=lambda zone: DnssecConfirmStep("verify", False, "still hidden"),
    ).apply("example.pl", ("r1",), commit=True, acknowledge_published=True)

    assert result.status == "VERIFY-FAILED"
    assert result.committed is True
    assert "Nie wycofuj DS" in result.steps[-1].message


def test_default_confirmer_uses_published_checkds(monkeypatch) -> None:
    calls = []

    def fake_run(command, timeout):
        calls.append((command, timeout))
        return CommandResult(0, "OK", "")

    monkeypatch.setattr("zonectl.core.dnssec_confirm_ds.run", fake_run)

    step = DnssecConfirmDsTransaction._confirm("example.pl")

    assert step.ok is True
    assert calls == [(["rndc", "dnssec", "-checkds", "published", "example.pl"], 15)]


def test_default_verifier_rejects_hidden_ds(monkeypatch) -> None:
    monkeypatch.setattr(
        "zonectl.core.dnssec_confirm_ds.run",
        lambda command, timeout: CommandResult(0, "- ds: hidden\n", ""),
    )

    step = DnssecConfirmDsTransaction._verify("example.pl")

    assert step.ok is False
