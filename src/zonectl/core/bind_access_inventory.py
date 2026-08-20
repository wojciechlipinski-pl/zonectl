"""Read-only inventory of BIND ACLs and named secondary server groups."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .discovery import BindConfigDiscovery, BindDiscoveryError


class BindAccessInventoryError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BindListDefinition:
    kind: str
    name: str
    source: Path
    line: int
    entries: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["source"] = str(self.source)
        data["entries"] = list(self.entries)
        return data


@dataclass(frozen=True, slots=True)
class BindListUsage:
    directive: str
    source: Path
    line: int
    values: tuple[str, ...]
    zone: str | None = None

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["source"] = str(self.source)
        data["values"] = list(self.values)
        return data


@dataclass(frozen=True, slots=True)
class BindAccessInventory:
    definitions: tuple[BindListDefinition, ...]
    usages: tuple[BindListUsage, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "definitions": [item.to_dict() for item in self.definitions],
            "usages": [item.to_dict() for item in self.usages],
        }


class BindAccessInventoryReader:
    _definition = re.compile(
        r'\b(?P<kind>acl|primaries|masters)\s+(?:["\'](?P<quoted>[^"\']+)["\']|(?P<plain>[A-Za-z0-9_.-]+))\s*\{',
        re.IGNORECASE,
    )
    _usage = re.compile(
        r"\b(?P<directive>allow-query|allow-query-cache|allow-recursion|"
        r"allow-transfer|allow-notify|allow-update|"
        r"also-notify|primaries)\s*\{",
        re.IGNORECASE,
    )

    def __init__(self, root_config: Path = Path("/etc/bind/named.conf")) -> None:
        self.root_config = root_config.expanduser().resolve()

    def collect(self) -> BindAccessInventory:
        try:
            files = BindConfigDiscovery(self.root_config).discover().config_files
        except BindDiscoveryError as exc:
            raise BindAccessInventoryError(str(exc)) from exc
        definitions: list[BindListDefinition] = []
        usages: list[BindListUsage] = []
        for source in files:
            raw = source.read_text(encoding="utf-8", errors="replace")
            masked = self._mask_comments(raw)
            definition_ranges: list[tuple[int, int]] = []
            zone_ranges = self._zone_ranges(masked, source)
            for match in self._definition.finditer(masked):
                opening = masked.find("{", match.start(), match.end())
                closing = BindConfigDiscovery._find_block_end(masked, opening, source)
                definition_ranges.append((match.start(), closing + 1))
                definitions.append(
                    BindListDefinition(
                        kind=match.group("kind").casefold(),
                        name=match.group("quoted") or match.group("plain"),
                        source=source,
                        line=raw.count("\n", 0, match.start()) + 1,
                        entries=self._entries(raw[opening + 1 : closing]),
                    )
                )
            for match in self._usage.finditer(masked):
                if any(start <= match.start() < end for start, end in definition_ranges):
                    continue
                opening = masked.find("{", match.start(), match.end())
                closing = BindConfigDiscovery._find_block_end(masked, opening, source)
                usages.append(
                    BindListUsage(
                        directive=match.group("directive").casefold(),
                        source=source,
                        line=raw.count("\n", 0, match.start()) + 1,
                        values=self._entries(raw[opening + 1 : closing]),
                        zone=next(
                            (
                                name
                                for start, end, name in zone_ranges
                                if start <= match.start() < end
                            ),
                            None,
                        ),
                    )
                )
        return BindAccessInventory(
            definitions=tuple(sorted(definitions, key=lambda x: (x.name.casefold(), str(x.source), x.line))),
            usages=tuple(sorted(usages, key=lambda x: (x.directive, str(x.source), x.line))),
        )

    @staticmethod
    def _zone_ranges(text: str, source: Path) -> tuple[tuple[int, int, str], ...]:
        ranges: list[tuple[int, int, str]] = []
        position = 0
        for match in BindConfigDiscovery._zone_start_re.finditer(text):
            if match.start() < position:
                continue
            opening = text.find("{", match.start(), match.end())
            closing = BindConfigDiscovery._find_block_end(text, opening, source)
            ranges.append((match.start(), closing + 1, match.group("name").rstrip(".")))
            position = closing + 1
        return tuple(ranges)

    @staticmethod
    def _entries(body: str) -> tuple[str, ...]:
        cleaned = BindAccessInventoryReader._mask_comments(body)
        return tuple(
            value.strip()
            for value in cleaned.split(";")
            if value.strip()
        )

    @staticmethod
    def _mask_comments(text: str) -> str:
        output = list(text)
        index = 0
        quote: str | None = None
        escaped = False
        while index < len(text):
            char = text[index]
            following = text[index + 1] if index + 1 < len(text) else ""
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                index += 1
                continue
            if char in {'"', "'"}:
                quote = char
                index += 1
                continue
            if char == "/" and following in {"/", "*"}:
                block = following == "*"
                output[index] = output[index + 1] = " "
                index += 2
                while index < len(text):
                    if block and text[index : index + 2] == "*/":
                        output[index] = output[index + 1] = " "
                        index += 2
                        break
                    if not block and text[index] == "\n":
                        break
                    if text[index] not in "\r\n":
                        output[index] = " "
                    index += 1
                continue
            if char == "#":
                while index < len(text) and text[index] != "\n":
                    output[index] = " "
                    index += 1
                continue
            index += 1
        return "".join(output)
