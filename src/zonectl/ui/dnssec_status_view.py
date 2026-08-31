"""Presentation model for the read-only DNSSEC TUI screen."""

from __future__ import annotations

from dataclasses import dataclass
import re

from ..core.dnssec_ds_check import DnssecDsCheck
from ..core.dnssec_guidance import build_dnssec_guidance
from ..core.dnssec_report import DnssecReport


@dataclass(frozen=True, slots=True)
class DnssecStatusView:
    DNSSEC_ALGORITHMS = {
        5: "RSASHA1",
        7: "RSASHA1-NSEC3-SHA1",
        8: "RSASHA256",
        10: "RSASHA512",
        13: "ECDSAP256SHA256",
        14: "ECDSAP384SHA384",
        15: "ED25519",
        16: "ED448",
    }
    DS_DIGEST_ALGORITHMS = {
        1: "SHA-1",
        2: "SHA-256",
        3: "GOST R 34.11-94",
        4: "SHA-384",
    }
    zone: str
    stage: str
    title: str
    lines: tuple[str, ...]
    publication_allowed: bool
    operation: str
    operation_label: str

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
        if delegation is not None and guidance.stage != "UNSIGNED":
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
            if (
                guidance.stage == "ACTIVE"
                and delegation.status == "PASS"
                and cls._kasp_ds_state(report) == "hidden"
            ):
                stage = "DS_CONFIRMATION_REQUIRED"
                title = "DS jest publiczny i wymaga potwierdzenia w KASP"
                publication_allowed = True
        lines: list[str] = [
            f"Status raportu       {report.status}",
            f"dnssec-policy        {report.dnssec_policy or '-'}",
            f"inline-signing       {'TAK' if report.inline_signing else 'NIE'}",
            f"Podpisywanie BIND    {cls._yes_no(report.signing)}",
            "",
            "STAN KASP",
        ]
        kasp_lines = [
            line.strip() for line in report.rndc_status if line.strip().startswith("-")
        ]
        lines.extend(kasp_lines or ["- brak danych KASP"])
        lines.extend(("", "DS DO PUBLIKACJI U REJESTRATORA"))
        lines.extend(cls._ds_record_lines(report.calculated_ds))
        lines.extend(("", "DS PUBLICZNY"))
        lines.extend(cls._ds_record_lines(report.parent_ds_records))

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
        lines.append(f"Następny krok        {guidance.next_action}")
        if guidance.stage in {"WITHDRAWING", "READY_TO_FINALIZE"}:
            lines.append(
                "Finalizacja         "
                + (
                    "DOZWOLONA PO DRY-RUNIE"
                    if guidance.stage == "READY_TO_FINALIZE"
                    else "ZABLOKOWANA"
                )
            )
        else:
            lines.append(
                "Publikacja DS        "
                + ("DOZWOLONA" if publication_allowed else "JESZCZE ZABLOKOWANA")
            )
        return cls(
            zone=report.zone,
            stage=stage,
            title=title,
            lines=tuple(lines),
            publication_allowed=publication_allowed,
            operation=cls._operation_for_stage(stage),
            operation_label=cls._operation_label(stage),
        )

    @staticmethod
    def _operation_for_stage(stage: str) -> str:
        if stage == "PROPAGATING":
            return "REFRESH"
        if stage in {"READY_FOR_DS", "DS_PROPAGATING"}:
            return "CHECK_DS"
        if stage in {"ERROR", "INDETERMINATE"}:
            return "REFRESH"
        if stage in {"WITHDRAWING", "READY_TO_FINALIZE"}:
            return "FINALIZE"
        if stage == "ACTIVE":
            return "WITHDRAWAL"
        if stage == "DS_CONFIRMATION_REQUIRED":
            return "CONFIRM_DS"
        if stage == "UNSIGNED":
            return "ENABLE"
        return "STATUS"

    @classmethod
    def _ds_record_lines(cls, records: tuple[str, ...]) -> list[str]:
        """Rozpisz rekord DS na pola spotykane w panelach rejestratorów."""
        if not records:
            return ["  -"]
        lines: list[str] = []
        for index, record in enumerate(records):
            fields = str(record).split()
            if len(fields) < 4:
                lines.append(f"  Pełny rekord       {record}")
                continue
            key_tag, algorithm, digest_type = fields[:3]
            digest = "".join(fields[3:]).upper()
            algorithm_label = cls._algorithm_label(algorithm, cls.DNSSEC_ALGORITHMS)
            digest_label = cls._algorithm_label(digest_type, cls.DS_DIGEST_ALGORITHMS)
            if index:
                lines.append("")
            lines.extend(
                (
                    f"  ID klucza          {key_tag}",
                    f"  Algorytm klucza    {algorithm_label}",
                    f"  Algorytm skrótu    {digest_label}",
                    f"  Skrót klucza       {digest}",
                    "  Pełny rekord DS    "
                    f"{key_tag} {algorithm} {digest_type} {digest}",
                )
            )
        return lines

    @staticmethod
    def _algorithm_label(value: str, names: dict[int, str]) -> str:
        try:
            number = int(value)
        except ValueError:
            return f"{value} — algorytm nierozpoznany"
        name = names.get(number, "algorytm nierozpoznany")
        return f"{number} — {name}"

    @classmethod
    def _operation_label(cls, stage: str) -> str:
        return {
            "FINALIZE": "finalizacja",
            "WITHDRAWAL": "wycofanie",
            "CONFIRM_DS": "potwierdzenie DS",
            "ENABLE": "włączenie",
            "REFRESH": "sprawdź gotowość",
            "CHECK_DS": "sprawdź DS",
            "STATUS": "wskazówki",
        }[cls._operation_for_stage(stage)]

    @staticmethod
    def _kasp_ds_state(report: DnssecReport) -> str | None:
        for line in report.rndc_status:
            match = re.match(r"^\s*-\s*ds:\s*([a-z-]+)\s*$", line, re.IGNORECASE)
            if match:
                return match.group(1).casefold()
        return None

    @staticmethod
    def _yes_no(value: bool | None) -> str:
        if value is True:
            return "TAK"
        if value is False:
            return "NIE"
        return "NIEZNANY"
