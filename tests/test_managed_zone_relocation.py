from pathlib import Path

import pytest

from zonectl.core.managed_zone_relocation import (
    ManagedZoneRelocationError,
    ManagedZoneRelocationPlanner,
)


def _planner(tmp_path: Path):
    bind = tmp_path / "bind"
    managed = bind / "zonectl-zones.d"
    old = bind / "Primary"
    target = tmp_path / "var/lib/bind/Primary"
    managed.mkdir(parents=True)
    old.mkdir()
    target.mkdir(parents=True)
    source = old / "example.pl"
    source.write_text(
        "$TTL 3600\n@ IN SOA ns1.example. hostmaster.example. 1 1 1 1 1\n"
    )
    declaration = managed / "example.pl.conf"
    declaration.write_text(f'zone "example.pl" {{ type primary; file "{source}"; }};\n')
    root = bind / "named.conf"
    root.write_text(f'include "{declaration}";\n')
    planner = ManagedZoneRelocationPlanner(
        root_config=root,
        managed_zone_directory=managed,
        target_directory=target,
    )
    return planner, source, target / "example.pl", declaration


def test_plan_relocates_only_file_directive(tmp_path: Path) -> None:
    planner, source, target, declaration = _planner(tmp_path)

    plan = planner.plan("example.pl")

    assert plan.source_file == source.resolve()
    assert plan.target_file == target.resolve()
    assert str(target.resolve()) in plan.declaration_candidate
    assert str(source.resolve()) in plan.declaration_original
    assert declaration.read_text() == plan.declaration_original
    assert not target.exists()


def test_existing_target_blocks_relocation(tmp_path: Path) -> None:
    planner, _source, target, _declaration = _planner(tmp_path)
    target.write_text("conflict")

    with pytest.raises(ManagedZoneRelocationError, match="docelowy już istnieje"):
        planner.plan("example.pl")
