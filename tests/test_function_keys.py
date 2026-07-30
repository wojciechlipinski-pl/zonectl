import curses

from zonectl.ui.curses_app import CursesApp


def decode(text: bytes) -> int | None:
    return CursesApp._function_key_sequence(list(text))


def test_xterm_function_keys_are_decoded() -> None:
    assert decode(b"OP") == curses.KEY_F1
    assert decode(b"[12~") == curses.KEY_F2
    assert decode(b"[18~") == curses.KEY_F7
    assert decode(b"[21~") == curses.KEY_F10
    assert decode(b"[24~") == curses.KEY_F12


def test_linux_console_function_keys_are_decoded() -> None:
    assert decode(b"[[A") == curses.KEY_F1
    assert decode(b"[[B") == curses.KEY_F2
    assert decode(b"[[C") == curses.KEY_F3
    assert decode(b"[[D") == curses.KEY_F4
    assert decode(b"[[E") == curses.KEY_F5


def test_unknown_escape_sequence_is_not_function_key() -> None:
    assert decode(b"[99~") is None
