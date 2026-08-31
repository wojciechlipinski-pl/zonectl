from __future__ import annotations

from zonectl.core.transaction import StepResult, TransactionResult
from zonectl.presentation import (
    transaction_exit_code,
    transaction_lines,
    transaction_title,
)


def result_with_step(
    *,
    status: str,
    step: StepResult,
    committed: bool = False,
) -> TransactionResult:
    return TransactionResult(
        transaction_id="tx-test",
        zone="example.pl",
        committed=committed,
        status=status,
        steps=[step],
    )


def test_dry_run_is_presented_as_success() -> None:
    result = result_with_step(
        status="DRY-RUN",
        step=StepResult(
            name="dry-run",
            ok=True,
            message="Nie zmieniono pliku",
        ),
    )

    assert result.ok is True
    assert transaction_exit_code(result) == 0
    assert transaction_title(result) == "Wynik transakcji: DRY-RUN"
    assert "[OK  ] dry-run: Nie zmieniono pliku" in transaction_lines(result)


def test_failed_step_has_consistent_details_and_exit_code() -> None:
    result = result_with_step(
        status="FAIL",
        step=StepResult(
            name="named-checkzone",
            ok=False,
            message="kod 1",
            stdout="loading failed",
            stderr="syntax error",
        ),
    )

    lines = transaction_lines(result)

    assert result.ok is False
    assert transaction_exit_code(result) == 1
    assert "[BŁĄD] named-checkzone: kod 1" in lines
    assert "  stdout: loading failed" in lines
    assert "  stderr: syntax error" in lines


def test_committed_transaction_is_presented_as_success() -> None:
    result = result_with_step(
        status="COMMIT",
        committed=True,
        step=StepResult(
            name="verify-soa",
            ok=True,
            message="serial oczekiwany=2 załadowany=2",
        ),
    )

    assert result.ok is True
    assert transaction_exit_code(result) == 0
    assert "Commit:     TAK" in transaction_lines(result)


def test_bulk_operation_is_presented_from_manifest_metadata() -> None:
    result = result_with_step(
        status="COMMIT",
        committed=True,
        step=StepResult("verify-soa", True, "OK"),
    )
    result.metadata = {
        "bulk_operations": [
            {
                "query": "type:A",
                "action": "SET",
                "field": "ttl",
                "value": "7200",
                "matched_count": 3,
            }
        ]
    }

    lines = transaction_lines(result)

    assert "Operacje masowe:" in lines
    assert "  SELECT type:A SET ttl=7200 (3 rekordów)" in lines
