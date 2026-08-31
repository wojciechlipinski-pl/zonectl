from pathlib import Path

import pytest

from zonectl.core.managed_zone_migration import (
    ManagedZoneMigrationError,
    ManagedZoneMigrationPlanner,
)


def _tree(tmp_path: Path) -> ManagedZoneMigrationPlanner:
    bind = tmp_path / "bind"
    managed = bind / "zonectl-zones.d"
    managed.mkdir(parents=True)
    (bind / "named.conf").write_text('include "named.conf.local";\n', encoding="utf-8")
    (bind / "named.conf.local").write_text(
        'include "zonectl-zones.conf";\n\n'
        '// komentarz strefy\nzone "legacy.example" {\n'
        '    type primary;\n    file "/zones/legacy.example"; // zachowaj\n};\n\n'
        'zone "signed.example" { type primary; file "/zones/signed"; '
        "dnssec-policy default; inline-signing yes; };\n"
        'zone "secondary.example" { type secondary; primaries { 192.0.2.1; }; };\n'
        'zone "cert-rpz.local" { type primary; file "/zones/rpz"; };\n',
        encoding="utf-8",
    )
    (bind / "zonectl-zones.conf").write_text(
        'include "zonectl-zones.d/managed.example.conf";\n', encoding="utf-8"
    )
    (managed / "managed.example.conf").write_text(
        'zone "managed.example" { type primary; file "/zones/managed"; };\n',
        encoding="utf-8",
    )
    return ManagedZoneMigrationPlanner(
        root_config=bind / "named.conf",
        local_config=bind / "named.conf.local",
        managed_config=bind / "zonectl-zones.conf",
        managed_zone_directory=managed,
    )


def test_inventory_classifies_safe_and_blocked_zones(tmp_path: Path) -> None:
    planner = _tree(tmp_path)
    states = {item.name: item.state for item in planner.inventory()}

    assert states == {
        "cert-rpz.local": "BLOCKED_RPZ",
        "legacy.example": "LEGACY_PRIMARY",
        "managed.example": "MANAGED",
        "secondary.example": "BLOCKED_SECONDARY",
        "signed.example": "BLOCKED_DNSSEC",
    }


def test_plan_preserves_block_and_has_no_side_effects(tmp_path: Path) -> None:
    planner = _tree(tmp_path)
    before_local = planner.local_config.read_bytes()
    before_index = planner.managed_config.read_bytes()

    plan = planner.plan("legacy.example")

    assert "// komentarz strefy" not in plan.declaration_text
    assert "// zachowaj" in plan.declaration_text
    assert 'zone "legacy.example"' not in plan.source_candidate
    assert 'zone "signed.example"' in plan.source_candidate
    assert str(plan.declaration_file) in plan.managed_candidate
    assert plan.source_diff and plan.declaration_diff and plan.managed_diff
    assert planner.local_config.read_bytes() == before_local
    assert planner.managed_config.read_bytes() == before_index
    assert not plan.declaration_file.exists()


@pytest.mark.parametrize(
    "zone",
    ["signed.example", "secondary.example", "cert-rpz.local", "managed.example"],
)
def test_plan_rejects_non_migratable_zone(tmp_path: Path, zone: str) -> None:
    planner = _tree(tmp_path)
    with pytest.raises(ManagedZoneMigrationError, match="zablokowana"):
        planner.plan(zone)


def test_commented_zone_is_not_discovered(tmp_path: Path) -> None:
    planner = _tree(tmp_path)
    with planner.local_config.open("a", encoding="utf-8") as stream:
        stream.write('// zone "ignored.example" { type primary; };\n')

    assert "ignored.example" not in {item.name for item in planner.inventory()}


def test_plan_rejects_existing_target(tmp_path: Path) -> None:
    planner = _tree(tmp_path)
    target = planner.managed_zone_directory / "legacy.example.conf"
    target.write_text("reserved\n", encoding="utf-8")

    with pytest.raises(ManagedZoneMigrationError, match="istnieje"):
        planner.plan("legacy.example")


def test_dnssec_plan_requires_explicit_profile(tmp_path: Path) -> None:
    planner = _tree(tmp_path)
    with pytest.raises(ManagedZoneMigrationError, match="zablokowana"):
        planner.plan("signed.example")

    plan = planner.plan("signed.example", allow_dnssec=True)
    assert "dnssec-policy default;" in plan.declaration_text
    assert "inline-signing yes;" in plan.declaration_text
    assert any("stanu KASP" in action for action in plan.actions)
