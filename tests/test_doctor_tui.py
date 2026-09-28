from __future__ import annotations

import inspect

from zonectl.ui.curses_app import CursesApp


def test_main_tui_routes_f5_to_doctor() -> None:
    main = inspect.getsource(CursesApp._main)
    footer = inspect.getsource(CursesApp._draw_main_footer)
    view = inspect.getsource(CursesApp._doctor_view)

    assert "curses.KEY_F5" in main
    assert '"F5", "Doctor"' in footer
    assert "Doctor(" in view
    assert "_run_with_wait_indicator" in view


def test_doctor_tui_preserves_preview_and_double_public_confirmation() -> None:
    view = inspect.getsource(CursesApp._doctor_view)

    assert "podgląd publicznego zgłoszenia" in view
    assert "PUBLIC_CONFIRMATION" in view
    assert "Wpisz ponownie" in view
    assert view.index("prepared.body") < view.index("submit_issue")
    assert "Nie wysłano żadnych danych" in view


def test_doctor_tui_offers_headless_link_and_local_report() -> None:
    view = inspect.getsource(CursesApp._doctor_view)

    assert 'action == "LINK"' in view
    assert 'action == "ZAPISZ"' in view
    assert "prepared.url" in view
    assert "write_public_report" in view
