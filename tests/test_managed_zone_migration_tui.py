import inspect
from pathlib import Path

from zonectl.core.managed_zone_migration_transaction import (
    ManagedZoneMigrationResult,
    ManagedZoneMigrationStep,
)
from zonectl.ui.curses_app import CursesApp


class _Config:
    toolkit = {
        "bind_root_config": "/tmp/custom/named.conf",
        "bind_local_config": "/tmp/custom/named.conf.local",
        "managed_config": "/tmp/custom/zonectl-zones.conf",
        "managed_zone_dir": "/tmp/custom/zonectl-zones.d",
    }


def test_domain_view_routes_f6_to_zone_migration() -> None:
    source = inspect.getsource(CursesApp._domain_view)

    assert "curses.KEY_F6" in source
    assert "self._zone_migration_view(win, zone)" in source
    assert "self.config._discover_bind_zones()" in source
    assert "zone = current" in source
    assert "self.bind.quick_status(zone)" in source
    assert "F6 migracja" in source


def test_migration_view_uses_mc_keys_and_explicit_confirmation() -> None:
    view = inspect.getsource(CursesApp._zone_migration_view)
    apply = inspect.getsource(CursesApp._apply_zone_migration)

    assert "curses.KEY_F3" in view
    assert "curses.KEY_F4" in view
    assert "self.read_only" in view
    assert "transaction.apply(plan)" in apply
    assert "Wpisz pełną nazwę strefy" in apply
    assert "commit=True, activate=True" in apply


def test_migration_view_routes_managed_legacy_path_to_relocation() -> None:
    view = inspect.getsource(CursesApp._zone_migration_view)
    apply = inspect.getsource(CursesApp._apply_zone_relocation)

    assert "MANAGED_LEGACY_PATH" in view
    assert "_show_zone_relocation_plan" in view
    assert "_apply_zone_relocation" in view
    assert "transaction.apply(plan)" in apply
    assert "commit=True, activate=True" in apply


def test_tui_planner_uses_configured_paths() -> None:
    app = CursesApp.__new__(CursesApp)
    app.config = _Config()

    planner = app._zone_migration_planner()

    assert planner.root_config == Path("/tmp/custom/named.conf")
    assert planner.local_config == Path("/tmp/custom/named.conf.local")
    assert planner.managed_config == Path("/tmp/custom/zonectl-zones.conf")
    assert planner.managed_zone_directory == Path(
        "/tmp/custom/zonectl-zones.d"
    )


def test_migration_result_lines_show_rollback() -> None:
    result = ManagedZoneMigrationResult(
        "tx", "example.pl", "ROLLED-BACK", rolled_back=True
    )
    result.steps.append(
        ManagedZoneMigrationStep("rollback", True, "Przywrócono")
    )

    lines = CursesApp._migration_result_lines(result)

    assert "Status: ROLLED-BACK" in lines
    assert "Rollback: TAK" in lines
    assert "[OK] rollback: Przywrócono" in lines
