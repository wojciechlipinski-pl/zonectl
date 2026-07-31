from __future__ import annotations

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


def test_tui_wizard_creates_and_adds_zone(monkeypatch) -> None:
    app = CursesApp([], bind=object())
    messages = []
    confirmations = iter([True])

    monkeypatch.setattr(
        ZoneCreateDialog,
        "collect",
        lambda *args, **kwargs: ZoneCreateForm(
            "new.example",
            "ns1.elkman.pl.",
            "hostmaster.elkman.pl.",
            "ns1.elkman.pl., ns2.elkman.pl.",
            "192.0.2.44",
            "",
            True,
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

    def apply(self, plan, *, commit=False, activate=False):
        assert commit is True and activate is True
        assert plan.zone_name == "new.example"
        assert "www IN A 192.0.2.44" in plan.zone_text
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
    assert app.all_zones[0].file == Path(
        "/var/lib/bind/Primary/new.example"
    )
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
    monkeypatch.setattr(
        ZoneCreateDialog,
        "collect",
        lambda *args, **kwargs: ZoneCreateForm(
            "bad_name",
            "ns1.elkman.pl.",
            "hostmaster.elkman.pl.",
            "ns1.elkman.pl.",
        ),
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
