"""Serializacja modelu strefy DNS do pliku kandydata."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterable, Protocol

from .zone_parser import DNSRecord


class ZoneSerializationError(RuntimeError):
    """Błąd podczas serializacji strefy DNS."""


class ZoneModelProtocol(Protocol):
    @property
    def records(self) -> Iterable[DNSRecord]:
        ...


class ZoneSerializer:
    """
    Serializuje rekordy DNS do tekstowego pliku strefy.

    Serializer:
    - nie wykonuje walidacji,
    - nie zwiększa numeru SOA,
    - nie zapisuje aktywnego pliku strefy,
    - nie uruchamia rndc,
    - pomija rekordy oznaczone jako usunięte.
    """

    def __init__(
        self,
        record_separator: str = "\n",
        final_newline: bool = True,
    ) -> None:
        self.record_separator = record_separator
        self.final_newline = final_newline

    @staticmethod
    def _is_deleted(record: DNSRecord) -> bool:
        """
        Obsługuje kilka wariantów modelu rekordów.

        Preferowane pole:
            deleted: bool

        Obsługiwane również:
            is_deleted: bool
            state == "deleted"
            change_type == "deleted"
        """
        deleted = getattr(record, "deleted", None)

        if deleted is not None:
            return bool(deleted)

        is_deleted = getattr(record, "is_deleted", None)

        if is_deleted is not None:
            if callable(is_deleted):
                return bool(is_deleted())

            return bool(is_deleted)

        state = getattr(record, "state", None)

        if isinstance(state, str):
            return state.casefold() in {
                "deleted",
                "delete",
                "removed",
            }

        change_type = getattr(record, "change_type", None)

        if isinstance(change_type, str):
            return change_type.casefold() in {
                "deleted",
                "delete",
                "removed",
            }

        return False

    @staticmethod
    def _normalise_owner(owner: str | None) -> str:
        value = (owner or "").strip()

        return value or "@"

    @staticmethod
    def _normalise_class(record_class: str | None) -> str:
        value = (record_class or "").strip()

        return value or "IN"

    @staticmethod
    def _record_owner(record: DNSRecord) -> str:
        for attribute in (
            "owner",
            "name",
            "hostname",
        ):
            value = getattr(record, attribute, None)

            if value is not None:
                return ZoneSerializer._normalise_owner(str(value))

        raise ZoneSerializationError(
            f"Rekord {record!r} nie zawiera pola owner/name"
        )

    @staticmethod
    def _record_type(record: DNSRecord) -> str:
        for attribute in (
            "rtype",
            "record_type",
            "type",
        ):
            value = getattr(record, attribute, None)

            if value:
                return str(value).strip().upper()

        raise ZoneSerializationError(
            f"Rekord {record!r} nie zawiera typu rekordu"
        )

    @staticmethod
    def _record_rdata(record: DNSRecord) -> str:
        for attribute in (
            "rdata",
            "value",
            "data",
        ):
            value = getattr(record, attribute, None)

            if value is not None:
                result = str(value).strip()

                if result:
                    return result

        raise ZoneSerializationError(
            f"Rekord {record!r} nie zawiera danych RDATA"
        )

    @staticmethod
    def _record_ttl(record: DNSRecord) -> int | None:
        ttl = getattr(record, "ttl", None)

        if ttl is None or ttl == "":
            return None

        try:
            value = int(ttl)
        except (TypeError, ValueError) as exc:
            raise ZoneSerializationError(
                f"Nieprawidłowy TTL rekordu {record!r}: {ttl!r}"
            ) from exc

        if value < 0:
            raise ZoneSerializationError(
                f"TTL nie może być ujemny: {value}"
            )

        return value

    @staticmethod
    def _record_class(record: DNSRecord) -> str:
        for attribute in (
            "rclass",
            "record_class",
            "dns_class",
        ):
            value = getattr(record, attribute, None)

            if value:
                return ZoneSerializer._normalise_class(
                    str(value)
                ).upper()

        return "IN"

    def render_record(self, record: DNSRecord) -> str:
        if self._is_deleted(record):
            raise ZoneSerializationError(
                "Nie można renderować usuniętego rekordu"
            )

        owner = self._record_owner(record)
        ttl = self._record_ttl(record)
        record_class = self._record_class(record)
        record_type = self._record_type(record)
        rdata = self._record_rdata(record)

        fields: list[str] = [owner]

        if ttl is not None:
            fields.append(str(ttl))

        fields.extend(
            (
                record_class,
                record_type,
                rdata,
            )
        )

        return "\t".join(fields)

    def render_records(
        self,
        records: Iterable[DNSRecord],
    ) -> str:
        lines: list[str] = []

        for record in records:
            if self._is_deleted(record):
                continue

            lines.append(self.render_record(record))

        text = self.record_separator.join(lines)

        if self.final_newline and text:
            text += "\n"

        return text

    def render_model(
        self,
        model: ZoneModelProtocol,
    ) -> str:
        try:
            records = model.records
        except AttributeError as exc:
            raise ZoneSerializationError(
                "Model strefy nie posiada właściwości records"
            ) from exc

        return self.render_records(records)

    def write_candidate(
        self,
        model: ZoneModelProtocol,
        directory: Path | None = None,
        prefix: str = "elkman-zone-",
        suffix: str = ".zone",
    ) -> Path:
        text = self.render_model(model)

        target_directory = (
            directory.expanduser().resolve()
            if directory is not None
            else None
        )

        if target_directory is not None:
            target_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

        try:
            fd, raw_path = tempfile.mkstemp(
                prefix=prefix,
                suffix=suffix,
                dir=str(target_directory)
                if target_directory is not None
                else None,
                text=True,
            )
        except OSError as exc:
            raise ZoneSerializationError(
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

        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass

            try:
                path.unlink()
            except FileNotFoundError:
                pass

            raise

        return path
