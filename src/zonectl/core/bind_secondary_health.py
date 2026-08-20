"""Operational SOA/AA gate for zones served by secondary servers."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable

from .runner import run


@dataclass(frozen=True, slots=True)
class SecondarySoaObservation:
    server: str
    authoritative: bool
    serial: int | None
    detail: str


@dataclass(frozen=True, slots=True)
class SecondaryZoneHealth:
    zone: str
    status: str
    primary_serial: int | None
    observations: tuple[SecondarySoaObservation, ...]
    message: str


Query = Callable[[str, str], SecondarySoaObservation]


class BindSecondaryHealthGate:
    def __init__(
        self, *, query: Query | None = None, attempts: int = 3,
        interval_seconds: float = 2.0,
    ) -> None:
        self.query = query or self._query_soa
        self.attempts = max(1, attempts)
        self.interval_seconds = max(0.0, interval_seconds)

    def check(
        self, zones: tuple[str, ...], servers: tuple[str, ...]
    ) -> tuple[SecondaryZoneHealth, ...]:
        return tuple(self._check_zone(zone, servers) for zone in zones)

    def _check_zone(
        self, zone: str, servers: tuple[str, ...]
    ) -> SecondaryZoneHealth:
        primary = self.query("127.0.0.1", zone)
        if not primary.authoritative or primary.serial is None:
            return SecondaryZoneHealth(
                zone, "FAIL", primary.serial, (),
                "Lokalny primary nie zwrócił autorytatywnego SOA",
            )
        observations: tuple[SecondarySoaObservation, ...] = ()
        for attempt in range(self.attempts):
            observations = tuple(self.query(server, zone) for server in servers)
            if all(
                item.authoritative and item.serial == primary.serial
                for item in observations
            ):
                return SecondaryZoneHealth(
                    zone, "PASS", primary.serial, observations,
                    "Secondary zwracają autorytatywny SOA zgodny z primary",
                )
            if attempt + 1 < self.attempts:
                time.sleep(self.interval_seconds)
        if any(not item.authoritative or item.serial is None for item in observations):
            return SecondaryZoneHealth(
                zone, "FAIL", primary.serial, observations,
                "Co najmniej jeden secondary nie zwraca autorytatywnego SOA",
            )
        if any(item.serial > primary.serial for item in observations):
            return SecondaryZoneHealth(
                zone, "FAIL", primary.serial, observations,
                "Secondary ma serial wyższy niż lokalny primary",
            )
        return SecondaryZoneHealth(
            zone, "PENDING", primary.serial, observations,
            "Transfer strefy jest jeszcze w toku; serial secondary jest niższy",
        )

    @staticmethod
    def _query_soa(server: str, zone: str) -> SecondarySoaObservation:
        outcome = run([
            "dig", f"@{server}", zone, "SOA", "+norecurse",
            "+comments", "+answer",
        ], 10)
        output = "\n".join((outcome.stdout, outcome.stderr)).strip()
        flags = re.search(r"flags:\s*([^;]+);", output, re.IGNORECASE)
        authoritative = bool(flags and "aa" in flags.group(1).split())
        serial = None
        for line in output.splitlines():
            fields = line.split()
            try:
                soa = next(i for i, value in enumerate(fields) if value.upper() == "SOA")
                serial = int(fields[soa + 3])
                break
            except (StopIteration, IndexError, ValueError):
                continue
        detail = output[-500:] if output else f"kod {outcome.returncode}"
        return SecondarySoaObservation(server, authoritative, serial, detail)
