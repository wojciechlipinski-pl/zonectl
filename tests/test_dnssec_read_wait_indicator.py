from __future__ import annotations

import inspect

from zonectl.ui.curses_app import CursesApp


def test_dnssec_status_and_delegation_checks_use_wait_dialogs() -> None:
    source = inspect.getsource(CursesApp._dnssec_status_view)

    assert 'title=f"Status DNSSEC: {zone.name}"' in source
    assert 'title=f"Kontrola DS: {zone.name}"' in source
    assert source.count("operation=lambda: self._collect_dnssec_status(zone)") == 2


def test_dnssec_dry_runs_use_wait_dialogs() -> None:
    source = inspect.getsource(CursesApp._dnssec_status_view)

    expected = (
        ("Dry-run backupu DNSSEC", "_dnssec_withdrawal_backup"),
        ("Dry-run potwierdzenia DS", "_dnssec_confirm_ds"),
        ("Dry-run włączenia DNSSEC", "_dnssec_enable_dry_run"),
        ("Dry-run finalizacji DNSSEC", "_dnssec_finalize_dry_run"),
    )
    for title, helper in expected:
        title_at = source.index(f'title=f"{title}: {{zone.name}}"')
        wait_at = source.rindex("self._run_with_wait_indicator", 0, title_at)
        helper_at = source.index(f"self.{helper}(zone)", title_at)
        assert wait_at < title_at < helper_at
