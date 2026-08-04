from __future__ import annotations

import curses

from zonectl.ui.records.editor import RecordEditor


class FakeWindow:
    def __init__(self, keys: list[int]):
        self.keys = list(keys)
        self.timeouts: list[int] = []

    def getch(self) -> int:
        if not self.keys:
            return -1
        return self.keys.pop(0)

    def timeout(self, value: int) -> None:
        self.timeouts.append(value)


def read_sequence(sequence: bytes) -> int:
    window = FakeWindow([27, *sequence])
    return RecordEditor._get_key(window)


def test_editor_decodes_putty_linux_f2() -> None:
    assert read_sequence(b"[[B") == curses.KEY_F2


def test_editor_decodes_xterm_f2() -> None:
    assert read_sequence(b"OQ") == curses.KEY_F2
    assert read_sequence(b"[12~") == curses.KEY_F2


def test_editor_decodes_home_and_end_sequences() -> None:
    for sequence in (b"[H", b"OH", b"[1~", b"[7~"):
        assert read_sequence(sequence) == curses.KEY_HOME

    for sequence in (b"[F", b"OF", b"[4~", b"[8~"):
        assert read_sequence(sequence) == curses.KEY_END


def test_editor_keeps_escape_for_unknown_sequence(
    monkeypatch,
) -> None:
    restored: list[int] = []
    monkeypatch.setattr(
        curses,
        "ungetch",
        lambda key: restored.append(key),
    )
    window = FakeWindow([27, ord("["), ord("9"), ord("9"), ord("~")])

    assert RecordEditor._get_key(window) == 27
    assert restored == [
        ord("~"),
        ord("9"),
        ord("9"),
        ord("["),
    ]
