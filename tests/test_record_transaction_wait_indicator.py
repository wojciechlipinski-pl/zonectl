from __future__ import annotations

import inspect

from zonectl.ui.curses_app import CursesApp


def test_record_commit_uses_shared_wait_dialog() -> None:
    sources = (
        inspect.getsource(CursesApp._records_view),
        inspect.getsource(CursesApp._pending_changes_view),
    )

    for source in sources:
        assert "self._run_with_wait_indicator" in source
        assert 'title=f"Zapis rekordów: {zone.name}"' in source
        assert 'label="Walidacja i zapis transakcji rekordów"' in source
        assert "operation=lambda: session.save(commit=True)" in source


def test_record_commit_keeps_existing_transaction_result_flow() -> None:
    sources = (
        inspect.getsource(CursesApp._records_view),
        inspect.getsource(CursesApp._pending_changes_view),
    )

    for source in sources:
        wait_call = source.index("self._run_with_wait_indicator")
        result_view = source.index("self._transaction_result_view", wait_call)
        committed_check = source.index(
            "save_result.transaction.committed", result_view,
        )

        assert wait_call < result_view < committed_check
