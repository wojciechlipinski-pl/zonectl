from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from zonectl.core.bulk_operations import BulkOperation
from zonectl.core.models import Zone
from zonectl.core.transaction import StepResult, TransactionResult
from zonectl.core.zone_edit_session import ZoneEditSession


@dataclass
class RecordingEngine:
    target: Path
    calls: list[dict[str, object]] = field(default_factory=list)

    def apply(
        self,
        zone_name: str,
        source: Path,
        commit: bool = False,
        metadata: dict[str, object] | None = None,
    ) -> TransactionResult:
        self.calls.append(
            {
                "zone": zone_name,
                "commit": commit,
                "metadata": metadata,
            }
        )
        if commit:
            self.target.write_bytes(source.read_bytes())
        return TransactionResult(
            transaction_id="bulk-transaction",
            zone=zone_name,
            committed=commit,
            status="COMMIT" if commit else "DRY-RUN",
            steps=[StepResult("transaction", True, "OK")],
            metadata=dict(metadata or {}),
        )


def test_bulk_save_is_one_transaction_with_manifest_metadata(
    tmp_path: Path,
) -> None:
    source = tmp_path / "example.pl"
    source.write_text(
        "$TTL 3600\n"
        "www 300 IN A 192.0.2.10\n"
        "api 300 IN A 192.0.2.20\n",
        encoding="utf-8",
    )
    engine = RecordingEngine(source)
    session = ZoneEditSession(
        Zone(name="example.pl", file=source),
        engine,
        auto_bump_serial=False,
    )

    operation = BulkOperation.parse(
        "SELECT type:A SET ttl=7200"
    )
    assert operation.apply(session.model) == 2

    result = session.save(commit=True)

    assert len(engine.calls) == 1
    assert result.transaction.transaction_id == "bulk-transaction"
    metadata = result.transaction.metadata
    assert metadata["change_count"] == 2
    assert metadata["bulk_operation_count"] == 1
    assert metadata["bulk_operations"] == [
        {
            "query": "type:A",
            "action": "SET",
            "field": "ttl",
            "value": "7200",
            "matched_count": 2,
        }
    ]
    assert "www\t7200\tIN\tA\t192.0.2.10" in source.read_text(
        encoding="utf-8"
    )
    assert "api\t7200\tIN\tA\t192.0.2.20" in source.read_text(
        encoding="utf-8"
    )
