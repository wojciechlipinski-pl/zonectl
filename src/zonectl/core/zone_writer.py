from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .zone_document import (
    BlankLine,
    Comment,
    Directive,
    RawLine,
    RecordNode,
    ZoneDocument,
    ZoneNode,
)
from .zone_parser import DNSRecord


class ZoneWriteError(RuntimeError):
    """Błąd podczas generowania lub zapisywania dokumentu strefy."""


class ZoneWriter:
    """
    Bezstratny zapis źródłowego dokumentu strefy.

    Zasady:
    - niezmienione węzły są zapisywane z pola `raw`,
    - zmodyfikowane rekordy są renderowane ponownie,
    - rekordy oznaczone jako usunięte są pomijane,
    - komentarze, dyrektywy, puste linie i RawLine pozostają bez zmian,
    - zachowywana jest informacja o końcowym znaku nowej linii.
    """

    def __init__(
        self,
        field_separator: str = "\t",
    ) -> None:
        self.field_separator = field_separator

    def render_document(
        self,
        document: ZoneDocument,
    ) -> str:
        lines: list[str] = []

        for node in document.nodes:
            rendered = self.render_node(node)

            if rendered is None:
                continue

            lines.append(rendered)

        text = "\n".join(lines)

        if document.trailing_newline:
            text += "\n"

        return text

    def render_node(
        self,
        node: ZoneNode,
    ) -> str | None:
        if isinstance(node, RecordNode):
            if node.deleted:
                return None

            if node.modified:
                return self.render_modified_record(node)

            return node.raw

        if isinstance(
            node,
            (
                BlankLine,
                Comment,
                Directive,
                RawLine,
            ),
        ):
            return node.raw

        raise ZoneWriteError(
            f"Nieobsługiwany typ węzła: {type(node).__name__}"
        )

    def render_modified_record(
        self,
        node: RecordNode,
    ) -> str:
        """Renderuj rekord, zachowując jego komentarz końcowy."""
        if node.record.rtype.upper() == "SOA" and "\n" in node.raw:
            return self._render_modified_multiline_soa(node)

        rendered = self.render_record(node.record)
        suffix = self._inline_comment_suffix(node.raw)
        return rendered + suffix

    @staticmethod
    def _soa_token_spans(raw: str) -> list[tuple[int, int, str]]:
        """Tokeny rekordu SOA poza komentarzami i nawiasami."""
        tokens: list[tuple[int, int, str]] = []
        index = 0

        while index < len(raw):
            character = raw[index]
            if character == ";":
                newline = raw.find("\n", index)
                index = len(raw) if newline < 0 else newline + 1
                continue
            if character.isspace() or character in "()":
                index += 1
                continue

            start = index
            while index < len(raw):
                character = raw[index]
                if character.isspace() or character in "();":
                    break
                index += 1
            tokens.append((start, index, raw[start:index]))

        return tokens

    def _render_modified_multiline_soa(self, node: RecordNode) -> str:
        """Podmień wartości SOA, zachowując układ i komentarze bloku."""
        tokens = self._soa_token_spans(node.raw)
        try:
            soa_index = next(
                index for index, token in enumerate(tokens)
                if token[2].upper() == "SOA"
            )
        except StopIteration as exc:
            raise ZoneWriteError("Nie można odnaleźć typu SOA w bloku") from exc

        rdata = node.record.rdata.split()
        if len(rdata) != 7 or len(tokens) < soa_index + 8:
            raise ZoneWriteError("Wielowierszowy SOA nie zawiera siedmiu pól")

        replacements: list[tuple[int, int, str]] = []
        for token, value in zip(tokens[soa_index + 1:soa_index + 8], rdata):
            replacements.append((token[0], token[1], value))

        ttl_token = next(
            (token for token in tokens[:soa_index] if token[2].isdigit()),
            None,
        )
        if ttl_token is not None and node.record.ttl is not None:
            replacements.append(
                (ttl_token[0], ttl_token[1], str(node.record.ttl))
            )
        elif ttl_token is not None and node.record.ttl is None:
            end = ttl_token[1]
            while end < len(node.raw) and node.raw[end] in " \t":
                end += 1
            replacements.append((ttl_token[0], end, ""))
        elif ttl_token is None and node.record.ttl is not None:
            insert_at = tokens[soa_index][0]
            class_token = next(
                (
                    token for token in tokens[:soa_index]
                    if token[2].upper() in {"IN", "CH", "HS"}
                ),
                None,
            )
            if class_token is not None:
                insert_at = class_token[0]
            replacements.append(
                (insert_at, insert_at, f"{node.record.ttl} ")
            )

        rendered = node.raw
        for start, end, value in sorted(replacements, reverse=True):
            rendered = rendered[:start] + value + rendered[end:]
        return rendered

    @staticmethod
    def _inline_comment_suffix(raw: str) -> str:
        """Zwróć komentarz poza cudzysłowem wraz z odstępem przed nim."""
        in_quotes = False
        escaped = False

        for index, character in enumerate(raw):
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
                start = index

                while start > 0 and raw[start - 1].isspace():
                    start -= 1

                return raw[start:]

        return ""

    def render_record(
        self,
        record: DNSRecord,
    ) -> str:
        owner = record.owner.strip() or "@"
        rrclass = record.rrclass.strip().upper() or "IN"
        rtype = record.rtype.strip().upper()
        rdata = record.rdata.strip()

        if not rtype:
            raise ZoneWriteError(
                "Rekord nie posiada typu DNS"
            )

        if not rdata:
            raise ZoneWriteError(
                f"Rekord {owner} {rtype} nie posiada danych RDATA"
            )

        fields: list[str] = [owner]

        if record.ttl is not None:
            if record.ttl < 0:
                raise ZoneWriteError(
                    f"TTL nie może być ujemny: {record.ttl}"
                )

            fields.append(str(record.ttl))

        fields.extend(
            (
                rrclass,
                rtype,
                rdata,
            )
        )

        return self.field_separator.join(fields)

    def write_candidate(
        self,
        document: ZoneDocument,
        directory: Path | None = None,
        prefix: str = "elkman-zone-",
        suffix: str = ".zone",
    ) -> Path:
        text = self.render_document(document)

        target_directory: Path | None = None

        if directory is not None:
            target_directory = directory.expanduser().resolve()
            target_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

        try:
            fd, raw_path = tempfile.mkstemp(
                prefix=prefix,
                suffix=suffix,
                dir=(
                    str(target_directory)
                    if target_directory is not None
                    else None
                ),
                text=True,
            )
        except OSError as exc:
            raise ZoneWriteError(
                f"Nie można utworzyć pliku kandydata: {exc}"
            ) from exc

        path = Path(raw_path)

        try:
            os.fchmod(fd, 0o600)

            with os.fdopen(
                fd,
                "w",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())

        except Exception as exc:
            try:
                os.close(fd)
            except OSError:
                pass

            try:
                path.unlink()
            except FileNotFoundError:
                pass

            if isinstance(exc, ZoneWriteError):
                raise

            raise ZoneWriteError(
                f"Nie można zapisać pliku kandydata {path}: {exc}"
            ) from exc

        return path
