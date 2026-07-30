from __future__ import annotations

import difflib
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Protocol

from .models import Zone
from .paths import CHANGE_EXPORT_DIR
from .soa_serial import (
    SoaSerialChange,
    SoaSerialError,
    bump_document_soa_serial,
)
from .transaction import TransactionResult
from .zone_document import ZoneDocument
from .zone_document_adapter import ZoneDocumentAdapter
from .zone_file_parser import ZoneFileParser
from .zone_model import ZoneModel
from .zone_writer import ZoneWriter


class TransactionEngineProtocol(Protocol):
    def apply(
        self,
        zone_name: str,
        source: Path,
        commit: bool = False,
    ) -> TransactionResult:
        ...


class ZoneEditSessionError(RuntimeError):
    """Błąd sesji edycji strefy."""


@dataclass(slots=True)
class ZoneSaveResult:
    transaction: TransactionResult
    candidate: Path

    @property
    def committed(self) -> bool:
        return self.transaction.committed

    @property
    def ok(self) -> bool:
        return self.transaction.ok

    @property
    def status(self) -> str:
        return self.transaction.status


class ZoneEditSession:
    """
    Pełna sesja edycji źródłowego pliku strefy.

    Pipeline:

        ZoneFileParser
            -> ZoneDocument
            -> ZoneModel
            -> ZoneDocumentAdapter
            -> ZoneWriter
            -> TransactionEngine
    """

    def __init__(
        self,
        zone: Zone,
        engine: TransactionEngineProtocol,
        *,
        writer: ZoneWriter | None = None,
        candidate_directory: Path | None = None,
        auto_bump_serial: bool = True,
        today_provider: Callable[[], date] = date.today,
    ) -> None:
        if zone.file is None:
            raise ZoneEditSessionError(
                f"Strefa {zone.name} nie posiada pliku źródłowego"
            )

        self.zone = zone
        self.engine = engine
        self.writer = writer or ZoneWriter()
        self.candidate_directory = candidate_directory
        self.auto_bump_serial = auto_bump_serial
        self.today_provider = today_provider

        self.serial_change: SoaSerialChange | None = None
        self._serial_prepared = False

        self.document: ZoneDocument
        self.model: ZoneModel
        self.adapter: ZoneDocumentAdapter

        self._load()

    @property
    def source_path(self) -> Path:
        if self.zone.file is None:
            raise ZoneEditSessionError(
                f"Strefa {self.zone.name} nie posiada pliku źródłowego"
            )

        return self.zone.file.expanduser().resolve()

    @property
    def dirty(self) -> bool:
        return self.model.dirty

    @property
    def change_count(self) -> int:
        return self.model.change_count

    def _load(self) -> None:
        source = self.source_path

        self.serial_change = None
        self._serial_prepared = False

        if not source.is_file():
            raise ZoneEditSessionError(
                f"Plik strefy nie istnieje: {source}"
            )

        self.document = ZoneFileParser.parse_file(source)
        self.model = ZoneModel(
            self.zone.name,
            self.document.records,
        )
        self.adapter = ZoneDocumentAdapter(
            self.document,
            self.model,
        )

    def _prepare_document(self) -> None:
        self.adapter.apply()

        if (
            self.auto_bump_serial
            and self.model.dirty
            and not self._serial_prepared
        ):
            try:
                self.serial_change = bump_document_soa_serial(
                    self.document,
                    today=self.today_provider(),
                )
            except SoaSerialError as exc:
                # Uproszczone dokumenty i kandydaci testowi mogą nie
                # zawierać SOA. W takim przypadku nie podbijamy serialu,
                # a poprawność całej strefy oceni TransactionEngine
                # za pomocą named-checkzone.
                if "Nie znaleziono rekordu SOA" not in str(exc):
                    raise

                self.serial_change = None

            self._serial_prepared = True

    def render_candidate(self) -> str:
        """
        Wygeneruj tekst kandydata bez tworzenia pliku.
        """
        self._prepare_document()
        return self.writer.render_document(self.document)

    def unified_diff(
        self,
        *,
        context: int = 3,
    ) -> str:
        """
        Pokaż różnice między aktywnym plikiem a kandydatem.

        Metoda nie tworzy pliku tymczasowego i nie wykonuje transakcji.
        """
        active = self.source_path.read_text(encoding="utf-8")
        candidate = self.render_candidate()

        return "".join(
            difflib.unified_diff(
                active.splitlines(keepends=True),
                candidate.splitlines(keepends=True),
                fromfile=str(self.source_path),
                tofile=f"{self.source_path} (kandydat)",
                n=max(0, context),
            )
        )

    def export_diff(
        self,
        *,
        directory: Path = CHANGE_EXPORT_DIR,
        timestamp: datetime | None = None,
    ) -> Path:
        """Atomowo zapisz unified diff bez wykonywania COMMIT."""
        content = self.unified_diff()

        if not content:
            raise ZoneEditSessionError(
                "Brak zmian do wyeksportowania"
            )

        directory = directory.expanduser().resolve()
        directory.mkdir(parents=True, exist_ok=True, mode=0o750)

        safe_zone = "".join(
            character
            if character.isalnum() or character in ".-_"
            else "_"
            for character in self.zone.name
        )
        stamp = (timestamp or datetime.now()).strftime(
            "%Y%m%d-%H%M%S"
        )
        filename = (
            f"{stamp}-{safe_zone}-{uuid.uuid4().hex[:8]}.diff"
        )
        destination = directory / filename
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{filename}.",
            dir=directory,
        )
        temporary = Path(temporary_name)

        try:
            os.fchmod(fd, 0o640)

            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(temporary, destination)
            directory_fd = os.open(directory, os.O_DIRECTORY)

            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)

            return destination

        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def create_candidate(self) -> Path:
        """
        Utwórz bezpieczny plik tymczasowy z bieżącymi zmianami.
        """
        self._prepare_document()

        directory = self.candidate_directory

        if directory is None:
            directory = self.source_path.parent

        return self.writer.write_candidate(
            self.document,
            directory=directory,
            prefix=f".{self.source_path.name}.elkman-candidate-",
        )

    def save(
        self,
        *,
        commit: bool = False,
        remove_candidate: bool = True,
    ) -> ZoneSaveResult:
        """
        Waliduj albo zapisz zmiany przez TransactionEngine.

        commit=False:
            dry-run, aktywny plik nie jest zmieniany.

        commit=True:
            backup, atomic install, reload, weryfikacja i rollback.
        """
        candidate = self.create_candidate()

        try:
            transaction = self.engine.apply(
                self.zone.name,
                candidate,
                commit=commit,
            )

            result = ZoneSaveResult(
                transaction=transaction,
                candidate=candidate,
            )

            if transaction.committed:
                self._load()

            return result

        finally:
            if remove_candidate:
                try:
                    candidate.unlink()
                except FileNotFoundError:
                    pass

    def discard(self) -> None:
        """
        Porzuć wszystkie niezapisane zmiany.
        """
        # Ponowny odczyt przywraca również serial SOA podbity
        # podczas wcześniejszego podglądu lub dry-run.
        self._load()

    def undo(self) -> bool:
        """Cofnij ostatnią zmianę bieżącej sesji."""
        if not self.model.undo():
            return False

        if not self.model.dirty:
            self._load()

        return True

    def reload(self) -> None:
        """
        Ponownie odczytaj aktywny plik strefy.

        Niezapisane zmiany są tracone.
        """
        self._load()
