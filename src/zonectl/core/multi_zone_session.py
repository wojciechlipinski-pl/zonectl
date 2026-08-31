from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from types import TracebackType

from .models import Zone
from .zone_edit_session import ZoneEditSession, ZoneSaveResult


class MultiZoneSessionError(RuntimeError):
    """Błąd koordynacji sesji obejmującej wiele stref."""


@dataclass(slots=True)
class MultiZoneSaveResult:
    """Wynik walidacji lub zapisu zestawu stref."""

    validated: list[ZoneSaveResult] = field(default_factory=list)
    committed: list[ZoneSaveResult] = field(default_factory=list)
    failed: ZoneSaveResult | None = None

    @property
    def ok(self) -> bool:
        return self.failed is None


class MultiZoneEditSession:
    """
    Przechowuj niezależne sesje edycji wielu stref.

    Każda strefa zachowuje własną blokadę, kandydat, backup i manifest
    transakcji. Przed pierwszym COMMIT wszystkie zmienione strefy są
    walidowane w trybie dry-run.
    """

    def __init__(
        self,
        zones: Iterable[Zone],
        session_factory: Callable[[Zone], ZoneEditSession],
    ) -> None:
        self._zones = {zone.name: zone for zone in zones}
        self._session_factory = session_factory
        self._sessions: dict[str, ZoneEditSession] = {}

    @property
    def open_zone_names(self) -> tuple[str, ...]:
        return tuple(self._sessions)

    @property
    def dirty_zone_names(self) -> tuple[str, ...]:
        return tuple(name for name, session in self._sessions.items() if session.dirty)

    def open(self, zone_name: str) -> ZoneEditSession:
        """Otwórz strefę lub zwróć już istniejącą sesję roboczą."""
        if zone_name in self._sessions:
            return self._sessions[zone_name]
        try:
            zone = self._zones[zone_name]
        except KeyError as exc:
            raise MultiZoneSessionError(f"Nieznana strefa: {zone_name}") from exc
        session = self._session_factory(zone)
        self._sessions[zone_name] = session
        return session

    def close_zone(
        self,
        zone_name: str,
        *,
        discard: bool = False,
    ) -> None:
        """Zamknij jedną strefę, opcjonalnie porzucając jej zmiany."""
        session = self._sessions.get(zone_name)
        if session is None:
            return
        if session.dirty and not discard:
            raise MultiZoneSessionError(f"Strefa {zone_name} ma niezapisane zmiany")
        if discard and session.dirty:
            session.discard()
        session.close()
        del self._sessions[zone_name]

    def validate_all(self) -> MultiZoneSaveResult:
        """Zweryfikuj wszystkie zmienione strefy bez COMMIT."""
        result = MultiZoneSaveResult()
        for name in self.dirty_zone_names:
            validation = self._sessions[name].save(commit=False)
            result.validated.append(validation)
            if not validation.ok:
                result.failed = validation
                break
        return result

    def save_all(self) -> MultiZoneSaveResult:
        """
        Zweryfikuj wszystkie strefy, a potem zapisuj je kolejno.

        Po pierwszym nieudanym COMMIT dalsze strefy nie są zapisywane.
        Wynik nie udaje atomowości pomiędzy niezależnymi strefami.
        """
        result = self.validate_all()
        if not result.ok:
            return result

        for name in tuple(self.dirty_zone_names):
            saved = self._sessions[name].save(commit=True)
            if saved.committed or saved.status == "NO-CHANGE":
                result.committed.append(saved)
                continue
            result.failed = saved
            break
        return result

    def close(self, *, discard: bool = False) -> None:
        """Zamknij wszystkie sesje i zwolnij ich blokady."""
        dirty = self.dirty_zone_names
        if dirty and not discard:
            raise MultiZoneSessionError("Niezapisane strefy: " + ", ".join(dirty))
        for name in tuple(self.open_zone_names):
            self.close_zone(name, discard=discard)

    def __enter__(self) -> "MultiZoneEditSession":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close(discard=True)
