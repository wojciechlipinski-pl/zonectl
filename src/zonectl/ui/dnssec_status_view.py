"""Presentation model for the read-only DNSSEC TUI screen."""

from __future__ import annotations

from dataclasses import dataclass

from ..core.dnssec_ds_check import DnssecDsCheck
from ..core.dnssec_guidance import build_dnssec_guidance
from ..core.dnssec_report import DnssecReport


@dataclass(frozen=True, slots=True)
class DnssecStatusView:
    zone: str
    stage: str
    title: str
    lines: tuple[str, ...]
    publication_allowed: bool

    @classmethod
    def build(
        cls,
        report: DnssecReport,
        delegation: DnssecDsCheck | None = None,
    ) -> "DnssecStatusView":
        guidance = build_dnssec_guidance(report)
        stage = guidance.stage
        title = guidance.title
        publication_allowed = guidance.ds_publication_allowed
        if delegation is not None:
            if delegation.status == "FAIL":
                stage = "ERROR"
                title = "Kontrola delegacji DNSSEC wykryła błąd"
                publication_allowed = False
            elif delegation.status == "INDETERMINATE":
                stage = "INDETERMINATE"
                title = "Nie udało się potwierdzić pełnego stanu delegacji"
                publication_allowed = False
            elif guidance.stage == "ACTIVE" and delegation.status != "PASS":
                stage = "DS_PROPAGATING"
                title = "DS jest jeszcze propagowany pomiędzy resolverami"
                publication_allowed = False
            elif guidance.stage == "READY_FOR_DS":
                publication_allowed = delegation.status == "NOT_PUBLISHED"
        lines: list[str] = [
            f"Status raportu       {report.status}",
            f"dnssec-policy        {report.dnssec_policy or '-'}",
            f"inline-signing       {'TAK' if report.inline_signing else 'NIE'}",
            f"Podpisywanie BIND    {cls._yes_no(report.signing)}",
            "",
            "STAN KASP",
        ]
        kasp_lines = [
            line.strip()
            for line in report.rndc_status
            if line.strip().startswith("-")
        ]
        lines.extend(kasp_lines or ["- brak danych KASP"])
        lines.extend(("", "DS OCZEKIWANY"))
        lines.extend(f"  {record}" for record in report.calculated_ds or ("-",))
        lines.extend(("", "DS PUBLICZNY"))
        lines.extend(f"  {record}" for record in report.parent_ds_records or ("-",))

        if delegation is not None:
            lines.extend(("", f"KONTROLA DELEGACJI: {delegation.status}", "Resolvery:"))
            lines.extend(
                f"  [{check.status}] {check.resolver} — {check.message}"
                for check in delegation.resolver_checks
            )
            lines.append("Serwery autorytatywne:")
            lines.extend(
                f"  [{check.status}] {check.server} — {check.message}"
                for check in delegation.authority_checks
            )

        lines.extend(("", f"Postęp              {guidance.progress}"))
        if guidance.not_before:
            lines.append(f"Następna kontrola   {guidance.not_before}")
        lines.extend(
            (
                f"Następny krok        {guidance.next_action}",
                "Publikacja DS        "
                + (
                    "DOZWOLONA"
                    if publication_allowed
                    else "JESZCZE ZABLOKOWANA"
                ),
            )
        )
        return cls(
            zone=report.zone,
            stage=stage,
            title=title,
            lines=tuple(lines),
            publication_allowed=publication_allowed,
        )

    @staticmethod
    def _yes_no(value: bool | None) -> str:
        if value is True:
            return "TAK"
        if value is False:
            return "NIE"
        return "NIEZNANY"
