from __future__ import annotations

from pathlib import Path

import pytest

from zonectl.core.discovery import ZoneConfig
from zonectl.core.dnssec_disable_plan import (
    DnssecDisablePlanError,
    DnssecDisablePlanner,
)


def signed_zone(tmp_path: Path, *, zone_type: str = "primary") -> ZoneConfig:
    zone_file = tmp_path / "example.pl"
    zone_file.write_text("zone data\n", encoding="utf-8")
    (tmp_path / "example.pl.signed").write_text("signed\n", encoding="utf-8")
    keys = tmp_path / "keys"
    keys.mkdir()
    (keys / "Kexample.pl.+013+12345.key").write_text("public\n")
    declaration = tmp_path / "zones.conf"
    declaration.write_text(
        'zone "other.pl" { type primary; file "/zones/other.pl"; };\n'
        'zone "example.pl" {\n'
        f"    type {zone_type};\n"
        f'    file "{zone_file}";\n'
        "    notify yes;\n"
        "    dnssec-policy default;\n"
        "    inline-signing yes;\n"
        f'    key-directory "{keys}";\n'
        "};\n",
        encoding="utf-8",
    )
    return ZoneConfig(
        name="example.pl",
        zone_type=zone_type,
        source_file=zone_file,
        config_file=declaration,
        dnssec_policy="default",
        inline_signing=True,
        key_directory=keys,
        source_exists=True,
        source_writable=True,
    )


def test_plan_has_no_side_effects_and_removes_only_dnssec_directives(
    tmp_path: Path,
) -> None:
    zone = signed_zone(tmp_path)
    before = zone.config_file.read_bytes()

    plan = DnssecDisablePlanner().plan(zone)

    assert zone.config_file.read_bytes() == before
    assert 'zone "other.pl"' in plan.candidate_text
    assert "notify yes;" in plan.candidate_text
    assert "dnssec-policy" not in plan.candidate_text
    assert "inline-signing" not in plan.candidate_text
    assert "key-directory" not in plan.candidate_text
    assert "-    dnssec-policy default;" in plan.unified_diff
    assert plan.key_files
    assert plan.signing_artifacts == (tmp_path / "example.pl.signed",)
    assert any("withdrawn" in action for action in plan.actions)


def test_plan_rejects_secondary(tmp_path: Path) -> None:
    with pytest.raises(DnssecDisablePlanError, match="primary"):
        DnssecDisablePlanner().plan(signed_zone(tmp_path, zone_type="secondary"))


def test_plan_rejects_unsigned_or_partial_configuration(tmp_path: Path) -> None:
    zone = signed_zone(tmp_path)
    unsigned = ZoneConfig(
        name=zone.name,
        zone_type=zone.zone_type,
        source_file=zone.source_file,
        config_file=zone.config_file,
        source_exists=True,
    )
    with pytest.raises(DnssecDisablePlanError, match="pełnej konfiguracji"):
        DnssecDisablePlanner().plan(unsigned)


def test_plan_rejects_declaration_changed_from_discovery(tmp_path: Path) -> None:
    zone = signed_zone(tmp_path)
    zone.config_file.write_text(
        zone.config_file.read_text().replace("inline-signing yes;", ""),
        encoding="utf-8",
    )
    with pytest.raises(DnssecDisablePlanError, match="oczekiwanej"):
        DnssecDisablePlanner().plan(zone)
