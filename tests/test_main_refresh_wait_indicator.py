import threading
import inspect
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


def test_completed_refresh_removes_spinner_and_keeps_zone_status() -> None:
    item = zone()
    app = CursesApp([item], bind=object())
    app.worker = FinishedThread()
    app.refresh_indicator = WaitIndicator.start("Odświeżanie stref")
    app.statuses[item.name] = ZoneStatus(zone=item, health=Health.PASS)

    app._complete_refresh_if_ready()

    assert app.refresh_indicator is None
    assert app.statuses[item.name].health is Health.PASS


def test_completed_refresh_leaves_warning_and_failure_in_zone_rows() -> None:
    first = zone("warn.test")
    second = zone("fail.test")
    app = CursesApp([first, second], bind=object())
    app.worker = FinishedThread()
    app.refresh_indicator = WaitIndicator.start("Odświeżanie stref")
    app.statuses[first.name] = ZoneStatus(zone=first, health=Health.WARN)
    app.statuses[second.name] = ZoneStatus(zone=second, health=Health.FAIL)

    app._complete_refresh_if_ready()

    assert app.refresh_indicator is None
    assert app.statuses[first.name].health is Health.WARN
    assert app.statuses[second.name].health is Health.FAIL


def test_running_worker_keeps_indicator_active() -> None:
    app = CursesApp([zone()], bind=object())
    app.worker = threading.Thread(target=lambda: None)
    app.worker.start()
    app.worker.join()

    app.refresh_indicator = WaitIndicator.start("Odświeżanie stref")
    app.messages.put(("example.test", ZoneStatus(zone=zone())))
    app._complete_refresh_if_ready()

    assert app.refresh_indicator is not None


def test_main_refresh_uses_centered_wait_box_and_blocks_actions() -> None:
    draw = inspect.getsource(CursesApp._draw)
    main = inspect.getsource(CursesApp._main)

    assert "self._draw_wait_box" in draw
    assert 'title="Odświeżanie stref"' in draw
    assert "_draw_refresh_status" not in draw
    assert "if self.refresh_indicator is not None" in main
    assert main.index("if self.refresh_indicator is not None") < main.index(
        'if key in (ord("q"), 27, curses.KEY_F10)'
    )


def test_main_loop_restores_polling_after_modal_wait_view() -> None:
    main = inspect.getsource(CursesApp._main)

    draw = "self._draw(stdscr)"
    polling = "stdscr.timeout(150)"
    read_key = "key = self._get_key("
    loop_body = main[main.index("while not self.stop_event.is_set():") :]

    assert loop_body.index(draw) < loop_body.index(polling) < loop_body.index(read_key)
