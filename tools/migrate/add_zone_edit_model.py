from __future__ import annotations

import ast
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

MODEL_FILE = ROOT / "src/elkman_dns/core/zone_model.py"
TEST_FILE = ROOT / "tests/test_zone_model.py"


MODEL_SOURCE = '''from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .zone_parser import DNSRecord


class ChangeKind(str, Enum):
    ADD = "add"
    MODIFY = "modify"
    DELETE = "delete"


@dataclass(slots=True, frozen=True)
class ZoneChange:
    kind: ChangeKind
    before: DNSRecord | None
    after: DNSRecord | None

    @property
    def record(self) -> DNSRecord:
        if self.after is not None:
            return self.after

        if self.before is not None:
            return self.before

        raise RuntimeError("Zmiana nie zawiera rekordu")


@dataclass(slots=True)
class _RecordEntry:
    identifier: int
    original: DNSRecord | None
    current: DNSRecord | None


class ZoneModel:
    """
    Bufor edycji rekordów pojedynczej strefy.

    Model nie zapisuje plików i nie wykonuje poleceń systemowych.
    Przechowuje jedynie stan początkowy, bieżący i wyliczony diff.
    """

    def __init__(
        self,
        zone_name: str,
        records: Iterable[DNSRecord],
    ) -> None:
        self.zone_name = zone_name.rstrip(".")

        self._entries: list[_RecordEntry] = []
        self._next_identifier = 1

        for record in records:
            self._entries.append(
                _RecordEntry(
                    identifier=self._allocate_identifier(),
                    original=record,
                    current=record,
                )
            )

    def _allocate_identifier(self) -> int:
        identifier = self._next_identifier
        self._next_identifier += 1
        return identifier

    def _visible_entries(self) -> list[_RecordEntry]:
        return [
            entry
            for entry in self._entries
            if entry.current is not None
        ]

    def _entry_at(self, index: int) -> _RecordEntry:
        entries = self._visible_entries()

        if index < 0 or index >= len(entries):
            raise IndexError(
                f"Indeks rekordu poza zakresem: {index}"
            )

        return entries[index]

    @property
    def records(self) -> tuple[DNSRecord, ...]:
        return tuple(
            entry.current
            for entry in self._entries
            if entry.current is not None
        )

    @property
    def original_records(self) -> tuple[DNSRecord, ...]:
        return tuple(
            entry.original
            for entry in self._entries
            if entry.original is not None
        )

    @property
    def pending_changes(self) -> tuple[ZoneChange, ...]:
        changes: list[ZoneChange] = []

        for entry in self._entries:
            before = entry.original
            after = entry.current

            if before is None and after is None:
                continue

            if before is None and after is not None:
                changes.append(
                    ZoneChange(
                        kind=ChangeKind.ADD,
                        before=None,
                        after=after,
                    )
                )
                continue

            if before is not None and after is None:
                changes.append(
                    ZoneChange(
                        kind=ChangeKind.DELETE,
                        before=before,
                        after=None,
                    )
                )
                continue

            if before != after:
                changes.append(
                    ZoneChange(
                        kind=ChangeKind.MODIFY,
                        before=before,
                        after=after,
                    )
                )

        return tuple(changes)

    @property
    def dirty(self) -> bool:
        return bool(self.pending_changes)

    @property
    def change_count(self) -> int:
        return len(self.pending_changes)

    def add(self, record: DNSRecord) -> int:
        entry = _RecordEntry(
            identifier=self._allocate_identifier(),
            original=None,
            current=record,
        )

        self._entries.append(entry)

        return len(self.records) - 1

    def replace(
        self,
        index: int,
        record: DNSRecord,
    ) -> DNSRecord:
        entry = self._entry_at(index)

        previous = entry.current

        if previous is None:
            raise RuntimeError(
                "Nie można edytować usuniętego rekordu"
            )

        entry.current = record
        return previous

    def delete(self, index: int) -> DNSRecord:
        entry = self._entry_at(index)

        previous = entry.current

        if previous is None:
            raise RuntimeError(
                "Rekord jest już usunięty"
            )

        entry.current = None

        # Dodanie, a następnie usunięcie nowego rekordu
        # nie powinno pozostawiać zmiany oczekującej.
        if entry.original is None:
            self._entries.remove(entry)

        return previous

    def discard(self) -> None:
        restored: list[_RecordEntry] = []

        for entry in self._entries:
            if entry.original is None:
                continue

            entry.current = entry.original
            restored.append(entry)

        self._entries = restored

    def accept(self) -> None:
        """
        Uznaje aktualny stan za nowy stan bazowy.

        Metoda będzie używana dopiero po udanym zapisie transakcji.
        """
        accepted: list[_RecordEntry] = []

        for entry in self._entries:
            if entry.current is None:
                continue

            entry.original = entry.current
            accepted.append(entry)

        self._entries = accepted
'''


TEST_SOURCE = '''from __future__ import annotations

import unittest

from elkman_dns.core.zone_model import (
    ChangeKind,
    ZoneModel,
)
from elkman_dns.core.zone_parser import DNSRecord


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
            "\\"temporary\\"",
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
'''


def backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = path.with_name(
        f"{path.name}.bak-{stamp}"
    )
    shutil.copy2(path, destination)
    return destination


def write_file(
    path: Path,
    content: str,
) -> None:
    ast.parse(content, filename=str(path))

    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        backup_path = backup(path)
        print(f"Backup: {backup_path}")

    path.write_text(content, encoding="utf-8")
    print(f"OK: zapisano {path}")


def main() -> None:
    write_file(MODEL_FILE, MODEL_SOURCE)
    write_file(TEST_FILE, TEST_SOURCE)

    print("OK: model edycji strefy został wdrożony")


if __name__ == "__main__":
    main()
