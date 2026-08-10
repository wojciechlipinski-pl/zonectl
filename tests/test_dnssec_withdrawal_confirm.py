from __future__ import annotations

import json
import subprocess
from pathlib import Path

from zonectl.core.dnssec_withdrawal_check import DnssecWithdrawalCheckResult
from zonectl.core.dnssec_withdrawal_confirm import (
    DnssecWithdrawalConfirmTransaction,
)


def checker(status: str):
    def _collect(zone: str, resolvers):
        return DnssecWithdrawalCheckResult(
            zone=zone,
            status=status,
            next_action=f"stub next action for {status}",
        )

    return _collect


def ok_rndc_runner(zone: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        ["rndc"], 0, stdout="checkds: withdrawn\n", stderr=""
    )


def failing_rndc_runner(zone: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        ["rndc"], 1, stdout="", stderr="checkds: not ready"
    )


def test_dry_run_never_touches_rndc_even_when_ready(tmp_path: Path) -> None:
    calls: list[str] = []

    def spy_rndc(zone: str) -> subprocess.CompletedProcess[str]:
        calls.append(zone)
        return ok_rndc_runner(zone)

    tx = DnssecWithdrawalConfirmTransaction(
        tmp_path / "manifests",
        checker=checker("READY_FOR_WITHDRAWN"),
        rndc_runner=spy_rndc,
    )

    result = tx.apply("example.pl", ("1.1.1.1",))

    assert result.status == "DRY-RUN"
    assert result.committed is False
    assert not calls
    assert not (tmp_path / "manifests").exists()


def test_commit_without_acknowledge_is_blocked(tmp_path: Path) -> None:
    tx = DnssecWithdrawalConfirmTransaction(
        tmp_path / "manifests",
        checker=checker("READY_FOR_WITHDRAWN"),
        rndc_runner=ok_rndc_runner,
    )

    result = tx.apply("example.pl", ("1.1.1.1",), commit=True)

    assert result.status == "BLOCKED"
    assert result.committed is False
    assert not (tmp_path / "manifests").exists()


def test_commit_blocked_when_fresh_check_is_not_ready(tmp_path: Path) -> None:
    calls: list[str] = []

    def spy_rndc(zone: str) -> subprocess.CompletedProcess[str]:
        calls.append(zone)
        return ok_rndc_runner(zone)

    tx = DnssecWithdrawalConfirmTransaction(
        tmp_path / "manifests",
        checker=checker("BLOCKED"),
        rndc_runner=spy_rndc,
    )

    result = tx.apply(
        "example.pl", ("1.1.1.1",), commit=True, acknowledge_withdrawn=True
    )

    assert result.status == "BLOCKED"
    assert result.committed is False
    assert not calls, "rndc must never run when the fresh check is not ready"
    assert not (tmp_path / "manifests").exists()


def test_successful_withdrawal_writes_manifest(tmp_path: Path) -> None:
    tx = DnssecWithdrawalConfirmTransaction(
        tmp_path / "manifests",
        checker=checker("READY_FOR_WITHDRAWN"),
        rndc_runner=ok_rndc_runner,
    )

    result = tx.apply(
        "example.pl", ("1.1.1.1",), commit=True, acknowledge_withdrawn=True
    )

    assert result.status == "WITHDRAWN"
    assert result.committed is True
    manifest = Path(result.manifest)
    assert manifest.is_file()
    payload = json.loads(manifest.read_text())
    assert payload["zone"] == "example.pl"
    assert payload["ds_check"]["status"] == "READY_FOR_WITHDRAWN"


def test_rndc_failure_is_reported_and_no_manifest_written(tmp_path: Path) -> None:
    tx = DnssecWithdrawalConfirmTransaction(
        tmp_path / "manifests",
        checker=checker("READY_FOR_WITHDRAWN"),
        rndc_runner=failing_rndc_runner,
    )

    result = tx.apply(
        "example.pl", ("1.1.1.1",), commit=True, acknowledge_withdrawn=True
    )

    assert result.status == "FAILED"
    assert result.committed is False
    assert not (tmp_path / "manifests").exists()
