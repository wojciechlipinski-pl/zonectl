from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from .models import Zone


class BindConfigError(RuntimeError):
    """Błąd odczytu lub analizy konfiguracji BIND."""


class BindConfigDiscovery:
    """
    Odczytuje strefy bezpośrednio z konfiguracji BIND.

    Obsługuje:
    - zone "example.org" { ... };
    - rekurencyjne dyrektywy include;
    - konfigurację w named.conf.local;
    - przyszłą strukturę zones.d;
    - wykrywanie pliku strefy, DNSSEC, notify, dns2 i HE.
    """

    ZONE_START = re.compile(
        r'\bzone\s+"(?P<name>[^"]+)"\s*(?:IN\s*)?\{',
        re.IGNORECASE,
    )

    INCLUDE = re.compile(
        r'\binclude\s+"(?P<path>[^"]+)"\s*;',
        re.IGNORECASE,
    )

    FILE = re.compile(
        r'\bfile\s+"(?P<path>[^"]+)"\s*;',
        re.IGNORECASE,
    )

    NOTIFY = re.compile(
        r'\bnotify\s+(?P<value>yes|no|explicit|master-only|primary-only)\s*;',
        re.IGNORECASE,
    )

    TYPE = re.compile(
        r'\btype\s+(?P<value>[a-z0-9_-]+)\s*;',
        re.IGNORECASE,
    )

    def __init__(self, root: Path = Path("/etc/bind/named.conf.local")):
        self.root = root.resolve()
        self._visited: set[Path] = set()

    def zones(self) -> list[Zone]:
        """Zwróć wszystkie strefy znalezione w konfiguracji BIND."""
        self._visited.clear()

        discovered: dict[str, Zone] = {}
        self._read_file(self.root, discovered)

        return sorted(discovered.values(), key=lambda zone: zone.name.casefold())

    def _read_file(self, path: Path, discovered: dict[str, Zone]) -> None:
        path = path.resolve()

        if path in self._visited:
            return

        self._visited.add(path)

        if not path.is_file():
            raise BindConfigError(f"Nie istnieje plik konfiguracji BIND: {path}")

        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            original = path.read_text(encoding="latin-1")
        except OSError as exc:
            raise BindConfigError(f"Nie można odczytać {path}: {exc}") from exc

        text = self._strip_comments(original)

        # Najpierw analizujemy strefy z aktualnego pliku.
        for name, block in self._zone_blocks(text, path):
            key = name.rstrip(".").casefold()

            if key in discovered:
                raise BindConfigError(
                    f"Strefa {name} została zdefiniowana więcej niż raz "
                    f"(kolejna definicja w {path})"
                )

            discovered[key] = self._zone_from_block(name, block, path)

        # Następnie przechodzimy rekurencyjnie po include.
        for match in self.INCLUDE.finditer(text):
            include_path = self._resolve_include(path, match.group("path"))
            self._read_file(include_path, discovered)

    @staticmethod
    def _resolve_include(parent_file: Path, raw_path: str) -> Path:
        include_path = Path(raw_path)

        if include_path.is_absolute():
            return include_path.resolve()

        return (parent_file.parent / include_path).resolve()

    def _zone_blocks(
        self,
        text: str,
        source: Path,
    ) -> Iterator[tuple[str, str]]:
        position = 0

        while True:
            match = self.ZONE_START.search(text, position)
            if match is None:
                return

            name = match.group("name").strip().rstrip(".")
            opening_brace = text.find("{", match.start(), match.end())

            if opening_brace < 0:
                raise BindConfigError(
                    f"Nie znaleziono początku bloku strefy {name} w {source}"
                )

            closing_brace = self._matching_brace(text, opening_brace)

            if closing_brace is None:
                raise BindConfigError(
                    f"Niedomknięty blok strefy {name} w {source}"
                )

            block = text[opening_brace + 1 : closing_brace]

            semicolon = closing_brace + 1
            while semicolon < len(text) and text[semicolon].isspace():
                semicolon += 1

            if semicolon >= len(text) or text[semicolon] != ";":
                raise BindConfigError(
                    f"Brak średnika po definicji strefy {name} w {source}"
                )

            yield name, block
            position = semicolon + 1

    @staticmethod
    def _matching_brace(text: str, opening: int) -> int | None:
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

        return None

    def _zone_from_block(self, name: str, block: str, source: Path) -> Zone:
        file_match = self.FILE.search(block)
        type_match = self.TYPE.search(block)
        notify_match = self.NOTIFY.search(block)

        zone_file: Path | None = None

        if file_match:
            raw_file = file_match.group("path")
            candidate = Path(raw_file)

            if candidate.is_absolute():
                zone_file = candidate
            else:
                zone_file = (source.parent / candidate).resolve()

        zone_type = (
            type_match.group("value").casefold()
            if type_match
            else "master"
        )

        notify = True
        if notify_match:
            notify = notify_match.group("value").casefold() != "no"

        lowered = block.casefold()

        dns2 = any(
            marker in lowered
            for marker in (
                "dns2-transfer",
                "dns2-notify",
            )
        )

        he = any(
            marker in lowered
            for marker in (
                "he-transfer",
                "he-notify",
            )
        )

        group = self._group_for(name, source, block)

        # Strefy secondary/slave nie powinny być traktowane jak lokalne
        # strefy edytowalne.
        reload_enabled = zone_type in {"master", "primary"}

        return Zone(
            name=name,
            file=zone_file,
            enabled=True,
            dns2=dns2,
            he=he,
            notify=notify,
            reload=reload_enabled,
            group=group,
        )

    @staticmethod
    def _group_for(name: str, source: Path, block: str) -> str:
        normalized = name.casefold()
        source_parts = {part.casefold() for part in source.parts}
        lowered = block.casefold()

        if normalized.endswith(".in-addr.arpa") or normalized.endswith(".ip6.arpa"):
            return "Strefy odwrotne"

        if (
            "rpz" in normalized
            or "response-policy" in lowered
            or "rpz" in source_parts
        ):
            return "RPZ"

        if "reverse" in source_parts:
            return "Strefy odwrotne"

        if "internal" in source_parts or "local" in source_parts:
            return "Wewnętrzne"

        return "Publiczne"

    @staticmethod
    def _strip_comments(text: str) -> str:
        """
        Usuń komentarze //, # i /* ... */ bez niszczenia tekstu
        znajdującego się wewnątrz cudzysłowów.
        """
        output: list[str] = []
        index = 0
        quote: str | None = None
        escaped = False
        length = len(text)

        while index < length:
            char = text[index]
            next_char = text[index + 1] if index + 1 < length else ""

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

            if char == "/" and next_char == "/":
                output.extend((" ", " "))
                index += 2

                while index < length and text[index] != "\n":
                    output.append(" ")
                    index += 1

                continue

            if char == "/" and next_char == "*":
                output.extend((" ", " "))
                index += 2

                while index < length:
                    if (
                        text[index] == "*"
                        and index + 1 < length
                        and text[index + 1] == "/"
                    ):
                        output.extend((" ", " "))
                        index += 2
                        break

                    output.append("\n" if text[index] == "\n" else " ")
                    index += 1

                continue

            if char == "#":
                output.append(" ")
                index += 1

                while index < length and text[index] != "\n":
                    output.append(" ")
                    index += 1

                continue

            output.append(char)
            index += 1

        return "".join(output)
