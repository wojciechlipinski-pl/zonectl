"""Zbiorczy, odczytowy audyt gotowości deklaracji DNSSEC do importu."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .dnssec_ds_check import DnssecDsChecker
from .dnssec_report import DnssecReporter
from .models import Zone


@dataclass(frozen=True, slots=True)
class DnssecOnboardingAuditItem:
    zone: str
    status: str
    report_status: str
    delegation_status: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class DnssecOnboardingAuditor:
    """Sprawdza wiele stref kolejno, nie modyfikując BIND, KASP ani DS."""

    def __init__(
        self,
        *,
        local_server: str = "127.0.0.1",
        resolvers: tuple[str, ...] = ("1.1.1.1", "8.8.8.8", "9.9.9.9"),
        timeout: int = 3,
        reporter_factory: Callable[..., DnssecReporter] = DnssecReporter,
        checker_factory: Callable[..., DnssecDsChecker] = DnssecDsChecker,
    ) -> None:
        self.local_server = local_server
        self.resolvers = resolvers
        self.timeout = timeout
        self.reporter_factory = reporter_factory
        self.checker_factory = checker_factory

    def audit(
        self, zones: tuple[Zone, ...], key_directory: Path
    ) -> tuple[DnssecOnboardingAuditItem, ...]:
        items: list[DnssecOnboardingAuditItem] = []
        for zone in zones:
            try:
                report = self.reporter_factory(
                    local_server=self.local_server,
                    resolver=self.resolvers[0],
                    timeout=self.timeout,
                ).collect(zone, zone.key_directory or key_directory)
                delegation = self.checker_factory(
                    local_server=self.local_server,
                    timeout=self.timeout,
                ).collect(zone.name, self.resolvers)
                ready = (
                    report.status == "PASS"
                    and delegation.status == "PASS"
                    and report.parent_ds_matches is True
                    and delegation.kasp_ready
                )
                status = "READY" if ready else "BLOCKED"
                reason = (
                    "Raport PASS, delegacja PASS, DS zgodny, KASP gotowy"
                    if ready
                    else f"raport={report.status}, delegacja={delegation.status}"
                )
            except Exception as exc:
                status, reason = "ERROR", str(exc)
                report_status = delegation_status = "ERROR"
            else:
                report_status = report.status
                delegation_status = delegation.status
            items.append(
                DnssecOnboardingAuditItem(
                    zone.name, status, report_status, delegation_status, reason
                )
            )
        return tuple(items)
