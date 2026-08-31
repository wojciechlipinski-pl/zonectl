import inspect

from zonectl.ui.curses_app import CursesApp


def test_secondary_health_uses_shared_non_cancellable_wait_view() -> None:
    source = inspect.getsource(CursesApp._show_secondary_health)

    assert "self._run_with_wait_indicator" in source
    assert 'label="Sprawdzanie propagacji secondary"' in source
    assert "BindSecondaryHealthGate().check" in source


def test_wait_view_preserves_operation_result_and_has_no_cancel_path() -> None:
    source = inspect.getsource(CursesApp._run_with_wait_indicator)
    box = inspect.getsource(CursesApp._draw_wait_box)

    assert "future.done()" in source
    assert "future.result()" in source
    assert "Operacji nie można anulować" in box
    assert "future.cancel" not in source
    assert "stop_event" not in source


def test_wait_view_uses_centered_framed_overlay() -> None:
    runner = inspect.getsource(CursesApp._run_with_wait_indicator)
    box = inspect.getsource(CursesApp._draw_wait_box)

    assert "self._draw_wait_box" in runner
    assert "(height - box_height) // 2" in box
    assert "(width - box_width) // 2" in box
    for border in (
        "ACS_ULCORNER",
        "ACS_URCORNER",
        "ACS_LLCORNER",
        "ACS_LRCORNER",
    ):
        assert border in box
    assert "stage = indicator.label" in box
    assert "indicator.frame()" in box
    assert "indicator.elapsed()" in box
    assert "top + 2" in box
    assert "top + 4" in box
    assert "top + 6" in box


def test_wait_view_restores_blocking_input_mode() -> None:
    source = inspect.getsource(CursesApp._run_with_wait_indicator)

    assert "win.timeout(100)" in source
    assert "win.timeout(-1)" in source
    assert "except curses.error" in source
