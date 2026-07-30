from __future__ import annotations

import unittest

from zonectl.ui.records.renderer import RecordRenderer


class RecordRendererTests(unittest.TestCase):
    def test_visible_rows_has_minimum_one(self) -> None:
        self.assertEqual(RecordRenderer.visible_rows(1), 1)

    def test_visible_rows_for_normal_terminal(self) -> None:
        self.assertEqual(RecordRenderer.visible_rows(30), 21)

    def test_summary_without_filter(self) -> None:
        result = RecordRenderer.summary_text(
            visible_count=13,
            total_count=13,
            sort_name="Nazwa",
            change_count=0,
        )
        self.assertEqual(
            result,
            "Rekordy: 13/13   Sortowanie: Nazwa   Zmiany: 0",
        )

    def test_summary_with_filter(self) -> None:
        result = RecordRenderer.summary_text(
            visible_count=2,
            total_count=13,
            sort_name="Typ",
            change_count=3,
            search_query="www",
        )
        self.assertEqual(
            result,
            'Rekordy: 2/13   Sortowanie: Typ   Zmiany: 3   Filtr: "www"',
        )

    def test_footer_contains_main_actions(self) -> None:
        footer = RecordRenderer.footer_text()
        self.assertIn("/ szukaj", footer)
        self.assertIn("n/N następny/poprzedni", footer)
        self.assertIn("c wyczyść", footer)
        self.assertIn("s sortuj", footer)
        self.assertIn("p zmiany", footer)
        self.assertIn("d diff", footer)


if __name__ == "__main__":
    unittest.main()
