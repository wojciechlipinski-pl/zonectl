"""Read-only inventory and plans for migrating legacy BIND declarations."""

from __future__ import annotations

import difflib
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .discovery import BindConfigDiscovery, BindDiscoveryError, ZoneConfig
from .zone_lifecycle import ZoneLifecycleError, normalize_zone_name


class ManagedZoneMigrationError(RuntimeError):
    """A migration cannot be planned without violating a safety rule."""


@dataclass(frozen=True, slots=True)
class ManagedZoneInventoryItem:
    name: str
    zone_type: str
    config_file: Path
    source_file: Path | None
    state: str
    migratable: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["config_file"] = str(self.config_file)
        payload["source_file"] = (
            str(self.source_file) if self.source_file else None
        )
        return payload


@dataclass(frozen=True, slots=True)
class ManagedZoneMigrationPlan:
    zone: str
    source_config: Path
    managed_config: Path
    declaration_file: Path
    declaration_text: str
    source_original: str
    managed_original: str
    source_candidate: str
    managed_candidate: str
    source_diff: str
    declaration_diff: str
    managed_diff: str
    actions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        for field in ("source_config", "managed_config", "declaration_file"):
            payload[field] = str(payload[field])
        payload["actions"] = list(self.actions)
        return payload


@dataclass(frozen=True, slots=True)
class _ZoneSpan:
    name: str
    start: int
    end: int
    text: str


