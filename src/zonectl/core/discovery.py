"""Automatyczne wykrywanie stref i plików źródłowych BIND."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


DEFAULT_NAMED_CONF = Path("/etc/bind/named.conf")


class BindDiscoveryError(RuntimeError):
    """Błąd odczytu lub interpretacji konfiguracji BIND."""


@dataclass(frozen=True, slots=True)
class ZoneConfig:
    """Konfiguracja pojedynczej strefy wykryta z konfiguracji BIND."""

    name: str
    zone_type: str
    source_file: Path | None
    config_file: Path

    dnssec_policy: str | None = None
    inline_signing: bool = False
    key_directory: Path | None = None

    journal_file: Path | None = None
    signed_file: Path | None = None
    signed_journal_file: Path | None = None

    source_exists: bool = False
    source_writable: bool = False
    journal_exists: bool = False
    signed_exists: bool = False
    signed_journal_exists: bool = False

    @property
    def is_primary(self) -> bool:
        return self.zone_type in {"master", "primary"}

    @property
    def is_secondary(self) -> bool:
        return self.zone_type in {"slave", "secondary"}

    @property
    def dnssec_enabled(self) -> bool:
        return bool(self.dnssec_policy or self.inline_signing)

    @property
    def editable(self) -> bool:
        return (
            self.is_primary
            and self.source_file is not None
            and self.source_exists
            and self.source_writable
            and not self.is_managed_signed_file
        )

    @property
    def is_managed_signed_file(self) -> bool:
        if self.source_file is None:
            return False

        name = self.source_file.name.lower()
        return name.endswith(".signed") or name.endswith(".signed.jnl")

    @property
    def requires_freeze(self) -> bool:
        """
        Journal aktywnej strefy oznacza, że zwykła atomowa podmiana
        pliku może być niewystarczająca.

        Sama obecność .signed.jnl nie powoduje ustawienia tej flagi,
        ponieważ jest to journal podpisanej strony inline-signing.
        """
        return self.journal_exists

    @property
    def save_mode(self) -> str:
        if not self.is_primary:
            return "READ_ONLY"

        if self.source_file is None:
            return "NO_SOURCE_FILE"

        if self.is_managed_signed_file:
            return "REJECT_SIGNED_FILE"

        if not self.source_exists:
            return "SOURCE_MISSING"

        if not self.source_writable:
            return "SOURCE_NOT_WRITABLE"

        if self.requires_freeze:
            return "FREEZE_SYNC_REPLACE_THAW"

        return "ATOMIC_REPLACE_RELOAD"


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    """Wynik przejścia przez konfigurację BIND."""

    root_config: Path
    config_files: tuple[Path, ...]
    zones: tuple[ZoneConfig, ...]

    def zone(self, name: str) -> ZoneConfig:
        wanted = name.rstrip(".").casefold()

        matches = [
            zone for zone in self.zones if zone.name.rstrip(".").casefold() == wanted
        ]

        if not matches:
            raise BindDiscoveryError(
                f'Nie znaleziono strefy "{name}" w konfiguracji BIND'
            )

        if len(matches) > 1:
            locations = ", ".join(str(zone.config_file) for zone in matches)
            raise BindDiscoveryError(
                f'Strefa "{name}" ma kilka aktywnych deklaracji: {locations}'
            )

        return matches[0]


@dataclass(frozen=True, slots=True)
class _ConfigSource:
    path: Path
    text: str


class BindConfigDiscovery:
    """Czyta konfigurację BIND, rozwija include i wykrywa strefy."""

    _include_re = re.compile(
        r'\binclude\s+["\'](?P<path>[^"\']+)["\']\s*;',
        re.IGNORECASE,
    )

    _zone_start_re = re.compile(
        r'\bzone\s+["\'](?P<name>[^"\']+)["\']\s*'
        r"(?:IN\s*)?\{",
        re.IGNORECASE,
    )

    _type_re = re.compile(
        r"\btype\s+(?P<value>[A-Za-z_-]+)\s*;",
        re.IGNORECASE,
    )

    _file_re = re.compile(
        r'\bfile\s+["\'](?P<value>[^"\']+)["\']\s*;',
        re.IGNORECASE,
    )

    _dnssec_policy_re = re.compile(
        r"\bdnssec-policy\s+(?P<value>[^;]+?)\s*;",
        re.IGNORECASE,
    )

    _inline_signing_re = re.compile(
        r"\binline-signing\s+(?P<value>yes|no)\s*;",
        re.IGNORECASE,
    )

    _key_directory_re = re.compile(
        r'\bkey-directory\s+["\'](?P<value>[^"\']+)["\']\s*;',
        re.IGNORECASE,
    )

    def __init__(
        self,
        root_config: Path = DEFAULT_NAMED_CONF,
    ) -> None:
        self.root_config = root_config

    def discover(self) -> DiscoveryResult:
        root = self.root_config.expanduser().resolve()

        if not root.is_file():
            raise BindDiscoveryError(
                f"Nie znaleziono głównego pliku konfiguracji BIND: {root}"
            )

        sources: list[_ConfigSource] = []
        visited: set[Path] = set()
        stack: list[Path] = []

        self._load_config_tree(
            path=root,
            sources=sources,
            visited=visited,
            stack=stack,
        )

        zones: list[ZoneConfig] = []

        for source in sources:
            zones.extend(self._parse_zones(source))

        return DiscoveryResult(
            root_config=root,
            config_files=tuple(source.path for source in sources),
            zones=tuple(zones),
        )

    def _load_config_tree(
        self,
        path: Path,
        sources: list[_ConfigSource],
        visited: set[Path],
        stack: list[Path],
    ) -> None:
        path = path.expanduser().resolve()

        if path in stack:
            chain = " -> ".join(str(item) for item in (*stack, path))
            raise BindDiscoveryError(
                f"Wykryto zapętlenie include w konfiguracji BIND: {chain}"
            )

        if path in visited:
            return

        if not path.is_file():
            raise BindDiscoveryError(
                f"Plik wskazany przez include nie istnieje: {path}"
            )

        try:
            raw_text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw_text = path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            raise BindDiscoveryError(
                f"Nie można odczytać konfiguracji BIND {path}: {exc}"
            ) from exc

        text = self._strip_comments(raw_text)

        visited.add(path)
        stack.append(path)
        sources.append(_ConfigSource(path=path, text=text))

        for match in self._include_re.finditer(text):
            include_path = self._resolve_config_path(
                match.group("path"),
                parent=path.parent,
            )

            self._load_config_tree(
                path=include_path,
                sources=sources,
                visited=visited,
                stack=stack,
            )

        stack.pop()

    def _parse_zones(
        self,
        source: _ConfigSource,
    ) -> list[ZoneConfig]:
        zones: list[ZoneConfig] = []
        position = 0

        while True:
            match = self._zone_start_re.search(source.text, position)

            if match is None:
                break

            opening = source.text.find("{", match.start(), match.end())

            if opening < 0:
                raise BindDiscoveryError(
                    f"Nie znaleziono początku bloku strefy w pliku {source.path}"
                )

            closing = self._find_block_end(
                source.text,
                opening,
                source.path,
            )

            body = source.text[opening + 1 : closing]
            name = match.group("name").rstrip(".")

            zone = self._zone_from_block(
                name=name,
                body=body,
                config_file=source.path,
            )

            if zone.zone_type not in {
                "hint",
                "forward",
                "redirect",
                "delegation-only",
            }:
                zones.append(zone)

            position = closing + 1

        return zones

    def _zone_from_block(
        self,
        name: str,
        body: str,
        config_file: Path,
    ) -> ZoneConfig:
        zone_type = (
            self._match_value(
                self._type_re,
                body,
                default="unknown",
            )
            or "unknown"
        ).lower()

        raw_file = self._match_value(
            self._file_re,
            body,
            default=None,
        )

        source_file = (
            self._resolve_zone_path(raw_file, config_file.parent) if raw_file else None
        )

        dnssec_policy = self._match_value(
            self._dnssec_policy_re,
            body,
            default=None,
        )

        inline_signing = (
            self._match_value(
                self._inline_signing_re,
                body,
                default="no",
            )
            or "no"
        ).lower() == "yes"

        raw_key_directory = self._match_value(
            self._key_directory_re,
            body,
            default=None,
        )

        key_directory = (
            self._resolve_zone_path(
                raw_key_directory,
                config_file.parent,
            )
            if raw_key_directory
            else None
        )

        journal_file: Path | None = None
        signed_file: Path | None = None
        signed_journal_file: Path | None = None

        if source_file is not None:
            journal_file = Path(f"{source_file}.jnl")
            signed_file = Path(f"{source_file}.signed")
            signed_journal_file = Path(f"{source_file}.signed.jnl")

        source_exists = bool(source_file is not None and source_file.is_file())

        source_writable = bool(
            source_file is not None
            and (
                os.access(source_file, os.W_OK)
                if source_exists
                else os.access(source_file.parent, os.W_OK)
            )
        )

        journal_exists = bool(journal_file is not None and journal_file.exists())

        signed_exists = bool(signed_file is not None and signed_file.exists())

        signed_journal_exists = bool(
            signed_journal_file is not None and signed_journal_file.exists()
        )

        return ZoneConfig(
            name=name,
            zone_type=zone_type,
            source_file=source_file,
            config_file=config_file,
            dnssec_policy=dnssec_policy,
            inline_signing=inline_signing,
            key_directory=key_directory,
            journal_file=journal_file,
            signed_file=signed_file,
            signed_journal_file=signed_journal_file,
            source_exists=source_exists,
            source_writable=source_writable,
            journal_exists=journal_exists,
            signed_exists=signed_exists,
            signed_journal_exists=signed_journal_exists,
        )

    @staticmethod
    def _match_value(
        pattern: re.Pattern[str],
        text: str,
        default: str | None,
    ) -> str | None:
        match = pattern.search(text)

        if match is None:
            return default

        return match.group("value").strip()

    @staticmethod
    def _resolve_config_path(
        raw_path: str,
        parent: Path,
    ) -> Path:
        path = Path(raw_path).expanduser()

        if not path.is_absolute():
            path = parent / path

        return path.resolve()

    @staticmethod
    def _resolve_zone_path(
        raw_path: str,
        config_parent: Path,
    ) -> Path:
        path = Path(raw_path).expanduser()

        if not path.is_absolute():
            # W BIND ścieżka względna może być liczona względem
            # directory z options. Na tym etapie bezpieczniej jest
            # wskazać lokalizację względem pliku konfiguracji niż
            # zgadywać /var/cache/bind.
            path = config_parent / path

        return path.resolve()

    @staticmethod
    def _find_block_end(
        text: str,
        opening: int,
        source_path: Path,
    ) -> int:
        depth = 0
        quote: str | None = None
        escaped = False

        for index in range(opening, len(text)):
            char = text[index]

            if quote is not None:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None

                continue

            if char in {'"', "'"}:
                quote = char
                continue

            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1

                if depth == 0:
                    return index

        raise BindDiscoveryError(f"Niedomknięty blok konfiguracji w {source_path}")

    @staticmethod
    def _strip_comments(text: str) -> str:
        """
        Usuwa komentarze //, # i /* ... */, ale zachowuje tekst
        wewnątrz cudzysłowów.
        """
        output: list[str] = []
        index = 0
        quote: str | None = None
        escaped = False

        while index < len(text):
            char = text[index]
            following = text[index + 1] if index + 1 < len(text) else ""

            if quote is not None:
                output.append(char)

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
                output.append(char)
                index += 1
                continue

            if char == "/" and following == "/":
                index += 2

                while index < len(text) and text[index] != "\n":
                    index += 1

                continue

            if char == "/" and following == "*":
                index += 2

                while index + 1 < len(text):
                    if text[index] == "*" and text[index + 1] == "/":
                        index += 2
                        break

                    if text[index] == "\n":
                        output.append("\n")

                    index += 1

                continue

            if char == "#":
                while index < len(text) and text[index] != "\n":
                    index += 1

                continue

            output.append(char)
            index += 1

        return "".join(output)
