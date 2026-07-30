from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .zone_parser import DNSRecord


class ZoneNode:
    """Element źródłowego dokumentu strefy."""


@dataclass(slots=True)
class BlankLine(ZoneNode):
    raw: str = ""


@dataclass(slots=True)
class Comment(ZoneNode):
    raw: str

    @property
    def text(self) -> str:
        return self.raw.lstrip()[1:].lstrip()


@dataclass(slots=True)
class Directive(ZoneNode):
    keyword: str
    value: str
    raw: str


@dataclass(slots=True)
class RecordNode(ZoneNode):
    record: DNSRecord
    raw: str
    modified: bool = False
    deleted: bool = False


@dataclass(slots=True)
class RawLine(ZoneNode):
    """
    Linia zachowana bez interpretacji.

    Używana m.in. dla:
    - rekordów wielowierszowych,
    - nieobsługiwanej składni,
    - linii kontynuacji.
    """

    raw: str


@dataclass(slots=True)
class ZoneDocument:
    nodes: list[ZoneNode] = field(default_factory=list)
    source_path: Path | None = None
    trailing_newline: bool = True

    @property
    def records(self) -> list[DNSRecord]:
        return [
            node.record
            for node in self.nodes
            if isinstance(node, RecordNode) and not node.deleted
        ]

    def iter_record_nodes(self) -> Iterable[RecordNode]:
        for node in self.nodes:
            if isinstance(node, RecordNode):
                yield node

    def find_record(
        self,
        record: DNSRecord,
    ) -> RecordNode | None:
        for node in self.iter_record_nodes():
            if node.record == record:
                return node

        return None
