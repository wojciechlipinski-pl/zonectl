from __future__ import annotations

import json
from pathlib import Path

from zonectl.core.zone_inventory import ZoneInventory


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_inventory_lists_disabled_zone_with_manifest_metadata(
    tmp_path: Path,
) -> None:
    disabled = tmp_path / "disabled/example.invalid"
    disabled.mkdir(parents=True)
    declaration = disabled / "example.invalid.conf"
    declaration.write_text("zone declaration\n", encoding="utf-8")
    manifests = tmp_path / "manifests"
    write_json(
        manifests / "disable.json",
        {
            "transaction_id": "tx-disable",
            "zone": "example.invalid",
            "status": "DISABLED",
            "reason": "koniec obsługi",
            "operator": "wojtek",
            "saved_at": "2026-07-31T12:00:00+02:00",
        },
    )

    records = ZoneInventory(
        disabled_root=tmp_path / "disabled",
        quarantine_root=tmp_path / "quarantine",
        disable_manifest_directory=manifests,
    ).records()

    assert len(records) == 1
    assert records[0].state == "DISABLED"
    assert records[0].zone == "example.invalid"
    assert records[0].operator == "wojtek"
    assert records[0].reason == "koniec obsługi"
    assert records[0].location == str(declaration)


def test_inventory_lists_every_quarantine_package(tmp_path: Path) -> None:
    root = tmp_path / "quarantine/example.invalid"
    for number, timestamp in (("tx-1", "2026-07-31T10:00:00+02:00"),
                              ("tx-2", "2026-07-31T11:00:00+02:00")):
        write_json(
            root / number / "manifest.json",
            {
                "transaction_id": number,
                "zone": "example.invalid",
                "status": "QUARANTINED",
                "reason": "retencja",
                "operator": "root",
                "created_at": timestamp,
            },
        )

    records = ZoneInventory(
        disabled_root=tmp_path / "disabled",
        quarantine_root=tmp_path / "quarantine",
        disable_manifest_directory=tmp_path / "manifests",
    ).records()

    assert [record.transaction_id for record in records] == ["tx-2", "tx-1"]
    assert all(record.state == "QUARANTINED" for record in records)


def test_inventory_ignores_invalid_manifests_and_incomplete_disabled_entries(
    tmp_path: Path,
) -> None:
    (tmp_path / "disabled/incomplete").mkdir(parents=True)
    bad = tmp_path / "quarantine/example.invalid/tx/manifest.json"
    bad.parent.mkdir(parents=True)
    bad.write_text("not json", encoding="utf-8")

    records = ZoneInventory(
        disabled_root=tmp_path / "disabled",
        quarantine_root=tmp_path / "quarantine",
        disable_manifest_directory=tmp_path / "manifests",
    ).records()

    assert records == []
