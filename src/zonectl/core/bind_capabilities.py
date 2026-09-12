"""Read-only detection of the installed BIND version and known capabilities."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import asdict, dataclass

from .runner import CommandResult, run


CommandRunner = Callable[[list[str], int], CommandResult]
_VERSION = re.compile(
    r"(?:\bBIND\s+|^)"
    r"(?P<major>\d+)\.(?P<minor>\d+)(?:\.(?P<patch>\d+))?"
    r"(?P<suffix>[^\s]*)",
    re.IGNORECASE | re.MULTILINE,
)
_TESTED_SERIES = {(9, 18), (9, 20)}


@dataclass(frozen=True, slots=True)
class BindCapabilities:
    """Privacy-safe capabilities inferred conservatively from ``named -v``."""

    detected: bool
    version: str | None
    series: str | None
    status: str
    dnssec_policy: bool | None
    inline_signing_in_policy: bool | None
    nsec3_iterations_zero_required: bool | None
    findings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a stable JSON-safe representation without build paths."""

        return asdict(self)


class BindCapabilityDetector:
    """Detect BIND capabilities without reading configuration or changing state."""

    def __init__(self, command_runner: CommandRunner = run) -> None:
        self._run = command_runner

    def detect(self) -> BindCapabilities:
        """Run the side-effect-free version command and classify known behavior."""

        outcomes = (
            self._run(["named", "-v"], 10),
            self._run(["named-checkconf", "-v"], 10),
        )
        match = next(
            (
                candidate
                for outcome in outcomes
                if outcome.returncode == 0
                if (candidate := _VERSION.search(outcome.stdout)) is not None
            ),
            None,
        )
        if match is None:
            successful = any(outcome.returncode == 0 for outcome in outcomes)
            finding = (
                "Nie rozpoznano wersji w wyniku narzędzi BIND"
                if successful
                else self._failure_detail(outcomes[-1])
            )
            return BindCapabilities(
                detected=False,
                version=None,
                series=None,
                status="BLOCKED",
                dnssec_policy=None,
                inline_signing_in_policy=None,
                nsec3_iterations_zero_required=None,
                findings=(finding,),
            )

        major = int(match.group("major"))
        minor = int(match.group("minor"))
        patch = int(match.group("patch") or 0)
        suffix = match.group("suffix")
        version = f"{major}.{minor}.{patch}{suffix}"
        series = f"{major}.{minor}"
        numeric = (major, minor, patch)
        findings: list[str] = []

        if numeric < (9, 20, 0):
            status = "BLOCKED"
            findings.append("ZoneCTL wymaga BIND 9.20 lub nowszego")
        elif (major, minor) not in _TESTED_SERIES:
            status = "WARN"
            findings.append(
                f"Seria BIND {series} nie należy do przetestowanych serii 9.18 i 9.20"
            )
        else:
            status = "PASS"

        dnssec_policy = numeric >= (9, 16, 0)
        bind_920 = numeric >= (9, 20, 0)
        return BindCapabilities(
            detected=True,
            version=version,
            series=series,
            status=status,
            dnssec_policy=dnssec_policy,
            inline_signing_in_policy=bind_920,
            nsec3_iterations_zero_required=bind_920,
            findings=tuple(findings),
        )

    @staticmethod
    def _failure_detail(outcome: CommandResult) -> str:
        if outcome.returncode == 127:
            return "Nie znaleziono poleceń named ani named-checkconf"
        if outcome.returncode == 124:
            return "Przekroczono czas wykrywania wersji BIND"
        return f"Polecenie named -v zakończyło się kodem {outcome.returncode}"
