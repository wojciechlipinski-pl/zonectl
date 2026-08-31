from __future__ import annotations

import curses
from types import SimpleNamespace

import pytest

from zonectl.ui import curses_app
from zonectl.ui.curses_app import CursesApp
from zonectl.ui.wait_indicator import ASCII_FRAMES, BRAILLE_FRAMES, WaitIndicator


class StrictWindow:
    """Minimal curses window that rejects writes outside terminal bounds."""

    def __init__(self, height: int, width: int) -> None:
        self.height = height
        self.width = width
        self.writes: list[tuple[int, int, str]] = []

    def erase(self) -> None:
        pass

    def getmaxyx(self) -> tuple[int, int]:
        return self.height, self.width

    def addnstr(self, row, column, value, limit, *attrs) -> None:
        text = str(value)[: max(0, limit)]
        self._check_span(row, column, len(text))
        self.writes.append((row, column, text))

    def addch(self, row, column, *args) -> None:
        self._check_span(row, column, 1)

    def hline(self, row, column, character, count, *attrs) -> None:
        self._check_span(row, column, count)

    def vline(self, row, column, character, count, *attrs) -> None:
        assert 0 <= column < self.width
        assert 0 <= row < self.height
        assert count >= 0
        assert row + count <= self.height

    def refresh(self) -> None:
        pass

    def timeout(self, value: int) -> None:
        pass

    def getch(self) -> int:
        return ord("q")

    def _check_span(self, row: int, column: int, count: int) -> None:
        assert 0 <= row < self.height
        assert 0 <= column < self.width
        assert count >= 0
        assert column + count <= self.width


def _provide_acs_characters(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, character in {
        "ACS_ULCORNER": "+",
        "ACS_URCORNER": "+",
        "ACS_LLCORNER": "+",
        "ACS_LRCORNER": "+",
        "ACS_HLINE": "-",
        "ACS_VLINE": "|",
    }.items():
        monkeypatch.setattr(curses, name, character, raising=False)


@pytest.mark.parametrize(
    ("height", "width"),
    [(8, 33), (9, 34), (24, 80), (30, 100), (50, 160)],
    ids=["small-fallback", "minimum-frame", "vt100", "xterm", "wide-xterm"],
)
def test_wait_dialog_stays_within_terminal_bounds(
    monkeypatch: pytest.MonkeyPatch,
    height: int,
    width: int,
) -> None:
    monkeypatch.setattr(curses, "has_colors", lambda: False)
    _provide_acs_characters(monkeypatch)
    window = StrictWindow(height, width)
    app = CursesApp([], bind=object())
    indicator = WaitIndicator.start("Odświeżanie stref", clock=lambda: 1.0)

    app._draw_wait_box(window, title="Odświeżanie stref", indicator=indicator)

    assert window.writes


@pytest.mark.parametrize(
    ("height", "width"),
    [(12, 40), (24, 80), (30, 100), (50, 160)],
    ids=["compact", "vt100", "xterm", "wide-xterm"],
)
def test_message_view_stays_within_terminal_bounds(
    monkeypatch: pytest.MonkeyPatch,
    height: int,
    width: int,
) -> None:
    monkeypatch.setattr(curses, "has_colors", lambda: False)
    window = StrictWindow(height, width)
    app = CursesApp([], bind=object())

    assert not app._message_view(
        window,
        title="Wynik transakcji",
        lines=[
            "Walidacja konfiguracji zakończona poprawnie.",
            "Długi komunikat operacyjny powinien zostać bezpiecznie zawinięty "
            "niezależnie od szerokości terminala.",
        ],
    )
    assert window.writes


@pytest.mark.parametrize(
    ("encoding", "expected_frames"),
    [
        ("UTF-8", BRAILLE_FRAMES),
        ("utf8", BRAILLE_FRAMES),
        ("ANSI_X3.4-1968", ASCII_FRAMES),
        (None, ASCII_FRAMES),
    ],
    ids=["utf-8", "utf8-alias", "ascii", "unknown"],
)
def test_wait_indicator_matches_terminal_encoding(
    monkeypatch: pytest.MonkeyPatch,
    encoding: str | None,
    expected_frames: tuple[str, ...],
) -> None:
    monkeypatch.setattr(
        curses_app,
        "sys",
        SimpleNamespace(stdout=SimpleNamespace(encoding=encoding)),
    )

    assert CursesApp._new_wait_indicator("Test").frames == expected_frames


@pytest.mark.parametrize(
    ("profile", "sequence", "expected"),
    [
        ("xterm-home", b"[H", curses.KEY_HOME),
        ("xterm-end", b"[F", curses.KEY_END),
        ("vt100-home", b"OH", curses.KEY_HOME),
        ("vt100-end", b"OF", curses.KEY_END),
        ("linux-home", b"[1~", curses.KEY_HOME),
        ("linux-end", b"[4~", curses.KEY_END),
        ("rxvt-home", b"[7~", curses.KEY_HOME),
        ("rxvt-end", b"[8~", curses.KEY_END),
    ],
)
def test_home_end_sequences_from_common_terminal_profiles(
    profile: str,
    sequence: bytes,
    expected: int,
) -> None:
    assert profile
    assert CursesApp._function_key_sequence(list(sequence)) == expected
