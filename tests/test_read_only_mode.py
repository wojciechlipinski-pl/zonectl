from __future__ import annotations

from pathlib import Path

import pytest

from zonectl.core.config import ToolkitConfig
from zonectl.core.models import Zone
from zonectl.core.transaction import TransactionEngine
from zonectl.core.zone_model import ZoneModel, ZoneModelReadOnlyError
from zonectl.core.zone_parser import DNSRecord


def record(address: str = "192.0.2.10") -> DNSRecord:
    return DNSRecord(
        owner="www.example.pl.",
        ttl=300,
        rrclass="IN",
        rtype="A",
        rdata=address,
        raw=f"www 300 IN A {address}",
    )


def config_with_read_only(tmp_path: Path, value: str | None) -> ToolkitConfig:
    toolkit = tmp_path / "toolkit.conf"
    setting = "" if value is None else f"read_only = {value}\n"
    toolkit.write_text(
        f"[toolkit]\nauto_discover_zones = no\n{setting}",
        encoding="utf-8",
    )
    zones = tmp_path / "zones.conf"
    zones.write_text("", encoding="utf-8")
    groups = tmp_path / "groups.yaml"
    groups.write_text("", encoding="utf-8")
    return ToolkitConfig(toolkit, zones, groups).load()


def test_read_only_defaults_to_disabled(tmp_path: Path) -> None:
    assert config_with_read_only(tmp_path, None).read_only is False


def test_read_only_accepts_yes(tmp_path: Path) -> None:
    assert config_with_read_only(tmp_path, "yes").read_only is True


@pytest.mark.parametrize("operation", ["add", "replace", "delete"])
def test_read_only_model_rejects_mutations(operation: str) -> None:
    original = record()
    model = ZoneModel("example.pl", [original], read_only=True)

    with pytest.raises(ZoneModelReadOnlyError, match="tylko do odczytu"):
        if operation == "add":
            model.add(record("192.0.2.20"))
        elif operation == "replace":
            model.replace(0, record("192.0.2.20"))
        else:
            model.delete(0)

    assert model.records == (original,)
    assert model.dirty is False


class FakeConfig:
    def __init__(self, root: Path, zone: Zone):
        self.toolkit = {
            "state_dir": str(root / "state"),
            "transaction_backup_dir": str(root / "backups"),
            "transaction_dir": str(root / "transactions"),
            "lock_dir": str(root / "locks"),
            "audit_log": str(root / "audit.jsonl"),
            "read_only": "yes",
        }
        self._zone = zone

    def zones(self) -> list[Zone]:
        return [self._zone]


def test_read_only_engine_blocks_commit_and_rollback(tmp_path: Path) -> None:
    target = tmp_path / "example.pl"
    source = tmp_path / "candidate.db"
    backup = tmp_path / "backup.db"
    target.write_text("active\n", encoding="utf-8")
    source.write_text("candidate\n", encoding="utf-8")
    backup.write_text("backup\n", encoding="utf-8")
    original = target.read_bytes()

    engine = TransactionEngine(
        FakeConfig(tmp_path, Zone(name="example.pl", file=target))
    )

    apply_result = engine.apply("example.pl", source, commit=True)
    rollback_result = engine.rollback("example.pl", backup, commit=True)

    assert apply_result.status == "READ-ONLY"
    assert rollback_result.status == "READ-ONLY"
    assert apply_result.committed is False
    assert rollback_result.committed is False
    assert target.read_bytes() == original
    assert not (tmp_path / "backups").exists()
