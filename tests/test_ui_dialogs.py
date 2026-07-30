from __future__ import annotations

import unittest

from zonectl.ui.dialogs import CursesDialogs


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


if __name__ == "__main__":
    unittest.main()