class ManagedZoneMigrationPlanner:
    """Build migration inventory and unified diffs without writing files."""

    _zone_start_re = re.compile(
        r'\bzone\s+["\'](?P<name>[^"\']+)["\']\s*(?:IN\s*)?\{',
        re.IGNORECASE,
    )
    _include_re = re.compile(
        r'\binclude\s+["\'](?P<path>[^"\']+)["\']\s*;',
        re.IGNORECASE,
    )

    def __init__(
        self,
        *,
        root_config: Path = Path("/etc/bind/named.conf"),
        local_config: Path = Path("/etc/bind/named.conf.local"),
        managed_config: Path = Path("/etc/bind/zonectl-zones.conf"),
        managed_zone_directory: Path = Path("/etc/bind/zonectl-zones.d"),
    ) -> None:
        self.root_config = root_config.expanduser().resolve()
        self.local_config = local_config.expanduser().resolve()
        self.managed_config = managed_config.expanduser().resolve()
        self.managed_zone_directory = (
            managed_zone_directory.expanduser().resolve()
        )

    def inventory(self) -> tuple[ManagedZoneInventoryItem, ...]:
        result = self._discover()
        counts: dict[str, int] = {}
        for zone in result.zones:
            key = self._key(zone.name)
            counts[key] = counts.get(key, 0) + 1

        items = [
            self._inventory_item(zone, counts[self._key(zone.name)])
            for zone in result.zones
        ]
        return tuple(
            sorted(
                items,
                key=lambda item: (
                    item.name.casefold(),
                    str(item.config_file).casefold(),
                ),
            )
        )

    def plan(self, zone_name: str) -> ManagedZoneMigrationPlan:
        try:
            wanted = normalize_zone_name(zone_name)
        except ZoneLifecycleError as exc:
            raise ManagedZoneMigrationError(str(exc)) from exc

        result = self._discover()
        matches = [
            zone for zone in result.zones if self._key(zone.name) == wanted
        ]
        if not matches:
            raise ManagedZoneMigrationError(
                f"Nie znaleziono aktywnej strefy: {wanted}"
            )
        if len(matches) != 1:
            locations = ", ".join(str(item.config_file) for item in matches)
            raise ManagedZoneMigrationError(
                f"Strefa {wanted} ma kilka aktywnych deklaracji: {locations}"
            )

        zone = matches[0]
        item = self._inventory_item(zone, 1)
        if not item.migratable:
            raise ManagedZoneMigrationError(
                f"Migracja strefy {wanted} jest zablokowana: {item.reason}"
            )

        if not self.local_config.is_file():
            raise ManagedZoneMigrationError(
                f"Nie istnieje plik źródłowy: {self.local_config}"
            )
        if not self.managed_config.is_file():
            raise ManagedZoneMigrationError(
                f"Nie istnieje indeks ZoneCTL: {self.managed_config}"
            )
        if not self.managed_zone_directory.is_dir():
            raise ManagedZoneMigrationError(
                "Nie istnieje katalog deklaracji ZoneCTL: "
                f"{self.managed_zone_directory}"
            )

        declaration_file = self.managed_zone_directory / f"{wanted}.conf"
        if declaration_file.exists():
            raise ManagedZoneMigrationError(
                f"Docelowa deklaracja już istnieje: {declaration_file}"
            )

        local_text = self._read(self.local_config)
        spans = [
            span
            for span in self._zone_spans(local_text, self.local_config)
            if self._key(span.name) == wanted
        ]
        if len(spans) != 1:
            raise ManagedZoneMigrationError(
                f"Nie można jednoznacznie wydzielić bloku strefy {wanted}"
            )

        managed_text = self._read(self.managed_config)
        included = self._included_paths(managed_text, self.managed_config.parent)
        if declaration_file.resolve() in included:
            raise ManagedZoneMigrationError(
                f"Indeks zawiera już include: {declaration_file}"
            )

        span = spans[0]
        source_candidate = local_text[: span.start] + local_text[span.end :]
        declaration_text = span.text.rstrip() + "\n"
        managed_candidate = self._append_include(managed_text, declaration_file)

        source_diff = self._diff(
            local_text,
            source_candidate,
            str(self.local_config),
            f"{self.local_config} (kandydat po migracji)",
        )
        declaration_diff = self._diff(
            "",
            declaration_text,
            "/dev/null",
            str(declaration_file),
        )
        managed_diff = self._diff(
            managed_text,
            managed_candidate,
            str(self.managed_config),
            f"{self.managed_config} (kandydat po migracji)",
        )

        return ManagedZoneMigrationPlan(
            zone=wanted,
            source_config=self.local_config,
            managed_config=self.managed_config,
            declaration_file=declaration_file,
            declaration_text=declaration_text,
            source_original=local_text,
            managed_original=managed_text,
            source_candidate=source_candidate,
            managed_candidate=managed_candidate,
            source_diff=source_diff,
            declaration_diff=declaration_diff,
            managed_diff=managed_diff,
            actions=(
                f"wykonaj backup {self.local_config}",
                f"wykonaj backup {self.managed_config}",
                f"utwórz {declaration_file} z niezmienionym blokiem strefy",
                f"usuń blok strefy z {self.local_config}",
                f"dodaj jeden include do {self.managed_config}",
                "wykonaj named-checkconf na konfiguracji kandydackiej",
                "zastosuj pliki atomowo i wykonaj rndc reconfig",
                f"potwierdź strefę {wanted} przez rndc zonestatus",
                "po każdym błędzie przywróć wszystkie pliki z backupu",
            ),
        )

    def _discover(self):
        try:
            return BindConfigDiscovery(self.root_config).discover()
        except BindDiscoveryError as exc:
            raise ManagedZoneMigrationError(str(exc)) from exc

    def _inventory_item(
        self, zone: ZoneConfig, duplicate_count: int
    ) -> ManagedZoneInventoryItem:
        config_file = zone.config_file.resolve()
        if duplicate_count > 1:
            state, migratable, reason = (
                "DUPLICATE",
                False,
                "strefa ma kilka aktywnych deklaracji",
            )
        elif config_file.parent == self.managed_zone_directory:
            state, migratable, reason = (
                "MANAGED",
                False,
                "deklaracja znajduje się już w zonectl-zones.d",
            )
        elif config_file != self.local_config:
            state, migratable, reason = (
                "EXTERNAL_INCLUDE",
                False,
                f"deklaracja pochodzi z innego pliku: {config_file}",
            )
        elif self._is_rpz(zone):
            state, migratable, reason = (
                "BLOCKED_RPZ",
                False,
                "automatyczna lub jawna strefa RPZ",
            )
        elif zone.dnssec_enabled:
            state, migratable, reason = (
                "BLOCKED_DNSSEC",
                False,
                "strefa używa dnssec-policy lub inline-signing",
            )
        elif zone.is_secondary:
            state, migratable, reason = (
                "BLOCKED_SECONDARY",
                False,
                "strefa secondary wymaga osobnego profilu migracji",
            )
        elif zone.is_primary:
            state, migratable, reason = (
                "LEGACY_PRIMARY",
                True,
                "strefa primary może otrzymać plan migracji",
            )
        else:
            state, migratable, reason = (
                "BLOCKED_TYPE",
                False,
                f"nieobsługiwany typ strefy: {zone.zone_type}",
            )

        return ManagedZoneInventoryItem(
            name=zone.name,
            zone_type=zone.zone_type,
            config_file=config_file,
            source_file=zone.source_file,
            state=state,
            migratable=migratable,
            reason=reason,
        )

    @staticmethod
    def _is_rpz(zone: ZoneConfig) -> bool:
        name = zone.name.casefold()
        parts = {part.casefold() for part in zone.config_file.parts}
        return "rpz" in name or "rpz" in parts

    @staticmethod
    def _key(name: str) -> str:
        return name.strip().rstrip(".").casefold()

    @staticmethod
    def _read(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise ManagedZoneMigrationError(
                f"Nie można odczytać {path}: {exc}"
            ) from exc

    @classmethod
    def _zone_spans(cls, raw: str, source: Path) -> tuple[_ZoneSpan, ...]:
        masked = cls._mask_comments(raw)
        spans: list[_ZoneSpan] = []
        position = 0
        while True:
            match = cls._zone_start_re.search(masked, position)
            if match is None:
                break
            opening = masked.find("{", match.start(), match.end())
            closing = BindConfigDiscovery._find_block_end(masked, opening, source)
            semicolon = closing + 1
            while semicolon < len(masked) and masked[semicolon].isspace():
                if masked[semicolon] in "\r\n":
                    break
                semicolon += 1
            if semicolon >= len(masked) or masked[semicolon] != ";":
                raise ManagedZoneMigrationError(
                    f"Brak średnika po strefie {match.group('name')} w {source}"
                )
            end = semicolon + 1
            if raw[end : end + 2] == "\r\n":
                end += 2
            elif raw[end : end + 1] == "\n":
                end += 1
            spans.append(
                _ZoneSpan(
                    name=match.group("name").rstrip("."),
                    start=match.start(),
                    end=end,
                    text=raw[match.start() : semicolon + 1],
                )
            )
            position = end
        return tuple(spans)

    @staticmethod
    def _mask_comments(text: str) -> str:
        output = list(text)
        index = 0
        quote: str | None = None
        escaped = False
        while index < len(text):
            char = text[index]
            following = text[index + 1] if index + 1 < len(text) else ""
            if quote is not None:
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
            if char == "/" and following == "/":
                while index < len(text) and text[index] != "\n":
                    output[index] = " "
                    index += 1
                continue
            if char == "/" and following == "*":
                output[index] = output[index + 1] = " "
                index += 2
                while index < len(text):
                    if text[index : index + 2] == "*/":
                        output[index] = output[index + 1] = " "
                        index += 2
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

    @classmethod
    def _included_paths(cls, text: str, parent: Path) -> set[Path]:
        masked = cls._mask_comments(text)
        paths: set[Path] = set()
        for match in cls._include_re.finditer(masked):
            path = Path(match.group("path")).expanduser()
            if not path.is_absolute():
                path = parent / path
            paths.add(path.resolve())
        return paths

    @staticmethod
    def _append_include(text: str, declaration: Path) -> str:
        candidate = text
        if candidate and not candidate.endswith("\n"):
            candidate += "\n"
        return candidate + f'include "{declaration}";\n'

    @staticmethod
    def _diff(before: str, after: str, source: str, target: str) -> str:
        return "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=source,
                tofile=target,
            )
        )
