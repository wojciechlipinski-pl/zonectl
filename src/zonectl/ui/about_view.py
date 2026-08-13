"""Treść ekranu F1 prezentującego projekt i jego autorstwo."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AboutView:
    title: str
    lines: tuple[str, ...]

    @classmethod
    def build(cls, version: str) -> "AboutView":
        return cls(
            title=f"ZoneCTL {version} — O programie",
            lines=(
                "ZoneCTL — Transactional DNS Management Toolkit for BIND 9",
                "",
                "AUTOR I WŁAŚCICIEL PROJEKTU",
                "Wojciech Lipiński",
                "Domain Expert • QA • Product Design",
                "",
                "ARCHITEKTURA I ROZWÓJ WSPOMAGANE PRZEZ AI",
                "OpenAI ChatGPT",
                "",
                "HISTORIA",
                "Projekt rozpoczął się od prostego skryptu Python służącego do",
                "porządkowania plików konfiguracyjnych domen. Rozwinął się w",
                "transakcyjne narzędzie CLI i TUI do zarządzania BIND, DNSSEC,",
                "ACL, serwerami secondary i integracjami RPZ.",
                "",
                "REPOZYTORIUM",
                "https://github.com/wojciechlipinski-pl/zonectl",
                "",
                "F1 zamyka ten ekran • q/Esc powrót",
            ),
        )
