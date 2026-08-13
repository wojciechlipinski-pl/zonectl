"""Model prezentacyjny panelu stanu integracji RPZ."""

from __future__ import annotations

from dataclasses import dataclass

from ..core.bind_environment_report import RpzEnvironment


@dataclass(frozen=True, slots=True)
class RpzStatusView:
    """Gotowe do renderowania, niezależne od curses dane stanu RPZ."""

    zone: str
    health: str
    title: str
    lines: tuple[str, ...]

    @classmethod
    def build(cls, rpz: RpzEnvironment) -> "RpzStatusView":
        age = cls._age(rpz.age_seconds)
        timer = (
            f"{'enabled' if rpz.timer_enabled else 'disabled'}, "
            f"{'active' if rpz.timer_active else 'inactive'}"
        )
        lines = [
            "INTEGRACJA",
            f"Tryb zarządzania      {rpz.mode}",
            f"Stan                  {rpz.health}",
            f"Plik strefy           {rpz.source_file or '-'}",
            "",
            "ŚWIEŻOŚĆ I ZAWARTOŚĆ",
            f"Wiek                  {age}",
            f"Dopuszczalny wiek     {cls._age(rpz.max_age_seconds)}",
            f"Serial                {rpz.serial or '-'}",
            f"Liczba węzłów         {rpz.nodes if rpz.nodes is not None else '-'}",
            f"Załadowana przez BIND {'TAK' if rpz.loaded else 'NIE'}",
            "",
            "AUTOMATYCZNA AKTUALIZACJA",
            f"Timer                 {rpz.timer_unit}",
            f"Stan timera           {timer}",
            f"Usługa                {rpz.service_unit}",
            f"Ostatni wynik         {rpz.service_result or 'nieznany'}",
            f"Aktualizator          {rpz.updater_path or '-'}",
        ]
        if rpz.findings:
            lines.extend(("", "OSTRZEŻENIA"))
            lines.extend(f"- {finding}" for finding in rpz.findings)
        lines.extend(("", "Widok tylko do odczytu — F3 nie zmienia konfiguracji."))
        return cls(
            zone=rpz.zone,
            health=rpz.health,
            title=f"RPZ: {rpz.zone} — {rpz.health}",
            lines=tuple(lines),
        )

    @staticmethod
    def _age(seconds: int | None) -> str:
        if seconds is None:
            return "-"
        minutes, remainder = divmod(max(0, seconds), 60)
        if minutes:
            return f"{minutes} min {remainder} s"
        return f"{remainder} s"
