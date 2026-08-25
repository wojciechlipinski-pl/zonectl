from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from zonectl import cli
from zonectl.core.zone_quarantine_retention import (
    QuarantineRetentionAuditor,
    format_days_pl,
)


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


class _EmptyConfig:
    def zones(self):
        return []


def package(root: Path, created_at: str, content: bytes = b"zone\n") -> Path:
    directory = root / "example.invalid/tx-1"
    directory.mkdir(parents=True)
    (directory / "zone.db").write_bytes(content)
    manifest = {
        "transaction_id": "tx-1",
        "zone": "example.invalid",
        "status": "QUARANTINED",
        "created_at": created_at,
        "files": {"zone.db": hashlib.sha256(content).hexdigest()},
    }
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory


def audit(root: Path, days: int = 90):
    return QuarantineRetentionAuditor(root, days, now=lambda: NOW).records()[0]


def test_recent_verified_package_is_retained(tmp_path: Path) -> None:
    package(tmp_path, "2026-08-20T12:00:00+00:00")
    record = audit(tmp_path)
    assert record.state == "RETAIN"
    assert record.age_days == 4
    assert "86 dni" in record.reason


def test_old_verified_package_is_only_marked_eligible(tmp_path: Path) -> None:
    directory = package(tmp_path, "2026-05-01T12:00:00+00:00")
    record = audit(tmp_path)
    assert record.state == "ELIGIBLE"
    assert record.package == str(directory)
    assert directory.exists()


def test_checksum_mismatch_blocks_package(tmp_path: Path) -> None:
    directory = package(tmp_path, "2026-05-01T12:00:00+00:00")
    (directory / "zone.db").write_text("changed\n", encoding="utf-8")
    record = audit(tmp_path)
    assert record.state == "BLOCKED"
    assert record.age_days is None
    assert "SHA-256" in record.reason


def test_invalid_manifest_is_visible_and_blocked(tmp_path: Path) -> None:
    manifest = tmp_path / "example.invalid/tx/manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("not json", encoding="utf-8")
    record = audit(tmp_path)
    assert record.state == "BLOCKED"
    assert "manifest" in record.reason


def test_retention_must_be_positive(tmp_path: Path) -> None:
    try:
        QuarantineRetentionAuditor(tmp_path, 0)
    except ValueError as exc:
        assert "co najmniej 1" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_polish_day_label_handles_singular() -> None:
    assert format_days_pl(1) == "1 dzień"
    assert format_days_pl(2) == "2 dni"
    assert format_days_pl(90) == "90 dni"


def test_cli_prints_read_only_retention_plan(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    package(tmp_path, "2026-05-01T12:00:00+00:00")

    code = cli.main(
        [
            "zone",
            "quarantine-retention",
            "--quarantine-root",
            str(tmp_path),
            "--retention-days",
            "1",
        ]
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "TYLKO ODCZYT" in output
    assert "Okres retencji: 1 dzień" in output
    assert "ELIGIBLE" in output
    assert "niczego nie usunięto" in output


def test_cli_rejects_invalid_retention(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    code = cli.main(
        [
            "zone",
            "quarantine-retention",
            "--quarantine-root",
            str(tmp_path),
            "--retention-days",
            "0",
        ]
    )

    captured = capsys.readouterr()
    assert code == 2
    assert "co najmniej 1" in captured.err
