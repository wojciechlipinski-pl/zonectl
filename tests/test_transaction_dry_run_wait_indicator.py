from __future__ import annotations

import inspect

from zonectl.ui.curses_app import CursesApp


def assert_wait_dry_run(method: object, title: str) -> None:
    source = inspect.getsource(method)
    assert "self._run_with_wait_indicator" in source
    assert title in source
    assert "operation=lambda: transaction.apply(" in source


def test_onboarding_dry_runs_use_wait_dialogs() -> None:
    assert_wait_dry_run(
        CursesApp._dry_run_bind_onboarding_import,
        'title=f"Dry-run importu: {zone_name}"',
    )
    assert_wait_dry_run(
        CursesApp._commit_bind_onboarding_import,
        'title=f"Kontrola importu: {zone_name}"',
    )
    assert_wait_dry_run(
        CursesApp._dry_run_dnssec_onboarding_import,
        'title=f"Dry-run importu DNSSEC: {zone_name}"',
    )
    assert_wait_dry_run(
        CursesApp._commit_dnssec_onboarding_import,
        'title=f"Kontrola importu DNSSEC: {zone_name}"',
    )


def test_bind_access_dry_runs_use_wait_dialogs() -> None:
    assert_wait_dry_run(CursesApp._edit_acl, 'title=f"Dry-run ACL: {name}"')
    assert_wait_dry_run(
        CursesApp._edit_secondary_group,
        'title=f"Dry-run secondary: {name}"',
    )
    assert_wait_dry_run(
        CursesApp._zone_secondary_view,
        'title=f"Dry-run secondary: {zone.name}"',
    )


def test_migration_and_relocation_dry_runs_use_wait_dialogs() -> None:
    assert_wait_dry_run(
        CursesApp._apply_zone_migration,
        'title=f"Dry-run migracji: {zone.name}"',
    )
    assert_wait_dry_run(
        CursesApp._apply_zone_relocation,
        'title=f"Dry-run relokacji: {zone.name}"',
    )
