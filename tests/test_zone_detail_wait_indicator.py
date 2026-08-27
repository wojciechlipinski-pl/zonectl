from __future__ import annotations

import inspect

from zonectl.ui.curses_app import CursesApp


def test_zone_detail_refresh_uses_wait_dialog() -> None:
    source = inspect.getsource(CursesApp._domain_view)

    assert 'title=f"Odświeżanie strefy: {zone.name}"' in source
    assert 'label="Kontrola BIND, SOA i propagacji"' in source
    assert "operation=lambda: self.bind.quick_status(zone)" in source
    assert 'notice = "Sprawdzanie strefy..."' not in source


def test_record_file_loading_uses_wait_dialog_for_new_session() -> None:
    source = inspect.getsource(CursesApp._records_view)

    assert "if existing_session is not None:" in source
    assert 'title=f"Rekordy strefy: {zone.name}"' in source
    assert 'label="Odczyt i analiza pliku strefy"' in source
    assert "operation=lambda: ZoneEditSession(" in source


def test_post_migration_status_refresh_uses_wait_dialog() -> None:
    source = inspect.getsource(CursesApp._domain_view)

    assert source.count('title=f"Odświeżanie strefy: {zone.name}"') == 2
    assert source.count("operation=lambda: self.bind.quick_status(zone)") == 2
