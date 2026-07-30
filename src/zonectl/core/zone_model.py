from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .zone_parser import DNSRecord


class ChangeKind(str, Enum):
    ADD = "add"
    MODIFY = "modify"
    DELETE = "delete"


class ZoneModelReadOnlyError(RuntimeError):
    """Próba zmiany modelu uruchomionego w trybie tylko do odczytu."""


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


@dataclass(slots=True, frozen=True)
class ZoneRecordView:
    """Rekord prezentowany w edytorze wraz ze stanem zmiany."""

    identifier: int
    record: DNSRecord
    change_kind: ChangeKind | None

    @property
    def deleted(self) -> bool:
        return self.change_kind is ChangeKind.DELETE

    @property
    def marker(self) -> str:
        return {
            ChangeKind.ADD: "+",
            ChangeKind.MODIFY: "~",
            ChangeKind.DELETE: "-",
            None: " ",
        }[self.change_kind]


@dataclass(slots=True)
class _RecordEntry:
    identifier: int
    original: DNSRecord | None
    current: DNSRecord | None


@dataclass(slots=True)
class _ModelSnapshot:
    entries: list[_RecordEntry]
    next_identifier: int


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
        *,
        read_only: bool = False,
    ) -> None:
        self.zone_name = zone_name.rstrip(".")
        self.read_only = read_only

        self._entries: list[_RecordEntry] = []
        self._next_identifier = 1
        self._undo_stack: list[_ModelSnapshot] = []

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

    def _snapshot(self) -> _ModelSnapshot:
        return _ModelSnapshot(
            entries=[
                _RecordEntry(
                    identifier=entry.identifier,
                    original=entry.original,
                    current=entry.current,
                )
                for entry in self._entries
            ],
            next_identifier=self._next_identifier,
        )

    def _remember(self) -> None:
        self._undo_stack.append(self._snapshot())

    def _ensure_writable(self) -> None:
        if self.read_only:
            raise ZoneModelReadOnlyError(
                "Tryb tylko do odczytu: modyfikowanie rekordów jest zablokowane"
            )

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
    def record_views(self) -> tuple[ZoneRecordView, ...]:
        """Zwraca rekordy widoczne w edytorze, również usuwane."""

        result: list[ZoneRecordView] = []

        for entry in self._entries:
            before = entry.original
            after = entry.current

            if before is None and after is None:
                continue

            if before is None and after is not None:
                record = after
                kind = ChangeKind.ADD
            elif before is not None and after is None:
                record = before
                kind = ChangeKind.DELETE
            elif before != after:
                assert after is not None
                record = after
                kind = ChangeKind.MODIFY
            else:
                assert after is not None
                record = after
                kind = None

            result.append(
                ZoneRecordView(
                    identifier=entry.identifier,
                    record=record,
                    change_kind=kind,
                )
            )

        return tuple(result)

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

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def add(self, record: DNSRecord) -> int:
        self._ensure_writable()
        self._remember()
        entry = _RecordEntry(
            identifier=self._allocate_identifier(),
            original=None,
            current=record,
        )

        self._entries.append(entry)

        return len(self.records) - 1

    def _entry_by_identifier(self, identifier: int) -> _RecordEntry:
        for entry in self._entries:
            if entry.identifier == identifier:
                return entry

        raise KeyError(
            f"Nie znaleziono rekordu o identyfikatorze: {identifier}"
        )

    def replace_by_identifier(
        self,
        identifier: int,
        record: DNSRecord,
    ) -> DNSRecord:
        self._ensure_writable()
        entry = self._entry_by_identifier(identifier)
        previous = entry.current

        if previous is None:
            raise RuntimeError(
                "Nie można edytować usuniętego rekordu"
            )

        if previous == record:
            return previous

        self._remember()
        entry.current = record
        return previous

    def delete_by_identifier(self, identifier: int) -> DNSRecord:
        self._ensure_writable()
        entry = self._entry_by_identifier(identifier)
        previous = entry.current

        if previous is None:
            raise RuntimeError(
                "Rekord jest już usunięty"
            )

        self._remember()
        entry.current = None

        if entry.original is None:
            self._entries.remove(entry)

        return previous

    def replace(
        self,
        index: int,
        record: DNSRecord,
    ) -> DNSRecord:
        self._ensure_writable()
        entry = self._entry_at(index)

        previous = entry.current

        if previous is None:
            raise RuntimeError(
                "Nie można edytować usuniętego rekordu"
            )

        if previous == record:
            return previous

        self._remember()
        entry.current = record
        return previous

    def delete(self, index: int) -> DNSRecord:
        self._ensure_writable()
        entry = self._entry_at(index)

        previous = entry.current

        if previous is None:
            raise RuntimeError(
                "Rekord jest już usunięty"
            )

        self._remember()
        entry.current = None

        # Dodanie, a następnie usunięcie nowego rekordu
        # nie powinno pozostawiać zmiany oczekującej.
        if entry.original is None:
            self._entries.remove(entry)

        return previous

    def bulk_replace_by_identifiers(
        self,
        replacements: dict[int, DNSRecord],
    ) -> int:
        """Zastąp wiele rekordów jako jeden krok historii cofania."""
        self._ensure_writable()
        pending: list[tuple[_RecordEntry, DNSRecord]] = []

        for identifier, record in replacements.items():
            entry = self._entry_by_identifier(identifier)
            if entry.current is None:
                raise RuntimeError(
                    "Nie można edytować usuniętego rekordu"
                )
            if entry.current != record:
                pending.append((entry, record))

        if not pending:
            return 0

        self._remember()
        for entry, record in pending:
            entry.current = record
        return len(pending)

    def bulk_delete_by_identifiers(
        self,
        identifiers: list[int],
    ) -> int:
        """Usuń wiele rekordów jako jeden krok historii cofania."""
        self._ensure_writable()
        entries: list[_RecordEntry] = []
        seen: set[int] = set()

        for identifier in identifiers:
            if identifier in seen:
                continue
            seen.add(identifier)
            entry = self._entry_by_identifier(identifier)
            if entry.current is not None:
                entries.append(entry)

        if not entries:
            return 0

        self._remember()
        for entry in entries:
            entry.current = None
            if entry.original is None:
                self._entries.remove(entry)
        return len(entries)

    def undo(self) -> bool:
        """Cofnij ostatnią operację wykonaną w modelu."""
        if not self._undo_stack:
            return False

        snapshot = self._undo_stack.pop()
        self._entries = snapshot.entries
        self._next_identifier = snapshot.next_identifier
        return True

    def discard(self) -> None:
        restored: list[_RecordEntry] = []

        for entry in self._entries:
            if entry.original is None:
                continue

            entry.current = entry.original
            restored.append(entry)

        self._entries = restored
        self._undo_stack.clear()

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
        self._undo_stack.clear()
