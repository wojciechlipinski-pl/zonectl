from __future__ import annotations

import curses

from zonectl.ui.dialogs import CursesDialogs


class FakeWindow:
    def __init__(self) -> None:
        self.timeouts: list[int] = []

    def getmaxyx(self) -> tuple[int, int]:
        return (24, 100)

    def move(self, _row: int, _column: int) -> None:
        pass

    def clrtoeol(self) -> None:
        pass

    def addnstr(self, *_args) -> None:
        pass

    def refresh(self) -> None:
        pass

    def timeout(self, value: int) -> None:
        self.timeouts.append(value)


def test_confirmation_ignores_function_keys() -> None:
    window = FakeWindow()
    keys = iter([curses.KEY_F1, curses.KEY_F7, ord("t")])

    confirmed = CursesDialogs.confirm(
        window,
        "Kontynuować?",
        key_reader=lambda _window: next(keys),
    )

    assert confirmed is True


def test_confirmation_rejects_explicit_no_after_function_key() -> None:
    window = FakeWindow()
    keys = iter([curses.KEY_F10, ord("n")])

    confirmed = CursesDialogs.confirm(
        window,
        "Kontynuować?",
        key_reader=lambda _window: next(keys),
    )

    assert confirmed is False
