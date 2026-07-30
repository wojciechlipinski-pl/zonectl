from __future__ import annotations

import unittest

from zonectl.ui.dialogs import CursesDialogs


class FakeConfirmWindow:
    def __init__(self, key: int) -> None:
        self.key = key
        self.timeouts: list[int] = []

    def getmaxyx(self) -> tuple[int, int]:
        return (24, 100)

    def move(self, *args) -> None:
        pass

    def clrtoeol(self) -> None:
        pass

    def addnstr(self, *args) -> None:
        pass

    def refresh(self) -> None:
        pass

    def timeout(self, value: int) -> None:
        self.timeouts.append(value)

    def getch(self) -> int:
        return self.key


class CursesDialogsTests(unittest.TestCase):
    def test_normalize_query_strips_whitespace(self) -> None:
        self.assertEqual(
            CursesDialogs.normalize_query("  elk.pl  "),
            "elk.pl",
        )

    def test_normalize_query_removes_outer_wildcards(self) -> None:
        self.assertEqual(
            CursesDialogs.normalize_query("*elk.pl"),
            "elk.pl",
        )
        self.assertEqual(
            CursesDialogs.normalize_query("elk.pl*"),
            "elk.pl",
        )
        self.assertEqual(
            CursesDialogs.normalize_query("*elk.pl*"),
            "elk.pl",
        )

    def test_normalize_query_keeps_internal_wildcard(self) -> None:
        self.assertEqual(
            CursesDialogs.normalize_query("elk*.pl"),
            "elk*.pl",
        )

    def test_normalize_empty_query(self) -> None:
        self.assertEqual(
            CursesDialogs.normalize_query("   "),
            "",
        )
        self.assertEqual(
            CursesDialogs.normalize_query("***"),
            "",
        )

    def test_confirm_waits_for_explicit_yes(self) -> None:
        window = FakeConfirmWindow(ord("t"))

        self.assertTrue(
            CursesDialogs.confirm(
                window,
                "Kontynuować?",
            )
        )
        self.assertEqual(window.timeouts, [-1, 150])

    def test_confirm_defaults_to_no(self) -> None:
        window = FakeConfirmWindow(ord("n"))

        self.assertFalse(
            CursesDialogs.confirm(
                window,
                "Kontynuować?",
            )
        )
        self.assertEqual(window.timeouts, [-1, 150])


if __name__ == "__main__":
    unittest.main()
