from __future__ import annotations

import curses


FUNCTION_KEY_SEQUENCES: dict[bytes, int] = {
    b"OP": curses.KEY_F1,
    b"OQ": curses.KEY_F2,
    b"OR": curses.KEY_F3,
    b"OS": curses.KEY_F4,
    b"[[A": curses.KEY_F1,
    b"[[B": curses.KEY_F2,
    b"[[C": curses.KEY_F3,
    b"[[D": curses.KEY_F4,
    b"[[E": curses.KEY_F5,
    b"[11~": curses.KEY_F1,
    b"[12~": curses.KEY_F2,
    b"[13~": curses.KEY_F3,
    b"[14~": curses.KEY_F4,
    b"[15~": curses.KEY_F5,
    b"[17~": curses.KEY_F6,
    b"[18~": curses.KEY_F7,
    b"[19~": curses.KEY_F8,
    b"[20~": curses.KEY_F9,
    b"[21~": curses.KEY_F10,
    b"[23~": curses.KEY_F11,
    b"[24~": curses.KEY_F12,
}


def decode_function_key(
    sequence: list[int],
) -> int | None:
    """Rozpoznaj sekwencję funkcyjną xterm lub PuTTY/Linux."""
    return FUNCTION_KEY_SEQUENCES.get(bytes(sequence))
