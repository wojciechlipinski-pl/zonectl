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
        rendered = self.render_record(node.record)
        suffix = self._inline_comment_suffix(node.raw)
        return rendered + suffix

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
