from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

import zonectl.ui.curses_app as tui
from zonectl.core.models import Zone
from zonectl.ui.curses_app import CursesApp, CursesDialogs

from tests.test_dnssec_policy_migration import make_plan, policy
from zonectl.core.dnssec_policy_inventory import PolicyKey


class TinyWindow:
    def erase(self) -> None:
        pass

    def getmaxyx(self) -> tuple[int, int]:
        return (4, 18)

    def addnstr(self, *args) -> None:
        pass

    def refresh(self) -> None:
        pass


def _app(monkeypatch, tmp_path: Path):
    plan, _ = make_plan(tmp_path)
    app = CursesApp.__new__(CursesApp)
    app.config = SimpleNamespace(
        toolkit={"bind_root_config": str(plan.declaration_file)},
        read_only=False,
        discovered_zone=lambda name: SimpleNamespace(dnssec_policy="old"),
    )
    messages = []
    monkeypatch.setattr(app, "_message_view", lambda *a, **kw: messages.append(kw))
    monkeypatch.setattr(
        app,
        "_run_with_wait_indicator",
        lambda *a, operation, **kw: operation(),
    )
    return app, plan, messages


def test_dnssec_status_routes_migration_action_and_keeps_compact_footer() -> None:
    source = inspect.getsource(CursesApp._dnssec_status_view)

    assert 'key in (ord("m"), ord("M"))' in source
    assert "self._dnssec_policy_migration_view(win, zone)" in source
    assert "m migracja" in source
    assert "addnstr" in source


def test_policy_chooser_cancels_cleanly_on_compact_terminal(
    monkeypatch, tmp_path: Path
) -> None:
    app = CursesApp.__new__(CursesApp)
    app.config = SimpleNamespace(toolkit={})
    inventory = SimpleNamespace(
        policies=(policy("old", (PolicyKey("CSK", "ED25519", "P1Y"),)),)
    )
    monkeypatch.setattr(app, "_run_with_wait_indicator", lambda *a, **kw: inventory)
    monkeypatch.setattr(app, "_get_key", lambda win: 27)

    assert app._dnssec_policy_chooser(TinyWindow()) is None


def test_migration_chooser_cancellation_stops_before_planning(
    monkeypatch, tmp_path: Path
) -> None:
    app, plan, messages = _app(monkeypatch, tmp_path)
    monkeypatch.setattr(app, "_dnssec_policy_chooser", lambda *a, **kw: None)
    monkeypatch.setattr(
        tui.DnssecPolicyInventoryReader,
        "read",
        lambda self: (_ for _ in ()).throw(AssertionError("planning must not run")),
    )

    app._dnssec_policy_migration_view(
        TinyWindow(), Zone(plan.zone, plan.declaration_file)
    )

    assert messages == []


def test_migration_shows_dry_run_then_honors_confirmation(
    monkeypatch, tmp_path: Path
) -> None:
    app, plan, messages = _app(monkeypatch, tmp_path)
    selections = iter(((plan.source, False), (plan.target, False)))
    monkeypatch.setattr(
        app, "_dnssec_policy_chooser", lambda *a, **kw: next(selections)
    )
    monkeypatch.setattr(tui.DnssecPolicyInventoryReader, "read", lambda self: object())
    monkeypatch.setattr(tui.DnssecPolicyMigrationPlanner, "plan", lambda *a, **kw: plan)
    monkeypatch.setattr(CursesDialogs, "text_input", lambda *a, **kw: "wrong.example")

    app._dnssec_policy_migration_view(
        TinyWindow(), Zone(plan.zone, plan.declaration_file)
    )

    assert messages[0]["title"].startswith("Dry-run migracji")
    assert len(messages) == 1


def test_migration_confirmed_path_starts_committed_workflow(
    monkeypatch, tmp_path: Path
) -> None:
    app, plan, messages = _app(monkeypatch, tmp_path)
    selections = iter(((plan.source, False), (plan.target, False)))
    monkeypatch.setattr(
        app, "_dnssec_policy_chooser", lambda *a, **kw: next(selections)
    )
    monkeypatch.setattr(tui.DnssecPolicyInventoryReader, "read", lambda self: object())
    monkeypatch.setattr(tui.DnssecPolicyMigrationPlanner, "plan", lambda *a, **kw: plan)
    monkeypatch.setattr(CursesDialogs, "text_input", lambda *a, **kw: plan.zone)
    monkeypatch.setattr(CursesDialogs, "confirm", lambda *a, **kw: True)
    calls = []

    class FakeWorkflow:
        def __init__(self, *args, **kwargs):
            pass

        def start(self, selected_plan, **kwargs):
            calls.append((selected_plan, kwargs))
            return SimpleNamespace(
                status="POLICY_APPLIED",
                phase="POLICY_APPLIED",
                next_action="check",
            )

    monkeypatch.setattr(tui, "DnssecPolicyMigrationWorkflow", FakeWorkflow)

    app._dnssec_policy_migration_view(
        TinyWindow(), Zone(plan.zone, plan.declaration_file)
    )

    assert calls == [
        (
            plan,
            {"commit": True, "activate": True, "confirmation": plan.zone},
        )
    ]
    assert messages[-1]["error"] is False
    assert messages[-1]["lines"][0] == "Status: POLICY_APPLIED"


def test_migration_error_is_displayed(monkeypatch, tmp_path: Path) -> None:
    app, plan, messages = _app(monkeypatch, tmp_path)
    selections = iter(((plan.source, False), (plan.target, False)))
    monkeypatch.setattr(
        app, "_dnssec_policy_chooser", lambda *a, **kw: next(selections)
    )
    monkeypatch.setattr(tui.DnssecPolicyInventoryReader, "read", lambda self: object())
    monkeypatch.setattr(
        tui.DnssecPolicyMigrationPlanner,
        "plan",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("synthetic failure")),
    )

    app._dnssec_policy_migration_view(
        TinyWindow(), Zone(plan.zone, plan.declaration_file)
    )

    assert messages[-1]["error"] is True
    assert messages[-1]["title"] == "Błąd migracji polityki DNSSEC"
    assert messages[-1]["lines"] == ["synthetic failure"]
