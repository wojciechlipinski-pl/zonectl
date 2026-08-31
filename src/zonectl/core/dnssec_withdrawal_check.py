"""Read-only confirmation that DS has disappeared everywhere before withdrawal.

This is the mirror image of :mod:`dnssec_ds_check`: instead of waiting for a
DS record to *appear* at every resolver, it waits for the DS record to
*disappear* at every resolver before allowing the operator to run
``rndc dnssec -checkds withdrawn``. As long as any checked resolver still
returns a DS record, the result is ``BLOCKED`` and no follow-up command
should touch KASP or the registrar.
"""

from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass, field
from typing import Callable, Sequence

DigRunner = Callable[[Sequence[str]], "subprocess.CompletedProcess[str]"]


@dataclass(slots=True)
class ResolverDsWithdrawalCheck:
    resolver: str
    status: str  # "DS_ABSENT" | "DS_PRESENT" | "ERROR"
    message: str
    records: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class DnssecWithdrawalCheckResult:
    zone: str
    status: str  # "BLOCKED" | "READY_FOR_WITHDRAWN" | "ERROR"
    resolver_checks: list[ResolverDsWithdrawalCheck] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    next_action: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class DnssecWithdrawalChecker:
    """Confirms DS is gone everywhere before permitting the withdrawn step.

    Purely read-only: issues ``dig ... DS`` queries against each resolver and
    never touches BIND, KASP, or the registrar. ``dig_runner`` can be
    injected for testing; it defaults to a real ``subprocess.run`` call.
    """

    def __init__(
        self,
        *,
        timeout: int = 3,
        dig_runner: DigRunner | None = None,
    ) -> None:
        self.timeout = timeout
        self._dig_runner = dig_runner or self._default_dig_runner

    def _default_dig_runner(
        self, args: Sequence[str]
    ) -> "subprocess.CompletedProcess[str]":
        return subprocess.run(
            list(args),
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )

    def _check_resolver(self, zone: str, resolver: str) -> ResolverDsWithdrawalCheck:
        query = zone if zone.endswith(".") else f"{zone}."
        args = ["dig", "+noall", "+answer", "+dnssec", f"@{resolver}", query, "DS"]
        try:
            completed = self._dig_runner(args)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return ResolverDsWithdrawalCheck(
                resolver, "ERROR", f"Zapytanie dig nie powiodło się: {exc}"
            )
        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            return ResolverDsWithdrawalCheck(
                resolver,
                "ERROR",
                f"dig zwrócił kod {completed.returncode}: {stderr}",
            )
        lines = [
            line
            for line in (completed.stdout or "").splitlines()
            if line.strip() and not line.startswith(";")
        ]
        # A DS record line looks like: "name.\tTTL\tIN\tDS\t<rdata>". RRSIG
        # lines covering DS ("...\tRRSIG\tDS <rdata>") are deliberately not
        # matched, since the covered-type token is space- not tab-separated.
        ds_lines = tuple(line for line in lines if "\tDS\t" in line)
        if ds_lines:
            return ResolverDsWithdrawalCheck(
                resolver,
                "DS_PRESENT",
                "Resolver nadal zwraca rekord DS",
                ds_lines,
            )
        return ResolverDsWithdrawalCheck(resolver, "DS_ABSENT", "Brak rekordu DS")

    def collect(
        self, zone: str, resolvers: Sequence[str]
    ) -> DnssecWithdrawalCheckResult:
        result = DnssecWithdrawalCheckResult(zone=zone, status="BLOCKED")
        for resolver in resolvers:
            check = self._check_resolver(zone, resolver)
            result.resolver_checks.append(check)
            if check.status == "ERROR":
                result.errors.append(f"{resolver}: {check.message}")

        if result.errors:
            result.status = "ERROR"
            result.next_action = (
                "Napraw błędy zapytań DS przed ponowną próbą kontroli wycofania. "
                "Nie wykonuj 'rndc dnssec -checkds withdrawn'."
            )
            return result

        still_present = [
            check for check in result.resolver_checks if check.status == "DS_PRESENT"
        ]
        if still_present:
            resolvers_listed = ", ".join(check.resolver for check in still_present)
            result.status = "BLOCKED"
            result.next_action = (
                f"DS nadal widoczny na: {resolvers_listed}. Nie wykonuj "
                "'rndc dnssec -checkds withdrawn' — poczekaj na wygaśnięcie TTL "
                "i propagację, następnie sprawdź ponownie."
            )
            return result

        result.status = "READY_FOR_WITHDRAWN"
        result.next_action = (
            "DS nie jest już widoczny na żadnym sprawdzonym resolverze. "
            "Dopiero teraz wolno rozważyć 'rndc dnssec -checkds withdrawn', "
            "pod warunkiem że DNSKEY/RRSIG są nadal bezpiecznie publikowane."
        )
        return result
