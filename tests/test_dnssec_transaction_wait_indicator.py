from __future__ import annotations

import inspect

from zonectl.ui.curses_app import CursesApp


def test_dnssec_commits_use_shared_wait_dialog() -> None:
    source = inspect.getsource(CursesApp._dnssec_status_view)

    expected = (
        ('title=f"Włączanie DNSSEC: {zone.name}"',
         "operation=lambda: self._dnssec_enable_commit(zone)"),
        ('title=f"Potwierdzenie DS: {zone.name}"',
         "self._dnssec_confirm_ds("),
        ('title=f"Backup DNSSEC: {zone.name}"',
         "self._dnssec_withdrawal_backup("),
        ('title=f"Finalizacja DNSSEC: {zone.name}"',
         "operation=lambda: self._dnssec_finalize_commit(zone)"),
    )
    for title, operation in expected:
        title_at = source.index(title)
        wait_at = source.rindex("self._run_with_wait_indicator", 0, title_at)
        operation_at = source.index(operation, title_at)
        assert wait_at < title_at < operation_at


def test_dnssec_wait_dialogs_preserve_existing_result_views() -> None:
    source = inspect.getsource(CursesApp._dnssec_status_view)

    for result_name in (
        "committed_enable",
        "committed_confirmation",
        "committed_backup",
        "committed_finalize",
    ):
        assignment = source.index(f"{result_name} = self._run_with_wait_indicator")
        result_view = source.index("self._message_view", assignment)
        assert assignment < result_view
