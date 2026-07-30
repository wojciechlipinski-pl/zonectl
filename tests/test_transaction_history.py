from __future__ import annotations

import json
from pathlib import Path

import pytest

from zonectl.core.models import Zone
from zonectl.core.transaction import TransactionEngine


class FakeConfig:
    def __init__(self, root: Path):
        self.toolkit = {
            "state_dir": str(root / "state"),
            "transaction_dir": str(root / "transactions"),
            "transaction_backup_dir": str(root / "backups"),
            "lock_dir": str(root / "locks"),
            "audit_log": str(root / "audit.jsonl"),
        }

    def zones(self) -> list[Zone]:
        return []


def write_manifest(
    directory: Path,
    transaction_id: str,
    zone: str,
    outcome: str,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{transaction_id}.json"
    path.write_text(
        json.dumps(
            {
                "transaction_id": transaction_id,
                "zone": zone,
                "committed": outcome == "COMMIT",
                "status": outcome,
                "outcome": outcome,
                "rolled_back": outcome == "ROLLED-BACK",
                "backup": None,
                "steps": [
                    {
                        "name": "named-checkzone",
                        "ok": outcome != "FAIL",
                        "message": "OK" if outcome != "FAIL" else "kod 1",
                        "command": ["named-checkzone", zone, "candidate"],
                        "stdout": "",
                        "stderr": "",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_history_filters_zone_and_skips_broken_manifest(
    tmp_path: Path,
) -> None:
    engine = TransactionEngine(FakeConfig(tmp_path))
    directory = engine.transaction_dir
    write_manifest(directory, "tx-1", "example.pl", "COMMIT")
    write_manifest(directory, "tx-2", "other.pl", "FAIL")
    (directory / "broken.json").write_text("{", encoding="utf-8")

    records = engine.history("example.pl")

    assert len(records) == 1
    assert records[0]["transaction_id"] == "tx-1"
    assert records[0]["outcome"] == "COMMIT"
    assert records[0]["saved_at"]


def test_load_transaction_restores_result_and_steps(
    tmp_path: Path,
) -> None:
    engine = TransactionEngine(FakeConfig(tmp_path))
    write_manifest(
        engine.transaction_dir,
        "tx-show",
        "example.pl",
        "COMMIT",
    )

    result = engine.load_transaction("tx-show")

    assert result.transaction_id == "tx-show"
    assert result.zone == "example.pl"
    assert result.status == "COMMIT"
    assert result.committed is True
    assert result.steps[0].name == "named-checkzone"
    assert result.steps[0].ok is True


@pytest.mark.parametrize(
    "transaction_id",
    ["", ".", "..", "../audit", "nested/id", r"..\audit"],
)
def test_load_transaction_rejects_unsafe_identifier(
    tmp_path: Path,
    transaction_id: str,
) -> None:
    engine = TransactionEngine(FakeConfig(tmp_path))

    with pytest.raises(
        RuntimeError,
        match="Nieprawidłowy identyfikator",
    ):
        engine.load_transaction(transaction_id)


def test_load_transaction_reports_missing_manifest(
    tmp_path: Path,
) -> None:
    engine = TransactionEngine(FakeConfig(tmp_path))

    with pytest.raises(
        RuntimeError,
        match="Nie znaleziono transakcji",
    ):
        engine.load_transaction("missing")
