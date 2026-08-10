from __future__ import annotations

import inspect
from pathlib import Path

from zonectl.core.dnssec_disable_transaction import DnssecDisableResult
from zonectl.core.models import Zone
from zonectl.ui.curses_app import CursesApp


def test_dnssec_screen_exposes_read_only_withdrawal_actions() -> None:
    source = inspect.getsource(CursesApp._dnssec_status_view)

    assert "F3 plan" in source
    assert "F4 dry-run finalizacji" in source
    assert "key == curses.KEY_F3" in source
    assert "key == curses.KEY_F4" in source
    assert 'ord("p")' not in source
    assert 'ord("f")' not in source
    assert "self._dnssec_disable_plan(zone)" in source
    assert "self._dnssec_finalize_dry_run(zone)" in source


def test_finalize_action_is_always_a_dry_run(monkeypatch) -> None:
    calls = []
    sentinel_plan = object()

    class FakeTransaction:
        def __init__(self, backup_root, manifest_directory):
            calls.append((backup_root, manifest_directory))

        def apply(self, plan, **kwargs):
            calls.append((plan, kwargs))
            return DnssecDisableResult("tx", "example.pl", "DRY-RUN")

    app = CursesApp.__new__(CursesApp)
    monkeypatch.setattr(app, "_dnssec_disable_plan", lambda _zone: sentinel_plan)
    monkeypatch.setattr(
        "zonectl.ui.curses_app.DnssecDisableTransaction", FakeTransaction
    )

    result = app._dnssec_finalize_dry_run(Zone("example.pl", Path("zone.db")))

    assert result.status == "DRY-RUN"
    assert calls[-1] == (sentinel_plan, {"stage": "finalize"})


def test_finalize_commit_uses_commit_and_activation(monkeypatch) -> None:
    calls = []
    sentinel_plan = object()

    class FakeTransaction:
        def __init__(self, _backup_root, _manifest_directory):
            pass

        def apply(self, plan, **kwargs):
            calls.append((plan, kwargs))
            return DnssecDisableResult("tx", "example.pl", "COMMIT")

    app = CursesApp.__new__(CursesApp)
    monkeypatch.setattr(app, "_dnssec_disable_plan", lambda _zone: sentinel_plan)
    monkeypatch.setattr(
        "zonectl.ui.curses_app.DnssecDisableTransaction", FakeTransaction
    )

    app._dnssec_finalize_commit(Zone("example.pl", Path("zone.db")))

    assert calls == [
        (
            sentinel_plan,
            {"stage": "finalize", "commit": True, "activate": True},
        )
    ]


def test_commit_path_requires_ready_stage_and_exact_zone_name() -> None:
    source = inspect.getsource(CursesApp._dnssec_status_view)

    assert 'view.stage == "READY_TO_FINALIZE"' in source
    assert "Wpisz pełną nazwę strefy" in source
    assert "supplied != expected" in source
    assert "CursesDialogs.confirm" in source
    assert "self._dnssec_finalize_commit(zone)" in source
