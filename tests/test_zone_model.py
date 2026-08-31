from __future__ import annotations

import unittest

from zonectl.core.zone_model import (
    ChangeKind,
    ZoneModel,
)
from zonectl.core.zone_parser import DNSRecord


def record(
    owner: str,
    rtype: str,
    rdata: str,
    ttl: int = 3600,
) -> DNSRecord:
    raw = f"{owner} {ttl} IN {rtype} {rdata}"

    return DNSRecord(
        owner=owner,
        ttl=ttl,
        rrclass="IN",
        rtype=rtype,
        rdata=rdata,
        raw=raw,
    )


class ZoneModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.www = record(
            "www.example.org.",
            "A",
            "192.0.2.10",
        )
        self.mail = record(
            "mail.example.org.",
            "A",
            "192.0.2.20",
        )

        self.model = ZoneModel(
            "example.org",
            [self.www, self.mail],
        )

    def test_initial_model_is_clean(self) -> None:
        self.assertFalse(self.model.dirty)
        self.assertEqual(self.model.change_count, 0)
        self.assertEqual(
            self.model.records,
            (self.www, self.mail),
        )

    def test_add_record(self) -> None:
        added = record(
            "ftp.example.org.",
            "A",
            "192.0.2.30",
        )

        self.model.add(added)

        self.assertTrue(self.model.dirty)
        self.assertEqual(self.model.change_count, 1)
        self.assertEqual(
            self.model.pending_changes[0].kind,
            ChangeKind.ADD,
        )
        self.assertEqual(
            self.model.pending_changes[0].after,
            added,
        )

    def test_replace_record(self) -> None:
        changed = record(
            "www.example.org.",
            "A",
            "192.0.2.99",
        )

        previous = self.model.replace(0, changed)

        self.assertEqual(previous, self.www)
        self.assertEqual(self.model.records[0], changed)
        self.assertEqual(
            self.model.pending_changes[0].kind,
            ChangeKind.MODIFY,
        )
        self.assertEqual(
            self.model.pending_changes[0].before,
            self.www,
        )
        self.assertEqual(
            self.model.pending_changes[0].after,
            changed,
        )

    def test_delete_record(self) -> None:
        deleted = self.model.delete(1)

        self.assertEqual(deleted, self.mail)
        self.assertEqual(self.model.records, (self.www,))
        self.assertEqual(
            self.model.pending_changes[0].kind,
            ChangeKind.DELETE,
        )

    def test_add_then_delete_cancels_change(self) -> None:
        added = record(
            "temporary.example.org.",
            "TXT",
            '"temporary"',
        )

        index = self.model.add(added)
        self.model.delete(index)

        self.assertFalse(self.model.dirty)
        self.assertEqual(self.model.change_count, 0)

    def test_discard_restores_original_state(self) -> None:
        changed = record(
            "www.example.org.",
            "A",
            "192.0.2.200",
        )
        added = record(
            "new.example.org.",
            "AAAA",
            "2001:db8::10",
        )

        self.model.replace(0, changed)
        self.model.delete(1)
        self.model.add(added)

        self.assertTrue(self.model.dirty)

        self.model.discard()

        self.assertFalse(self.model.dirty)
        self.assertEqual(
            self.model.records,
            (self.www, self.mail),
        )

    def test_accept_sets_new_baseline(self) -> None:
        changed = record(
            "www.example.org.",
            "A",
            "192.0.2.123",
        )

        self.model.replace(0, changed)
        self.assertTrue(self.model.dirty)

        self.model.accept()

        self.assertFalse(self.model.dirty)
        self.assertEqual(
            self.model.original_records,
            (changed, self.mail),
        )


if __name__ == "__main__":
    unittest.main()
