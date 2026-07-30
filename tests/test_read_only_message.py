from __future__ import annotations

from zonectl.ui.curses_app import CursesApp


class FakeWindow:
    def __init__(self) -> None:
        self.timeouts: list[int] = []
        self.getch_calls = 0

    def erase(self) -> None:
        pass

    def getmaxyx(self) -> tuple[int, int]:
        return (24, 100)

    def addnstr(self, *args) -> None:
        pass

    def refresh(self) -> None:
        pass

    def timeout(self, value: int) -> None:
        self.timeouts.append(value)

    def getch(self) -> int:
        self.getch_calls += 1
        return ord("q")


def test_read_only_message_waits_without_window_timeout() -> None:
    app = CursesApp([], bind=object())
    window = FakeWindow()

    app._message_view(
        window,
        title="Tylko odczyt",
        lines=["COMMIT jest zablokowany."],
    )

    assert window.getch_calls == 1
    assert window.timeouts == [-1, 150]
