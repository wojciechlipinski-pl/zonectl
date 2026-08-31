from __future__ import annotations

import curses

from zonectl.ui.curses_app import CursesApp


class RecordingWindow:
    def __init__(self, height: int, width: int) -> None:
        self.height = height
        self.width = width
        self.writes: list[tuple[int, int, str, int]] = []

    def erase(self) -> None:
        pass

    def getmaxyx(self) -> tuple[int, int]:
        return self.height, self.width

    def addnstr(self, row, column, text, limit, *attrs) -> None:
        self.writes.append((row, column, str(text), limit))

    def addch(self, *args) -> None:
        pass

    def refresh(self) -> None:
        pass

    def timeout(self, value: int) -> None:
        pass

    def getch(self) -> int:
        return ord("q")


def test_wide_message_keeps_multiline_transaction_output_in_left_panel(
    monkeypatch,
) -> None:
    monkeypatch.setattr(curses, "has_colors", lambda: False)
    window = RecordingWindow(24, 100)
    app = CursesApp([], bind=object())

    app._message_view(
        window,
        title="Wynik transakcji",
        lines=[
            "[OK] rndc-zonestatus: name: example.invalid\n"
            "type: primary\n"
            "a very long operational line that must wrap inside the left panel"
        ],
    )

    divider = 62
    detail_writes = [write for write in window.writes if write[1] == 3]
    assert detail_writes
    assert all("\n" not in text for _, _, text, _ in detail_writes)
    assert all(
        column + min(len(text), limit) < divider
        for _, column, text, limit in detail_writes
    )
    assert any(text == "type: primary" for _, _, text, _ in detail_writes)
