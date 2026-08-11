from __future__ import annotations

import inspect
from pathlib import Path

from zonectl.core.dnssec_disable_transaction import DnssecDisableResult
from zonectl.core.dnssec_enable_transaction import DnssecEnableResult
from zonectl.core.dnssec_withdrawal_backup import DnssecWithdrawalBackupResult
from zonectl.core.models import Zone
from zonectl.ui.curses_app import CursesApp


def test_dnssec_screen_exposes_read_only_withdrawal_actions() -> None:
    source = inspect.getsource(CursesApp._dnssec_status_view)

    assert "F3 plan" in source
    assert "F4 {view.operation_label" in source
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


def test_f4_routes_non_finalize_stages_to_guidance_only() -> None:
    source = inspect.getsource(CursesApp._dnssec_status_view)

    assert 'view.operation != "FINALIZE"' in source
    assert 'view.operation == "WITHDRAWAL"' in source
    assert 'view.operation == "ENABLE"' in source
    assert "self._dnssec_withdrawal_backup(zone)" in source


def test_withdrawal_backup_routes_dry_run_and_commit(monkeypatch) -> None:
    calls = []
    sentinel_plan = type(
        "Plan",
        (),
        {"key_directory": Path("keys"), "zone": "example.pl"},
    )()

    class Payload:
        def to_dict(self):
            return {"status": "PASS"}

    class FakeReporter:
        def __init__(self, **_kwargs):
            pass

        def collect(self, *_args):
            return Payload()

    class FakeChecker(FakeReporter):
        pass

    class FakeBackup:
        def __init__(self, root):
            calls.append(("root", root))

        def create(self, plan, **kwargs):
            calls.append((plan, kwargs))
            status = "BACKUP-CREATED" if kwargs["commit"] else "DRY-RUN"
            return DnssecWithdrawalBackupResult("tx", "example.pl", status)

    app = CursesApp.__new__(CursesApp)
    app.config = None
    monkeypatch.setattr(app, "_dnssec_disable_plan", lambda _zone: sentinel_plan)
    monkeypatch.setattr("zonectl.ui.curses_app.DnssecReporter", FakeReporter)
    monkeypatch.setattr("zonectl.ui.curses_app.DnssecDsChecker", FakeChecker)
    monkeypatch.setattr("zonectl.ui.curses_app.DnssecWithdrawalBackup", FakeBackup)

    zone = Zone("example.pl", Path("zone.db"))
    assert app._dnssec_withdrawal_backup(zone).status == "DRY-RUN"
    assert app._dnssec_withdrawal_backup(zone, commit=True).status == "BACKUP-CREATED"
    assert calls[-1][1]["commit"] is True
    assert calls[-1][1]["dnssec_report"] == {"status": "PASS"}
    assert calls[-1][1]["ds_check"] == {"status": "PASS"}


def test_withdrawal_backup_ui_requires_exact_confirmation() -> None:
    source = inspect.getsource(CursesApp._dnssec_status_view)

    assert "Wpisz pełną nazwę strefy, aby utworzyć backup" in source
    assert "Utworzyć backup wycofania DNSSEC" in source
    assert "zone, commit=True" in source
    assert 'committed.status != "BACKUP-CREATED"' in source


def test_enable_dry_run_never_commits_or_activates(monkeypatch) -> None:
    calls = []
    sentinel_plan = object()

    class FakeTransaction:
        def __init__(self, backup_root, manifest_directory):
            calls.append((backup_root, manifest_directory))

        def apply(self, plan, **kwargs):
            calls.append((plan, kwargs))
            return DnssecEnableResult("tx", "example.pl", "DRY-RUN")

    app = CursesApp.__new__(CursesApp)
    monkeypatch.setattr(app, "_dnssec_enable_plan", lambda _zone: sentinel_plan)
    monkeypatch.setattr(
        "zonectl.ui.curses_app.DnssecEnableTransaction", FakeTransaction
    )

    result = app._dnssec_enable_dry_run(Zone("example.pl", Path("zone.db")))

    assert result.status == "DRY-RUN"
    assert calls[-1] == (sentinel_plan, {})


def test_unsigned_tui_uses_real_plan_and_dry_run() -> None:
    source = inspect.getsource(CursesApp._dnssec_status_view)

    assert "plan = self._dnssec_enable_plan(zone)" in source
    assert "plan.unified_diff.splitlines()" in source
    assert "self._dnssec_enable_dry_run(zone)" in source
    assert "Dry-run włączenia DNSSEC" in source


def test_enable_commit_uses_commit_and_activation(monkeypatch) -> None:
    calls = []
    sentinel_plan = object()

    class FakeTransaction:
        def __init__(self, _backup_root, _manifest_directory):
            pass

        def apply(self, plan, **kwargs):
            calls.append((plan, kwargs))
            return DnssecEnableResult("tx", "example.pl", "COMMIT")

    app = CursesApp.__new__(CursesApp)
    monkeypatch.setattr(app, "_dnssec_enable_plan", lambda _zone: sentinel_plan)
    monkeypatch.setattr(
        "zonectl.ui.curses_app.DnssecEnableTransaction", FakeTransaction
    )

    app._dnssec_enable_commit(Zone("example.pl", Path("zone.db")))

    assert calls == [(sentinel_plan, {"commit": True, "activate": True})]


def test_enable_commit_ui_requires_exact_confirmation() -> None:
    source = inspect.getsource(CursesApp._dnssec_status_view)

    assert "Wpisz pełną nazwę strefy, aby włączyć DNSSEC" in source
    assert "Włączyć i aktywować DNSSEC" in source
    assert "self._dnssec_enable_commit(zone)" in source
    assert "self.config.read_only" in source
