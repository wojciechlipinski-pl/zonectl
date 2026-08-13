"""Prezentacja raportu pierwszego uruchomienia w TUI."""

from __future__ import annotations

from dataclasses import dataclass

from ..core.bind_onboarding_report import BindOnboardingReport


@dataclass(frozen=True, slots=True)
class BindOnboardingView:
    title: str
    lines: tuple[str, ...]

    @classmethod
    def build(cls, report: BindOnboardingReport) -> "BindOnboardingView":
        lines = [
            "WYKRYTE ŚRODOWISKO",
            f"Konfiguracja          {report.root_config}",
            f"Pliki konfiguracji   {report.config_files}",
            f"Strefy                {report.zones}",
            f"Strefy DNSSEC         {report.dnssec_zones}",
            "",
            "KLASYFIKACJA",
        ]
        lines.extend(
            f"[{item.state:<8}] {item.count:>3} — {item.description}"
            for item in report.classes
        )
        lines.extend(
            (
                "",
                "KONFIGURACJA WSPÓŁDZIELONA",
                f"ACL                   {report.acl_definitions}",
                f"Grupy secondary       {report.secondary_groups}",
                f"Integracje RPZ        {report.rpz_integrations}",
                f"Tryby RPZ             {', '.join(report.rpz_modes) or '-'}",
                "",
                f"Kandydaci do importu  {report.import_candidates}",
                f"Zablokowane           {report.blocked}",
                "",
                "NASTĘPNY KROK",
                report.next_action,
                "",
                "Raport tylko do odczytu — nie zmieniono BIND.",
                "Enter — przejrzyj kandydatów do importu.",
            )
        )
        return cls("Pierwsze uruchomienie — środowisko BIND", tuple(lines))
