from __future__ import annotations

from zonectl.core.models import Zone
from zonectl.ui.curses_app import CursesApp, Row


def app_with_rows() -> CursesApp:
    app = CursesApp.__new__(CursesApp)
    app.rows = [
        Row("group", "Test", count=2),
        Row(
            "zone",
            "one.example",
            zone=Zone(name="one.example", file=None),
        ),
        Row(
            "zone",
            "two.example",
            zone=Zone(name="two.example", file=None),
        ),
    ]
    app.selected = 1
    app.multi_selected = set()
    app.collapsed = set()
    app.offset = 0
    return app


def test_space_toggles_zone_in_multi_selection() -> None:
    app = app_with_rows()

    app._toggle_multi_selection()
    assert app.multi_selected == {"one.example"}

    app._toggle_multi_selection()
    assert app.multi_selected == set()


def test_selection_can_contain_multiple_zones() -> None:
    app = app_with_rows()

    app._toggle_multi_selection()
    app.selected = 2
    app._toggle_multi_selection()

    assert app.multi_selected == {
        "one.example",
        "two.example",
    }


def test_space_on_group_preserves_collapse_behavior(
    monkeypatch,
) -> None:
    app = app_with_rows()
    app.selected = 0
    monkeypatch.setattr(app, "_rebuild_rows", lambda: None)

    app._toggle_multi_selection()
    assert app.collapsed == {"Test"}

    app._toggle_multi_selection()
    assert app.collapsed == set()
