import curses

from zonectl.ui.dialogs import CursesDialogs


class FakeWindow:
    def __init__(self, keys: list[int]) -> None:
        self.keys = list(keys)
        self.timeouts: list[int] = []

    def getch(self) -> int:
        return self.keys.pop(0) if self.keys else -1

    def timeout(self, value: int) -> None:
        self.timeouts.append(value)

    def move(self, *_args) -> None:
        pass

    def clrtoeol(self) -> None:
        pass

    def addnstr(self, *_args) -> None:
        pass

    def refresh(self) -> None:
        pass


def test_editor_modifies_the_real_initial_value_with_arrows_and_delete() -> None:
    win = FakeWindow([
        curses.KEY_LEFT,
        curses.KEY_LEFT,
        curses.KEY_DC,
        ord("9"),
        10,
    ])
    assert CursesDialogs._edit_line(win, 0, 0, "192.0.2.53", 30) == "192.0.2.93"


def test_editor_can_remove_entire_initial_value() -> None:
    win = FakeWindow([curses.KEY_HOME] + [curses.KEY_DC] * 11 + [10])
    assert CursesDialogs._edit_line(win, 0, 0, "192.0.2.53", 30) == ""


def test_xterm_end_sequence_is_normalized_and_not_inserted_as_text() -> None:
    win = FakeWindow([27, ord("["), ord("4"), ord("~")])
    assert CursesDialogs._get_key(win) == curses.KEY_END
    assert win.timeouts == [80, -1]


def test_xterm_delete_sequence_is_normalized() -> None:
    win = FakeWindow([27, ord("["), ord("3"), ord("~")])
    assert CursesDialogs._get_key(win) == curses.KEY_DC


def test_escape_without_sequence_cancels_editor() -> None:
    assert CursesDialogs._edit_line(FakeWindow([27]), 0, 0, "value", 20) is None
