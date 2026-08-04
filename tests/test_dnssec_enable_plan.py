from __future__ import annotations

from pathlib import Path

import pytest

from zonectl.core.discovery import ZoneConfig
from zonectl.core.dnssec_enable_plan import (
    DnssecEnablePlanError,
    DnssecEnablePlanner,
)


def zone_config(tmp_path: Path, *, zone_type: str = "primary") -> ZoneConfig:
    zone_file = tmp_path / "example.pl"
    zone_file.write_text("zone data\n", encoding="utf-8")
    declaration = tmp_path / "zones.conf"
    declaration.write_text(
        'zone "other.pl" { type primary; file "/zones/other.pl"; };\n'
        'zone "example.pl" IN {\n'
        f"    type {zone_type};\n"
        f'    file "{zone_file}";\n'
        "    \n"
        "    notify yes;\n"
        "};\n",
        encoding="utf-8",
    )
    return ZoneConfig(
        name="example.pl",
        zone_type=zone_type,
        source_file=zone_file,
        config_file=declaration,
        source_exists=True,
        source_writable=True,
    )


def test_plan_has_no_side_effects_and_changes_only_target(tmp_path: Path) -> None:
    zone = zone_config(tmp_path)
    before = zone.config_file.read_bytes()

    plan = DnssecEnablePlanner().plan(zone)

    assert zone.config_file.read_bytes() == before
    assert 'zone "other.pl" { type primary;' in plan.candidate_text
    assert "dnssec-policy default;" in plan.candidate_text
    assert "inline-signing yes;" in plan.candidate_text
    assert 'key-directory "/var/lib/bind/keys";' in plan.candidate_text
    assert plan.unified_diff.startswith("--- ")
    assert plan.source_zone_file == zone.source_file
    assert plan.target_zone_file == Path("/var/lib/bind/Primary/example.pl")
    assert plan.migration_required is True
    assert 'file "/var/lib/bind/Primary/example.pl";' in plan.candidate_text
    assert "-    notify yes;" not in plan.unified_diff
    assert "+    notify yes;" not in plan.unified_diff


def test_plan_rejects_secondary_zone(tmp_path: Path) -> None:
    with pytest.raises(DnssecEnablePlanError, match="primary"):
        DnssecEnablePlanner().plan(zone_config(tmp_path, zone_type="secondary"))


def test_plan_rejects_existing_dnssec(tmp_path: Path) -> None:
    zone = zone_config(tmp_path)
    zone = ZoneConfig(
        name=zone.name,
        zone_type=zone.zone_type,
        source_file=zone.source_file,
        config_file=zone.config_file,
        dnssec_policy="default",
        source_exists=True,
        source_writable=True,
    )
    with pytest.raises(DnssecEnablePlanError, match="już konfigurację DNSSEC"):
        DnssecEnablePlanner().plan(zone)


def test_plan_rejects_relative_key_directory(tmp_path: Path) -> None:
    with pytest.raises(DnssecEnablePlanError, match="absolutną"):
        DnssecEnablePlanner().plan(
            zone_config(tmp_path), key_directory=Path("relative/keys")
        )


def test_plan_does_not_migrate_zone_already_in_target_directory(
    tmp_path: Path,
) -> None:
    zone = zone_config(tmp_path)
    plan = DnssecEnablePlanner().plan(
        zone,
        zone_directory=zone.source_file.parent,
    )

    assert plan.migration_required is False
    assert plan.target_zone_file == zone.source_file


def test_plan_rejects_existing_target_file(tmp_path: Path) -> None:
    zone = zone_config(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    (target / "example.pl").write_text("conflict", encoding="utf-8")

    with pytest.raises(DnssecEnablePlanError, match="już istnieje"):
        DnssecEnablePlanner().plan(zone, zone_directory=target)


def test_diff_keeps_repeated_bind_lines_as_context() -> None:
    repeated = "\n".join(
        f'zone "zone-{number}.example" {{\n    notify yes;\n}};'
        for number in range(150)
    )
    original = repeated + '\nzone "target.example" {\n    notify yes;\n};\n'
    candidate = repeated + (
        '\nzone "target.example" {\n'
        "    notify yes;\n"
        "    dnssec-policy default;\n"
        "};\n"
    )

    diff = DnssecEnablePlanner._unified_diff(
        original,
        candidate,
        fromfile="named.conf.local",
        tofile="named.conf.local (kandydat)",
    )

    assert "-    notify yes;" not in diff
    assert "+    notify yes;" not in diff
    assert "+    dnssec-policy default;" in diff
