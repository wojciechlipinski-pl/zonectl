import threading
from pathlib import Path

from zonectl.core.models import Health, Zone, ZoneStatus
from zonectl.ui.curses_app import CursesApp
from zonectl.ui.wait_indicator import WaitIndicator


class FinishedThread(threading.Thread):
    def is_alive(self) -> bool:
        return False


def zone(name: str = "example.test") -> Zone:
    return Zone(name=name, file=Path(f"/zones/{name}"), group="Test")


def test_main_refresh_starts_visible_wait_indicator(monkeypatch) -> None:
    app = CursesApp([zone()], bind=object())

    class ThreadWithoutStart(threading.Thread):
        def start(self) -> None:
            return None

        def is_alive(self) -> bool:
            return False

    monkeypatch.setattr(threading, "Thread", ThreadWithoutStart)
    app._start_refresh(force=True)

    assert app.refresh_indicator is not None
    assert "Odświeżanie stref" in app.refresh_indicator.render()
    assert app.refresh_notice is None


def test_completed_refresh_replaces_spinner_with_pass() -> None:
    item = zone()
    app = CursesApp([item], bind=object())
    app.worker = FinishedThread()
    app.refresh_indicator = WaitIndicator.start("Odświeżanie stref")
    app.statuses[item.name] = ZoneStatus(zone=item, health=Health.PASS)

    app._complete_refresh_if_ready()

    assert app.refresh_indicator is None
    assert app.refresh_notice == (
        "[PASS] Odświeżanie stref: sprawdzono 1/1"
    )


def test_completed_refresh_preserves_warning_and_failure_semantics() -> None:
    first = zone("warn.test")
    second = zone("fail.test")
    app = CursesApp([first, second], bind=object())
    app.worker = FinishedThread()
    app.refresh_indicator = WaitIndicator.start("Odświeżanie stref")
    app.statuses[first.name] = ZoneStatus(zone=first, health=Health.WARN)
    app.statuses[second.name] = ZoneStatus(zone=second, health=Health.FAIL)

    app._complete_refresh_if_ready()

    assert app.refresh_notice == (
        "[FAIL] Odświeżanie stref: sprawdzono 2/2"
    )


def test_running_worker_keeps_indicator_active() -> None:
    app = CursesApp([zone()], bind=object())
    app.worker = threading.Thread(target=lambda: None)
    app.worker.start()
    app.worker.join()

    app.refresh_indicator = WaitIndicator.start("Odświeżanie stref")
    app.messages.put(("example.test", ZoneStatus(zone=zone())))
    app._complete_refresh_if_ready()

    assert app.refresh_indicator is not None
    assert app.refresh_notice is None
