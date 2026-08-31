from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .zone_document import (
    BlankLine,
    Comment,
    Directive,
    RawLine,
    RecordNode,
    ZoneDocument,
)
from .zone_parser import DNSRecord


class ZoneFileParseError(RuntimeError):
    """Błąd odczytu źródłowego pliku strefy."""


@dataclass(slots=True, frozen=True)
class _Token:
    value: str
    start: int
    end: int


class ZoneFileParser:
    """
    Zachowujący formatowanie parser źródłowego pliku strefy.

    Parser interpretuje bezpieczne rekordy jednowierszowe. Linie,
    których nie potrafi jednoznacznie rozpoznać, zapisuje jako RawLine.

    Dzięki temu żadna część źródłowego pliku nie jest tracona.
    """

    DNS_CLASSES = {
        "IN",
        "CH",
        "CHAOS",
        "HS",
        "HESIOD",
    }

    COMMON_TYPES = {
        "A",
        "AAAA",
        "AFSDB",
        "CAA",
        "CERT",
        "CNAME",
        "DNAME",
        "DNSKEY",
        "DS",
        "HINFO",
        "HTTPS",
        "KEY",
        "KX",
        "LOC",
        "MB",
        "MD",
        "MF",
        "MG",
        "MINFO",
        "MR",
        "MX",
        "NAPTR",
        "NSEC",
        "NSEC3",
        "NSEC3PARAM",
        "NS",
        "OPENPGPKEY",
        "PTR",
        "RP",
        "RRSIG",
        "RT",
        "SIG",
        "SMIMEA",
        "SOA",
        "SPF",
        "SRV",
        "SSHFP",
        "SVCB",
        "TLSA",
        "TXT",
        "URI",
        "WKS",
        "ZONEMD",
    }

    DIRECTIVES = {
        "$TTL",
        "$ORIGIN",
        "$INCLUDE",
        "$GENERATE",
    }

    @classmethod
    def parse_file(cls, path: Path) -> ZoneDocument:
        source = path.expanduser().resolve()

        try:
            text = source.read_text(encoding="utf-8")
        except OSError as exc:
            raise ZoneFileParseError(
                f"Nie można odczytać pliku strefy {source}: {exc}"
            ) from exc
        except UnicodeDecodeError as exc:
            raise ZoneFileParseError(
                f"Plik strefy {source} nie jest poprawnym UTF-8"
            ) from exc

        document = cls.parse_text(text)
        document.source_path = source

        return document

    @classmethod
    def parse_text(cls, text: str) -> ZoneDocument:
        document = ZoneDocument(
            trailing_newline=text.endswith("\n"),
        )

        previous_owner: str | None = None
        lines = text.splitlines()
        index = 0

        while index < len(lines):
            raw_line = lines[index]
            stripped = raw_line.strip()
            index += 1

            if not stripped:
                document.nodes.append(BlankLine(raw=raw_line))
                continue

            if stripped.startswith(";"):
                document.nodes.append(Comment(raw=raw_line))
                continue

            directive = cls._parse_directive(raw_line)

            if directive is not None:
                document.nodes.append(directive)
                continue

            content = cls._remove_comment(raw_line)
            delta = cls._parenthesis_delta(content)

            # Na tym etapie rekordów wielowierszowych nie interpretujemy.
            if delta != 0:
                block = [raw_line]
                depth = delta

                while depth > 0 and index < len(lines):
                    continuation = lines[index]
                    index += 1
                    block.append(continuation)
                    depth += cls._parenthesis_delta(cls._remove_comment(continuation))

                multiline = cls._parse_multiline_soa(
                    block,
                    previous_owner=previous_owner,
                )

                if multiline is not None:
                    record, owner_was_explicit = multiline
                    document.nodes.append(
                        RecordNode(record=record, raw="\n".join(block))
                    )
                    if owner_was_explicit:
                        previous_owner = record.owner
                else:
                    document.nodes.extend(RawLine(raw=line) for line in block)
                continue

            parsed = cls._parse_record_line(
                raw_line,
                previous_owner=previous_owner,
            )

            if parsed is None:
                document.nodes.append(RawLine(raw=raw_line))
                continue

            record, owner_was_explicit = parsed

            document.nodes.append(
                RecordNode(
                    record=record,
                    raw=raw_line,
                )
            )

            if owner_was_explicit:
                previous_owner = record.owner

        return document

    @classmethod
    def _parse_multiline_soa(
        cls,
        lines: list[str],
        previous_owner: str | None,
    ) -> tuple[DNSRecord, bool] | None:
        """Rozpoznaj bezpiecznie wielowierszowy SOA jako jeden rekord."""
        if not lines:
            return None

        logical = "\n".join(cls._remove_comment(line) for line in lines)
        logical = logical.replace("(", " ").replace(")", " ")
        parsed = cls._parse_record_line(
            logical,
            previous_owner=previous_owner,
        )
        if parsed is None:
            return None

        record, explicit = parsed
        if record.rtype != "SOA":
            return None

        rdata = " ".join(record.rdata.split())
        if len(rdata.split()) != 7:
            return None

        record = DNSRecord(
            owner=record.owner,
            ttl=record.ttl,
            rrclass=record.rrclass,
            rtype=record.rtype,
            rdata=rdata,
            raw=record.raw,
        )
        return record, explicit

    @classmethod
    def _parse_directive(
        cls,
        raw_line: str,
    ) -> Directive | None:
        stripped = raw_line.strip()

        if not stripped.startswith("$"):
            return None

        parts = stripped.split(None, 1)
        keyword = parts[0].upper()

        if keyword not in cls.DIRECTIVES:
            return None

        value = parts[1] if len(parts) == 2 else ""

        return Directive(
            keyword=keyword,
            value=value,
            raw=raw_line,
        )

    @classmethod
    def _parse_record_line(
        cls,
        raw_line: str,
        previous_owner: str | None,
    ) -> tuple[DNSRecord, bool] | None:
        content = cls._remove_comment(raw_line)

        if not content.strip():
            return None

        tokens = cls._tokenise(content)

        if not tokens:
            return None

        owner_omitted = raw_line[:1].isspace()
        position = 0

        if owner_omitted:
            if previous_owner is None:
                return None

            owner = previous_owner
            owner_was_explicit = False
        else:
            owner = tokens[0].value
            owner_was_explicit = True
            position = 1

        ttl: int | None = None
        rrclass = "IN"
        rtype: str | None = None

        while position < len(tokens):
            token = tokens[position].value
            upper = token.upper()

            if ttl is None and cls._is_ttl(token):
                ttl = int(token)
                position += 1
                continue

            if upper in cls.DNS_CLASSES:
                rrclass = cls._normalise_class(upper)
                position += 1
                continue

            if cls._is_record_type(upper):
                rtype = upper
                position += 1
                break

            return None

        if rtype is None or position >= len(tokens):
            return None

        rdata_start = tokens[position].start
        rdata = content[rdata_start:].rstrip()

        if not rdata:
            return None

        canonical_fields = [owner]

        if ttl is not None:
            canonical_fields.append(str(ttl))

        canonical_fields.extend(
            (
                rrclass,
                rtype,
                rdata,
            )
        )

        canonical = " ".join(canonical_fields)

        return (
            DNSRecord(
                owner=owner,
                ttl=ttl,
                rrclass=rrclass,
                rtype=rtype,
                rdata=rdata,
                raw=canonical,
            ),
            owner_was_explicit,
        )

    @staticmethod
    def _is_ttl(value: str) -> bool:
        if not value.isdigit():
            return False

        try:
            ttl = int(value)
        except ValueError:
            return False

        return 0 <= ttl <= 2_147_483_647

    @classmethod
    def _is_record_type(cls, value: str) -> bool:
        if value in cls.COMMON_TYPES:
            return True

        # Obsługa składni RFC 3597, np. TYPE65280.
        return value.startswith("TYPE") and value[4:].isdigit()

    @staticmethod
    def _normalise_class(value: str) -> str:
        aliases = {
            "CHAOS": "CH",
            "HESIOD": "HS",
        }

        return aliases.get(value, value)

    @staticmethod
    def _remove_comment(line: str) -> str:
        """
        Usuń komentarz rozpoczynający się średnikiem poza cudzysłowem.
        """
        in_quotes = False
        escaped = False

        for index, character in enumerate(line):
            if escaped:
                escaped = False
                continue

            if character == "\\":
                escaped = True
                continue

            if character == '"':
                in_quotes = not in_quotes
                continue

            if character == ";" and not in_quotes:
                return line[:index]

        return line

    @staticmethod
    def _tokenise(line: str) -> list[_Token]:
        """
        Podziel linię według białych znaków, zachowując tekst w cudzysłowach.
        """
        tokens: list[_Token] = []
        index = 0
        length = len(line)

        while index < length:
            while index < length and line[index].isspace():
                index += 1

            if index >= length:
                break

            start = index
            in_quotes = False
            escaped = False

            while index < length:
                character = line[index]

                if escaped:
                    escaped = False
                    index += 1
                    continue

                if character == "\\":
                    escaped = True
                    index += 1
                    continue

                if character == '"':
                    in_quotes = not in_quotes
                    index += 1
                    continue

                if character.isspace() and not in_quotes:
                    break

                index += 1

            tokens.append(
                _Token(
                    value=line[start:index],
                    start=start,
                    end=index,
                )
            )

        return tokens

    @staticmethod
    def _parenthesis_delta(line: str) -> int:
        """
        Policz nawiasy poza cudzysłowami.

        Nie interpretuje rekordów wielowierszowych, lecz pozwala zachować
        cały blok jako RawLine.
        """
        delta = 0
        in_quotes = False
        escaped = False

        for character in line:
            if escaped:
                escaped = False
                continue

            if character == "\\":
                escaped = True
                continue

            if character == '"':
                in_quotes = not in_quotes
                continue

            if in_quotes:
                continue

            if character == "(":
                delta += 1
            elif character == ")":
                delta -= 1

        return delta
