from __future__ import annotations

from pathlib import Path

from zonectl.core.models import Zone
from zonectl.ui.curses_app import CursesApp


def zone(name: str, group: str) -> Zone:
    return Zone(name=name, file=Path(f"/zones/{name}"), group=group)


def test_home_and_end_select_boundary_domains_not_group_headers() -> None:
    app = CursesApp(
        [zone("alpha.example", "A"), zone("omega.example", "Z")],
        bind=object(),
    )

    app.selected = len(app.rows) - 1
    app._move_to_boundary_zone(last=False)
    assert app.rows[app.selected].zone is not None
    assert app.rows[app.selected].zone.name == "alpha.example"

    app._move_to_boundary_zone(last=True)
    assert app.rows[app.selected].zone is not None
    assert app.rows[app.selected].zone.name == "omega.example"


def test_home_and_end_are_wired_in_main_loop() -> None:
    import inspect

    source = inspect.getsource(CursesApp._main)
    assert "key == curses.KEY_HOME" in source
    assert "self._move_to_boundary_zone(last=False)" in source
    assert "key == curses.KEY_END" in source
    assert "self._move_to_boundary_zone(last=True)" in source
