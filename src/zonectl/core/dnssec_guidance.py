"""Operator guidance derived from the read-only DNSSEC report."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .dnssec_report import DnssecReport


@dataclass(frozen=True, slots=True)
class DnssecGuidance:
    stage: str
    title: str
    progress: str
    next_action: str
    not_before: str | None = None
    ds_publication_allowed: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _kasp_states(lines: tuple[str, ...]) -> dict[str, str]:
    states: dict[str, str] = {}
    pattern = re.compile(
        r"^\s*-\s*(goal|dnskey|ds|zone rrsig|key rrsig):\s*([a-z-]+)\s*$",
        re.IGNORECASE,
    )
    for line in lines:
        match = pattern.match(line)
        if match:
            states[match.group(1).casefold()] = match.group(2).casefold()
    return states


def localize_bind_time(value: str | None) -> str | None:
    """Convert a BIND GMT timestamp to the server's local timezone."""
    if not value:
        return None
    try:
        moment = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return value
    if moment.tzinfo is None:
        return value
    return moment.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def build_dnssec_guidance(report: DnssecReport) -> DnssecGuidance:
    """Return one unambiguous next step without changing BIND."""
    if report.status == "FAIL":
        return DnssecGuidance(
            stage="ERROR",
            title="Wymagana interwencja operatora",
            progress="Nie można bezpiecznie kontynuować.",
            next_action="Usuń zgłoszone błędy; nie publikuj ani nie usuwaj DS.",
        )
    if not report.configured:
        return DnssecGuidance(
            stage="UNSIGNED",
            title="DNSSEC nie jest włączony",
            progress="0/4 warunków gotowych",
            next_action=f"Utwórz plan: zctl dnssec enable-plan {report.zone}",
        )
    states = _kasp_states(report.rndc_status)
    if (report.dnssec_policy or "").casefold() == "insecure":
        withdrawal_states = (
            "goal",
            "dnskey",
            "ds",
            "zone rrsig",
            "key rrsig",
        )
        hidden = sum(states.get(name) == "hidden" for name in withdrawal_states)
        not_before = localize_bind_time(report.next_key_event)
        if all(states.get(name) == "hidden" for name in ("goal", "dnskey", "ds")):
            return DnssecGuidance(
                stage="READY_TO_FINALIZE",
                title="KASP zakończył wycofywanie DNSSEC",
                progress=f"{hidden}/5 stanów KASP ukrytych",
                next_action=(
                    "Sprawdź dry-run: zctl dnssec disable-apply "
                    f"{report.zone} --stage finalize"
                ),
                not_before=not_before,
            )
        action = f"Ponów kontrolę: zctl dnssec report {report.zone}"
        if not_before:
            action = (
                f"Po {not_before} uruchom ponownie: zctl dnssec report {report.zone}"
            )
        return DnssecGuidance(
            stage="WITHDRAWING",
            title="Trwa bezpieczne wycofywanie DNSSEC przez KASP",
            progress=f"{hidden}/5 stanów KASP ukrytych",
            next_action=action,
            not_before=not_before,
        )
    if report.parent_ds_matches is True:
        return DnssecGuidance(
            stage="ACTIVE",
            title="Łańcuch zaufania DNSSEC jest aktywny",
            progress="4/4 warunków gotowych",
            next_action="Monitoruj DNSSEC; nie zmieniaj ręcznie kluczy KASP.",
            ds_publication_allowed=True,
        )

    required = ("dnskey", "zone rrsig", "key rrsig")
    ready = sum(states.get(name) == "omnipresent" for name in required)
    if ready == len(required) and report.calculated_ds:
        return DnssecGuidance(
            stage="READY_FOR_DS",
            title="DNSSEC jest gotowy do publikacji DS",
            progress="3/3 warunków propagacji gotowych",
            next_action=(
                "Opublikuj podany DS u rejestratora, a następnie uruchom "
                f"zctl dnssec report {report.zone}."
            ),
            ds_publication_allowed=True,
        )

    not_before = localize_bind_time(report.next_key_event)
    action = f"Uruchom ponownie: zctl dnssec report {report.zone}"
    if not_before:
        action = f"Po {not_before} uruchom ponownie: zctl dnssec report {report.zone}"
    return DnssecGuidance(
        stage="PROPAGATING",
        title="Trwa propagacja DNSKEY i podpisów strefy",
        progress=f"{ready}/3 warunków propagacji gotowych",
        next_action=action,
        not_before=not_before,
    )
