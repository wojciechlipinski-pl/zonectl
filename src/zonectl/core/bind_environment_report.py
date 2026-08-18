"""Odczytowa autodetekcja środowiska BIND i integracji RPZ."""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .discovery import BindConfigDiscovery, BindDiscoveryError, ZoneConfig
from .runner import CommandResult, run


@dataclass(frozen=True, slots=True)
class RpzEnvironment:
    """Stan pojedynczej strefy używanej przez ``response-policy``."""

    zone: str
    source_file: str | None
    mode: str
    health: str
    age_seconds: int | None
    max_age_seconds: int
    serial: str | None
    nodes: int | None
    loaded: bool
    timer_unit: str
    timer_enabled: bool
    timer_active: bool
    service_unit: str
    service_result: str | None
    timer_last_trigger: str | None
    timer_next_elapse: str | None
    updater_path: str | None
    findings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BindEnvironmentReport:
    """Wynik pierwszego, pozbawionego skutków ubocznych rozpoznania BIND."""

    root_config: str
    config_files: tuple[str, ...]
    zone_count: int
    primary_count: int
    secondary_count: int
    dnssec_count: int
    rpz: tuple[RpzEnvironment, ...]
    findings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class BindEnvironmentReporter:
    """Rozpoznaje aktywną konfigurację bez zapisywania plików i wywołań mutujących."""

    _response_policy_re = re.compile(
        r"\bresponse-policy\s*\{(?P<body>.*?)\}\s*;",
        re.IGNORECASE | re.DOTALL,
    )
    _policy_zone_re = re.compile(
        r"\bzone\s+[\"'](?P<name>[^\"']+)[\"']",
        re.IGNORECASE,
    )
    _status_value_re = re.compile(r"^(?P<name>[^:]+):\s*(?P<value>.*)$")

    def __init__(
        self,
        root_config: Path = Path("/etc/bind/named.conf"),
        *,
        command_runner: Callable[[list[str], int], CommandResult] = run,
        clock: Callable[[], float] = time.time,
        timer_unit: str = "update-cert-rpz.timer",
        service_unit: str = "update-cert-rpz.service",
        managed_timer_unit: str = "zonectl-cert-rpz.timer",
        managed_service_unit: str = "zonectl-cert-rpz.service",
        rpz_max_age: int = 600,
    ) -> None:
        self.root_config = root_config
        self.command_runner = command_runner
        self.clock = clock
        self.timer_unit = timer_unit
        self.service_unit = service_unit
        self.managed_timer_unit = managed_timer_unit
        self.managed_service_unit = managed_service_unit
        self.rpz_max_age = rpz_max_age

    def collect(self) -> BindEnvironmentReport:
        discovery = BindConfigDiscovery(self.root_config).discover()
        policy_zones = self._response_policy_zones(discovery.config_files)
        zone_index = {zone.name.casefold(): zone for zone in discovery.zones}
        findings: list[str] = []
        rpz: list[RpzEnvironment] = []

        for policy_zone in policy_zones:
            zone = zone_index.get(policy_zone.casefold())
            if zone is None:
                findings.append(
                    f"response-policy wskazuje niewykrytą strefę {policy_zone}"
                )
                continue
            rpz.append(self._rpz_environment(zone))

        if not policy_zones:
            findings.append("Nie wykryto aktywnej dyrektywy response-policy")

        return BindEnvironmentReport(
            root_config=str(discovery.root_config),
            config_files=tuple(str(path) for path in discovery.config_files),
            zone_count=len(discovery.zones),
            primary_count=sum(
                zone.zone_type in {"primary", "master"} for zone in discovery.zones
            ),
            secondary_count=sum(
                zone.zone_type in {"secondary", "slave"} for zone in discovery.zones
            ),
            dnssec_count=sum(
                bool(zone.dnssec_policy or zone.inline_signing)
                for zone in discovery.zones
            ),
            rpz=tuple(rpz),
            findings=tuple(findings),
        )

    def _response_policy_zones(self, config_files: tuple[Path, ...]) -> tuple[str, ...]:
        names: list[str] = []
        for path in config_files:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                raise BindDiscoveryError(f"Nie można odczytać konfiguracji {path}: {exc}") from exc
            text = BindConfigDiscovery._strip_comments(text)
            for policy in self._response_policy_re.finditer(text):
                for match in self._policy_zone_re.finditer(policy.group("body")):
                    name = match.group("name").rstrip(".")
                    if name.casefold() not in {item.casefold() for item in names}:
                        names.append(name)
        return tuple(names)

    def _rpz_environment(self, zone: ZoneConfig) -> RpzEnvironment:
        findings: list[str] = []
        age: int | None = None
        if zone.source_file and zone.source_file.is_file():
            age = max(0, int(self.clock() - zone.source_file.stat().st_mtime))
        else:
            findings.append("Plik strefy RPZ nie istnieje")

        managed = bool(
            self._systemctl_property(self.managed_timer_unit, "FragmentPath")
            and self._systemctl_property(self.managed_service_unit, "FragmentPath")
        )
        timer_unit = self.managed_timer_unit if managed else self.timer_unit
        service_unit = self.managed_service_unit if managed else self.service_unit
        timer_enabled = self._systemctl_bool("is-enabled", timer_unit)
        timer_active = self._systemctl_bool("is-active", timer_unit)
        service_result = self._systemctl_property(service_unit, "Result")
        timer_last_trigger = self._systemctl_property(
            timer_unit, "LastTriggerUSec"
        )
        timer_next_elapse = self._systemctl_property(
            timer_unit, "NextElapseUSecRealtime"
        )
        updater_path = self._systemctl_exec_path(service_unit)
        status = self.command_runner(["rndc", "zonestatus", zone.name], 10)
        values = self._status_values(status.stdout) if status.returncode == 0 else {}
        loaded = status.returncode == 0
        if not loaded:
            findings.append("BIND nie potwierdził załadowania strefy RPZ")
        if service_result not in {None, "success"}:
            findings.append(f"Ostatni wynik usługi aktualizującej: {service_result}")
        if not timer_enabled or not timer_active:
            findings.append("Timer aktualizacji RPZ nie jest aktywny i włączony")

        if not loaded or age is None or service_result not in {None, "success"}:
            health = "FAILED"
        elif not timer_enabled or not timer_active:
            health = "DISABLED"
        elif age <= self.rpz_max_age:
            health = "ACTIVE"
        elif age <= self.rpz_max_age * 2:
            health = "DELAYED"
        else:
            health = "STALE"

        mode = "MANAGED" if managed else "EXTERNAL" if timer_enabled or updater_path else "OFF"
        serial = values.get("serial")
        raw_nodes = values.get("nodes")
        nodes = int(raw_nodes) if raw_nodes and raw_nodes.isdigit() else None
        return RpzEnvironment(
            zone=zone.name,
            source_file=str(zone.source_file) if zone.source_file else None,
            mode=mode,
            health=health,
            age_seconds=age,
            max_age_seconds=self.rpz_max_age,
            serial=serial,
            nodes=nodes,
            loaded=loaded,
            timer_unit=timer_unit,
            timer_enabled=timer_enabled,
            timer_active=timer_active,
            service_unit=service_unit,
            service_result=service_result,
            timer_last_trigger=timer_last_trigger,
            timer_next_elapse=timer_next_elapse,
            updater_path=updater_path,
            findings=tuple(findings),
        )

    def _systemctl_bool(self, action: str, unit: str) -> bool:
        return self.command_runner(["systemctl", action, unit], 10).returncode == 0

    def _systemctl_property(self, unit: str, name: str) -> str | None:
        result = self.command_runner(
            ["systemctl", "show", unit, f"--property={name}", "--value"], 10
        )
        value = result.stdout.strip()
        if result.returncode != 0 or not value or value.casefold() == "n/a":
            return None
        return value

    def _systemctl_exec_path(self, unit: str) -> str | None:
        result = self.command_runner(
            ["systemctl", "show", unit, "--property=ExecStart", "--value"], 10
        )
        if result.returncode != 0:
            return None
        match = re.search(r"path=(?P<path>[^ ;}]+)", result.stdout)
        return match.group("path") if match else None

    @classmethod
    def _status_values(cls, text: str) -> dict[str, str]:
        values: dict[str, str] = {}
        for line in text.splitlines():
            match = cls._status_value_re.match(line.strip())
            if match:
                values[match.group("name").strip().casefold()] = match.group(
                    "value"
                ).strip()
        return values
