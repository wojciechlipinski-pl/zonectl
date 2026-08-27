from __future__ import annotations

import inspect

from zonectl.ui.curses_app import CursesApp


def assert_wait_commit(source: str, title: str, label: str) -> None:
    assert "self._run_with_wait_indicator" in source
    assert title in source
    assert label in source
    assert "commit=True, activate=True" in source


def test_zone_creation_uses_shared_wait_dialog() -> None:
    assert_wait_commit(
        inspect.getsource(CursesApp._create_zone_wizard),
        'title=f"Tworzenie strefy: {plan.zone_name}"',
        'label="Zapis, walidacja i aktywacja strefy"',
    )


def test_bind_and_dnssec_onboarding_commits_use_shared_wait_dialog() -> None:
    assert_wait_commit(
        inspect.getsource(CursesApp._commit_bind_onboarding_import),
        'title=f"Import strefy: {zone_name}"',
        'label="Walidacja, aktywacja i kontrola BIND"',
    )
    assert_wait_commit(
        inspect.getsource(CursesApp._commit_dnssec_onboarding_import),
        'title=f"Import DNSSEC: {zone_name}"',
        'label="Walidacja, aktywacja i kontrola DNSSEC"',
    )


def test_zone_migration_and_relocation_use_shared_wait_dialog() -> None:
    assert_wait_commit(
        inspect.getsource(CursesApp._apply_zone_migration),
        'title=f"Migracja strefy: {zone.name}"',
        'label="Migracja deklaracji, walidacja i aktywacja BIND"',
    )
    assert_wait_commit(
        inspect.getsource(CursesApp._apply_zone_relocation),
        'title=f"Relokacja strefy: {zone.name}"',
        'label="Przenoszenie pliku, walidacja i aktywacja BIND"',
    )
