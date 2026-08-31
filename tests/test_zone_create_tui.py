from __future__ import annotations

import curses
from pathlib import Path

from zonectl.core.zone_create_transaction import (
    ZoneCreateResult,
    ZoneCreateStep,
)
from zonectl.ui.curses_app import CursesApp
from zonectl.ui.dialogs import CursesDialogs
from zonectl.ui.zone_create_dialog import ZoneCreateDialog, ZoneCreateForm


class FakeWindow:
    def getmaxyx(self):
        return (30, 120)


class KeyWindow:
    def __init__(self, keys: list[int]):
        self.keys = list(keys)

    def getch(self):
        return self.keys.pop(0) if self.keys else -1

    def timeout(self, value):
        pass


def test_zone_create_dialog_decodes_home_and_end() -> None:
    assert ZoneCreateDialog._get_key(KeyWindow([27, *b"[H"])) == curses.KEY_HOME
    assert ZoneCreateDialog._get_key(KeyWindow([27, *b"[F"])) == curses.KEY_END


def test_tui_wizard_creates_and_adds_zone(monkeypatch) -> None:
    app = CursesApp([], bind=object())
    messages = []
    confirmations = iter([True])

    monkeypatch.setattr(
        ZoneCreateDialog,
        "collect",
        lambda *args, **kwargs: ZoneCreateForm(
            "new.example",
            "ns1.example.pl.",
            "hostmaster.example.pl.",
            "ns1.example.pl., ns2.example.pl.",
            "192.0.2.44",
            "",
            True,
            group="Klienci",
            refresh=7200,
            retry=1200,
            expire=604800,
            negative_ttl=600,
        ),
    )
    monkeypatch.setattr(
        CursesDialogs,
        "confirm",
        lambda *args, **kwargs: next(confirmations),
    )
    monkeypatch.setattr(
        app,
        "_message_view",
        lambda *args, **kwargs: messages.append(kwargs),
    )
    monkeypatch.setattr(
        app,
        "_run_with_wait_indicator",
        lambda win, *, title, label, operation: operation(),
    )

    def apply(self, plan, *, commit=False, activate=False):
        assert commit is True and activate is True
        assert plan.zone_name == "new.example"
        assert "www IN A 192.0.2.44" in plan.zone_text
        assert "    7200 ; refresh" in plan.zone_text
        assert plan.group == "Klienci"
        return ZoneCreateResult(
            "tx-create",
            plan.zone_name,
            "COMMIT",
            committed=True,
            steps=[ZoneCreateStep("rndc-zonestatus", True, "loaded")],
        )

    monkeypatch.setattr(
        "zonectl.ui.curses_app.ZoneCreateTransaction.apply",
        apply,
    )

    app._create_zone_wizard(FakeWindow())

    assert [zone.name for zone in app.all_zones] == ["new.example"]
    assert app.all_zones[0].file == Path("/var/lib/bind/Primary/new.example")
    assert app.all_zones[0].group == "Klienci"
    assert len(messages) == 2


def test_tui_wizard_cancel_before_plan_has_no_effect(monkeypatch) -> None:
    app = CursesApp([], bind=object())
    monkeypatch.setattr(
        ZoneCreateDialog,
        "collect",
        lambda *args, **kwargs: None,
    )

    app._create_zone_wizard(FakeWindow())

    assert app.all_zones == []


def test_tui_wizard_shows_validation_error(monkeypatch) -> None:
    app = CursesApp([], bind=object())
    messages = []
    forms = iter(
        (
            ZoneCreateForm(
                "bad_name",
                "ns1.example.pl.",
                "hostmaster.example.pl.",
                "ns1.example.pl.",
            ),
            None,
        )
    )
    monkeypatch.setattr(
        ZoneCreateDialog,
        "collect",
        lambda *args, **kwargs: next(forms),
    )
    monkeypatch.setattr(
        CursesDialogs,
        "confirm",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(
        app,
        "_message_view",
        lambda *args, **kwargs: messages.append(kwargs),
    )

    app._create_zone_wizard(FakeWindow())

    assert app.all_zones == []
    assert messages[0]["error"] is True
    assert "Błąd planu" in messages[0]["title"]


def test_tui_wizard_returns_to_preserved_form_after_preview(monkeypatch) -> None:
    app = CursesApp([], bind=object())
    first = ZoneCreateForm(
        "test-zone.example",
        "ns1.example.pl.",
        "hostmaster.example.pl.",
        "ns1.example.pl.",
    )
    corrected = ZoneCreateForm(
        "test-zone.example",
        "ns1.example.pl.",
        "admin.example.pl.",
        "ns1.example.pl.",
    )
    initial_values = []
    forms = iter((first, corrected))
    monkeypatch.setattr(
        ZoneCreateDialog,
        "collect",
        lambda *args, **kwargs: (
            initial_values.append(kwargs.get("initial")) or next(forms)
        ),
    )
    confirmations = iter((False, True))
    monkeypatch.setattr(
        CursesDialogs,
        "confirm",
        lambda *args, **kwargs: next(confirmations),
    )
    monkeypatch.setattr(app, "_message_view", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        app,
        "_run_with_wait_indicator",
        lambda win, *, title, label, operation: operation(),
    )

    def apply(self, plan, *, commit=False, activate=False):
        assert "admin.example.pl." in plan.zone_text
        return ZoneCreateResult(
            "tx",
            plan.zone_name,
            "COMMIT",
            committed=True,
            steps=[ZoneCreateStep("loaded", True, "OK")],
        )

    monkeypatch.setattr(
        "zonectl.ui.curses_app.ZoneCreateTransaction.apply",
        apply,
    )

    app._create_zone_wizard(FakeWindow())

    assert initial_values == [None, first]
