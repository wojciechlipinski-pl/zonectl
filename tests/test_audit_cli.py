import json
from pathlib import Path

from zonectl import cli
from zonectl.core.audit_store import (
    AuditRecord,
    AuditResource,
    AuditRollback,
    AuditStore,
    Outcome,
    RecordKind,
    ResourceKind,
)


def _record(
    *,
    record_id: str,
    transaction_id: str,
    recorded_at: str,
    kind: RecordKind,
    outcome: Outcome,
    zone: str = "alpha.example.test",
    operation: str = "zone.disable",
) -> AuditRecord:
    return AuditRecord(
        record_id=record_id,
        transaction_id=transaction_id,
        recorded_at=recorded_at,
        record_kind=kind,
        operation=operation,
        resource=AuditResource(ResourceKind.ZONE, zone),
        outcome=outcome,
        committed=outcome is Outcome.COMMITTED,
        rollback=AuditRollback(),
    )


def _registry(tmp_path: Path) -> Path:
    path = tmp_path / "audit-v1.jsonl"
    store = AuditStore(path)
    store.append(
        _record(
            record_id="11111111-1111-4111-8111-111111111111",
            transaction_id="20260901-100000-alpha-00000001",
            recorded_at="2026-09-01T10:00:00Z",
            kind=RecordKind.START,
            outcome=Outcome.STARTED,
        )
    )
    store.append(
        _record(
            record_id="22222222-2222-4222-8222-222222222222",
            transaction_id="20260901-100000-alpha-00000001",
            recorded_at="2026-09-01T10:00:02Z",
            kind=RecordKind.RESULT,
            outcome=Outcome.COMMITTED,
        )
    )
    store.append(
        _record(
            record_id="33333333-3333-4333-8333-333333333333",
            transaction_id="20260901-110000-beta-00000002",
            recorded_at="2026-09-01T11:00:00Z",
            kind=RecordKind.RESULT,
            outcome=Outcome.BLOCKED,
            zone="beta.example.test",
            operation="dnssec.enable",
        )
    )
    return path


def test_audit_list_filters_without_loading_bind_config(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    path = _registry(tmp_path)
    monkeypatch.setattr(
        cli.ToolkitConfig,
        "load",
        lambda self: (_ for _ in ()).throw(AssertionError("config read")),
    )

    code = cli.main(
        [
            "audit",
            "list",
            "--audit-log",
            str(path),
            "--zone",
            "alpha.example.test.",
            "--status",
            "COMMITTED",
            "--since",
            "2026-09-01T09:00:00Z",
            "--until",
            "2026-09-01T10:30:00+00:00",
        ]
    )

    assert code == 0
    output = capsys.readouterr().out
    assert "alpha.example.test" in output
    assert "COMMITTED" in output
    assert "beta.example.test" not in output
    assert "STARTED" not in output


def test_audit_show_json_returns_start_and_result(tmp_path: Path, capsys) -> None:
    path = _registry(tmp_path)
    code = cli.main(
        [
            "audit",
            "show",
            "20260901-100000-alpha-00000001",
            "--audit-log",
            str(path),
            "--json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "zonectl.audit-query/v1"
    assert {record["record_kind"] for record in payload["records"]} == {
        "START",
        "RESULT",
    }


def test_audit_export_json_applies_operation_filter(tmp_path: Path, capsys) -> None:
    path = _registry(tmp_path)
    code = cli.main(
        [
            "audit",
            "export",
            "--audit-log",
            str(path),
            "--operation",
            "dnssec.enable",
            "--format",
            "json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["records"]) == 1
    assert payload["records"][0]["resource"]["name"] == "beta.example.test"


def test_audit_export_text_uses_compact_allowlisted_lines(
    tmp_path: Path, capsys
) -> None:
    path = _registry(tmp_path)
    code = cli.main(
        [
            "audit",
            "export",
            "--audit-log",
            str(path),
            "--zone",
            "beta.example.test",
            "--format",
            "text",
        ]
    )

    assert code == 0
    output = capsys.readouterr().out
    assert "beta.example.test" in output
    assert "BLOCKED" in output
    assert "dnssec.enable" in output
    assert "record_id" not in output


def test_audit_cli_reports_corruption_without_exposing_payload(
    tmp_path: Path, capsys
) -> None:
    path = _registry(tmp_path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"secret":"do-not-print"\n')

    code = cli.main(["audit", "list", "--audit-log", str(path)])

    assert code == 0
    captured = capsys.readouterr()
    assert "UWAGA: wiersz 4" in captured.err
    assert "do-not-print" not in captured.err


def test_audit_cli_rejects_naive_time_and_invalid_limit(tmp_path: Path, capsys) -> None:
    path = _registry(tmp_path)
    assert (
        cli.main(
            [
                "audit",
                "list",
                "--audit-log",
                str(path),
                "--since",
                "2026-09-01T10:00:00",
            ]
        )
        == 2
    )
    assert "explicit timezone" in capsys.readouterr().err
    assert cli.main(["audit", "list", "--audit-log", str(path), "--limit", "0"]) == 2
