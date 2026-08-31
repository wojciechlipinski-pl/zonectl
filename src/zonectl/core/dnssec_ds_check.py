"""Read-only verification of DNSSEC delegation and authoritative servers."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Callable

from .dnssec_report import _answer_rdata, dnskey_to_ds
from .runner import CommandResult, run


@dataclass(frozen=True, slots=True)
class DsResolverCheck:
    resolver: str
    status: str
    records: tuple[str, ...]
    message: str


@dataclass(frozen=True, slots=True)
class DnskeyAuthorityCheck:
    server: str
    status: str
    authoritative: bool
    dnskey_records: tuple[str, ...]
    rrsig_records: tuple[str, ...]
    message: str


@dataclass(frozen=True, slots=True)
class DnssecDsCheck:
    zone: str
    status: str
    kasp_ready: bool
    expected_ds: tuple[str, ...]
    resolver_checks: tuple[DsResolverCheck, ...]
    authority_checks: tuple[DnskeyAuthorityCheck, ...]
    next_action: str
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class DnssecDsChecker:
    """Compare DS and DNSKEY through independent read-only DNS queries."""

    def __init__(
        self,
        *,
        local_server: str = "127.0.0.1",
        timeout: int = 3,
        command_runner: Callable[[list[str], int], CommandResult] = run,
    ) -> None:
        self.local_server = local_server
        self.timeout = timeout
        self.command_runner = command_runner

    def _command(self, command: list[str], timeout: int | None = None) -> CommandResult:
        return self.command_runner(command, timeout or self.timeout + 3)

    def _dig(
        self,
        server: str,
        zone: str,
        rtype: str,
        *,
        comments: bool = False,
    ) -> CommandResult:
        command = [
            "dig",
            f"@{server}",
            zone,
            rtype,
            "+dnssec",
            "+noall",
        ]
        if comments:
            command.append("+comments")
        command.extend(("+answer", f"+time={self.timeout}", "+tries=1"))
        return self._command(command)

    @staticmethod
    def _normal(records: tuple[str, ...]) -> set[str]:
        return {record.casefold() for record in records}

    @staticmethod
    def _kasp_ready(output: str) -> bool:
        states = {}
        for name, value in re.findall(
            r"^\s*-\s*(dnskey|zone rrsig|key rrsig):\s*([a-z-]+)\s*$",
            output,
            re.MULTILINE | re.IGNORECASE,
        ):
            states[name.casefold()] = value.casefold()
        return all(
            states.get(name) == "omnipresent"
            for name in ("dnskey", "zone rrsig", "key rrsig")
        )

    @staticmethod
    def _kasp_ds_state(output: str) -> str | None:
        match = re.search(
            r"^\s*-\s*ds:\s*([a-z-]+)\s*$",
            output,
            re.MULTILINE | re.IGNORECASE,
        )
        return match.group(1).casefold() if match else None

    def collect(self, zone: str, resolvers: tuple[str, ...]) -> DnssecDsCheck:
        if not resolvers:
            raise ValueError("Wymagany jest co najmniej jeden resolver")

        errors: list[str] = []
        kasp = self._command(["rndc", "dnssec", "-status", zone], 8)
        kasp_output = kasp.stdout + kasp.stderr
        kasp_ready = kasp.returncode == 0 and self._kasp_ready(kasp_output)
        kasp_ds_state = (
            self._kasp_ds_state(kasp_output) if kasp.returncode == 0 else None
        )

        local = self._dig(self.local_server, zone, "DNSKEY")
        local_dnskeys = _answer_rdata(local.stdout, "DNSKEY")
        expected: list[str] = []
        for dnskey in local_dnskeys:
            try:
                if int(dnskey.split()[0]) & 1:
                    expected.append(dnskey_to_ds(zone, dnskey))
            except (ValueError, IndexError) as exc:
                errors.append(f"Nie można obliczyć DS z DNSKEY: {exc}")
        if local.returncode != 0 or not expected:
            errors.append("Brak lokalnego DNSKEY pozwalającego obliczyć DS.")

        expected_set = self._normal(tuple(expected))
        resolver_checks: list[DsResolverCheck] = []
        for resolver in resolvers:
            result = self._dig(resolver, zone, "DS")
            records = _answer_rdata(result.stdout, "DS")
            if result.returncode != 0:
                status = "ERROR"
                message = "Resolver nie odpowiedział poprawnie"
            elif not records:
                status = "MISSING"
                message = "DS nie jest widoczny"
            elif expected_set & self._normal(records):
                status = "MATCH"
                message = "DS jest zgodny"
            else:
                status = "MISMATCH"
                message = "Widoczny DS nie odpowiada lokalnemu DNSKEY"
                errors.append(f"Niezgodny DS przez resolver {resolver}.")
            resolver_checks.append(DsResolverCheck(resolver, status, records, message))

        ns_result = self._dig(resolvers[0], zone, "NS")
        nameservers = _answer_rdata(ns_result.stdout, "NS")
        if ns_result.returncode != 0 or not nameservers:
            errors.append("Nie udało się ustalić serwerów autorytatywnych strefy.")

        authority_checks: list[DnskeyAuthorityCheck] = []
        local_key_set = self._normal(local_dnskeys)
        for nameserver in nameservers:
            server = nameserver.rstrip(".")
            result = self._dig(server, zone, "DNSKEY", comments=True)
            dnskeys = _answer_rdata(result.stdout, "DNSKEY")
            rrsigs = _answer_rdata(result.stdout, "RRSIG")
            authoritative = bool(
                re.search(r"flags:\s*[^\n;]*\baa\b", result.stdout, re.IGNORECASE)
            )
            if result.returncode != 0:
                status, message = "ERROR", "Serwer nie odpowiedział poprawnie"
            elif not authoritative:
                status, message = "NOT-AUTH", "Odpowiedź nie ma flagi AA"
            elif self._normal(dnskeys) != local_key_set or not rrsigs:
                status, message = "MISMATCH", "DNSKEY lub RRSIG jest niezgodny"
            else:
                status, message = "MATCH", "DNSKEY i RRSIG są zgodne"
            if status != "MATCH":
                errors.append(f"Problem DNSSEC na serwerze {server}: {message}.")
            authority_checks.append(
                DnskeyAuthorityCheck(
                    server, status, authoritative, dnskeys, rrsigs, message
                )
            )

        resolver_states = {check.status for check in resolver_checks}
        authorities_ok = bool(authority_checks) and all(
            check.status == "MATCH" for check in authority_checks
        )
        if errors:
            status = "FAIL"
            next_action = "Usuń zgłoszone błędy; nie potwierdzaj publikacji DS w KASP."
        elif resolver_states == {"MATCH"} and authorities_ok:
            status = "PASS"
            if kasp_ds_state in {"rumoured", "omnipresent"}:
                next_action = (
                    "DS został już potwierdzony w KASP; nie wykonuj ponownie "
                    "confirm-ds. Monitoruj DNSSEC"
                    + (
                        " do osiągnięcia stanu ds: omnipresent."
                        if kasp_ds_state == "rumoured"
                        else "."
                    )
                )
            else:
                next_action = (
                    "DS jest zgodny i widoczny przez wszystkie resolvery; można "
                    "przejść do kontrolowanego potwierdzenia publikacji w KASP."
                )
        elif "MATCH" in resolver_states:
            status = "PROPAGATING"
            next_action = "Poczekaj na pełną propagację DS i uruchom kontrolę ponownie."
        elif "ERROR" in resolver_states:
            status = "INDETERMINATE"
            next_action = (
                "Nie udało się potwierdzić stanu DS; nie zmieniaj DS ani KASP "
                "i powtórz kontrolę."
            )
        elif not kasp_ready:
            status = "NOT_READY"
            next_action = "Nie publikuj DS; poczekaj na gotowość KASP."
        else:
            status = "NOT_PUBLISHED"
            next_action = (
                "DS nie jest widoczny; opublikuj go u rejestratora lub poczekaj."
            )

        return DnssecDsCheck(
            zone=zone,
            status=status,
            kasp_ready=kasp_ready,
            expected_ds=tuple(expected),
            resolver_checks=tuple(resolver_checks),
            authority_checks=tuple(authority_checks),
            next_action=next_action,
            errors=tuple(errors),
        )
