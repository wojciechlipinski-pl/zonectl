from __future__ import annotations

import ipaddress
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from .models import Zone
from .paths import DEFAULT_GROUPS


class ZoneLifecycleError(ValueError):
    """Nieprawidłowy lub kolidujący plan cyklu życia strefy."""


_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def normalize_zone_name(value: str) -> str:
    """Znormalizuj i zwaliduj nazwę strefy DNS."""
    name = value.strip().rstrip(".").casefold()
    if not name or len(name) > 253 or "." not in name:
        raise ZoneLifecycleError(
            "Nazwa strefy musi być pełną nazwą domenową"
        )
    labels = name.split(".")
    if any(not _LABEL.fullmatch(label) for label in labels):
        raise ZoneLifecycleError(
            f"Nieprawidłowa nazwa strefy: {value}"
        )
    return name


def normalize_fqdn(value: str, field: str) -> str:
    """Zwróć bezpieczną absolutną nazwę DNS zakończoną kropką."""
    try:
        name = normalize_zone_name(value)
    except ZoneLifecycleError as exc:
        raise ZoneLifecycleError(
            f"Nieprawidłowe pole {field}: {value}"
        ) from exc
    return f"{name}."


@dataclass(frozen=True, slots=True)
class ZoneCreateRequest:
    name: str
    primary_ns: str
    admin: str
    nameservers: tuple[str, ...]
    zone_directory: Path = Path("/var/lib/bind/Primary")
    managed_config: Path = Path("/etc/bind/zonectl-zones.conf")
    managed_zone_directory: Path = Path(
        "/etc/bind/zonectl-zones.d"
    )
    default_ttl: int = 3600
    refresh: int = 3600
    retry: int = 900
    expire: int = 1209600
    negative_ttl: int = 3600
    apex_ipv4: str | None = None
    apex_ipv6: str | None = None
    add_www: bool = False
    group: str = "Pozostałe"
    groups_config: Path = DEFAULT_GROUPS


@dataclass(frozen=True, slots=True)
class ZoneCreatePlan:
    zone_name: str
    zone_file: Path
    managed_config: Path
    zone_declaration_file: Path
    serial: int
    zone_text: str
    bind_declaration: str
    actions: tuple[str, ...]
    group: str = "Pozostałe"
    groups_config: Path = DEFAULT_GROUPS
    groups_text: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["zone_file"] = str(self.zone_file)
        payload["managed_config"] = str(self.managed_config)
        payload["zone_declaration_file"] = str(
            self.zone_declaration_file
        )
        payload["groups_config"] = str(self.groups_config)
        return payload


class ZoneLifecyclePlanner:
    """Twórz pozbawione skutków ubocznych plany zarządzania strefami."""

    def __init__(
        self,
        existing_zones: Iterable[Zone],
        *,
        today_provider=date.today,
    ) -> None:
        self._existing = {
            zone.name.rstrip(".").casefold()
            for zone in existing_zones
        }
        self._today_provider = today_provider

    @staticmethod
    def ensure_lifecycle_allowed(
        zone_name: str,
        existing_zones: Iterable[Zone],
        operation: str,
    ) -> None:
        """Reject lifecycle mutations for automatically managed RPZ zones."""
        name = zone_name.strip().rstrip(".").casefold()
        zone = next(
            (
                candidate
                for candidate in existing_zones
                if candidate.name.rstrip(".").casefold() == name
            ),
            None,
        )
        if zone is not None and zone.health_profile.casefold() == "rpz":
            raise ZoneLifecycleError(
                f"Operacja {operation} jest zablokowana dla automatycznej "
                f"strefy RPZ: {zone.name}"
            )
        if zone is not None and (
            zone.dnssec_policy or zone.inline_signing
        ):
            details = []
            if zone.dnssec_policy:
                details.append(f"dnssec-policy={zone.dnssec_policy}")
            if zone.inline_signing:
                details.append("inline-signing=yes")
            raise ZoneLifecycleError(
                f"Operacja {operation} jest zablokowana dla strefy DNSSEC "
                f"{zone.name} ({', '.join(details)})"
            )

    def plan_create(self, request: ZoneCreateRequest) -> ZoneCreatePlan:
        """Zbuduj plan utworzenia strefy bez zapisywania plików."""
        zone_name = normalize_zone_name(request.name)
        if zone_name in self._existing:
            raise ZoneLifecycleError(
                f"Strefa już istnieje: {zone_name}"
            )
        if not 0 < request.default_ttl <= 2147483647:
            raise ZoneLifecycleError("TTL musi być dodatnią liczbą")
        for value, label, allow_zero in (
            (request.refresh, "refresh", False),
            (request.retry, "retry", False),
            (request.expire, "expire", False),
            (request.negative_ttl, "minimum", True),
        ):
            minimum = 0 if allow_zero else 1
            if not minimum <= value <= 2147483647:
                raise ZoneLifecycleError(
                    f"Parametr SOA {label} musi mieć zakres "
                    f"{minimum}–2147483647"
                )
        if request.expire <= max(request.refresh, request.retry):
            raise ZoneLifecycleError(
                "Parametr SOA expire musi być większy od refresh i retry"
            )

        primary_ns = normalize_fqdn(
            request.primary_ns,
            "primary_ns",
        )
        admin = normalize_fqdn(request.admin, "admin")
        nameservers = tuple(
            dict.fromkeys(
                normalize_fqdn(value, "nameserver")
                for value in request.nameservers
            )
        )
        if not nameservers:
            raise ZoneLifecycleError(
                "Wymagany jest co najmniej jeden serwer NS"
            )
        if primary_ns not in nameservers:
            raise ZoneLifecycleError(
                "primary_ns musi znajdować się na liście nameservers"
            )

        ipv4 = self._address(request.apex_ipv4, 4)
        ipv6 = self._address(request.apex_ipv6, 6)
        if request.add_www and not (ipv4 or ipv6):
            raise ZoneLifecycleError(
                "Rekord www wymaga adresu apex IPv4 lub IPv6"
            )

        serial = int(self._today_provider().strftime("%Y%m%d") + "00")
        zone_file = (
            request.zone_directory.expanduser().resolve()
            / zone_name
        )
        managed_config = request.managed_config.expanduser().resolve()
        declaration_file = (
            request.managed_zone_directory.expanduser().resolve()
            / f"{zone_name}.conf"
        )
        zone_text = self._zone_text(
            request,
            primary_ns,
            admin,
            nameservers,
            serial,
            ipv4,
            ipv6,
        )
        bind_declaration = (
            f'zone "{zone_name}" IN {{\n'
            "    type primary;\n"
            f'    file "{zone_file}";\n'
            "};\n"
        )
        group = request.group.strip() or "Pozostałe"
        groups_text = self._groups_text(
            request.groups_config,
            group,
            zone_name,
        )
        actions = [
            f"utwórz plik strefy {zone_file}",
            f"utwórz deklarację {declaration_file}",
            f"dodaj include do {managed_config}",
        ]
        if groups_text is not None:
            actions.append(
                f"przypisz {zone_name} do grupy {group} w "
                f"{request.groups_config}"
            )
        actions.extend((
            f"wykonaj named-checkzone {zone_name}",
            "wykonaj named-checkconf",
            "wykonaj rndc reconfig",
            f"potwierdź załadowanie strefy {zone_name}",
        ))
        return ZoneCreatePlan(
            zone_name=zone_name,
            zone_file=zone_file,
            managed_config=managed_config,
            zone_declaration_file=declaration_file,
            serial=serial,
            zone_text=zone_text,
            bind_declaration=bind_declaration,
            actions=tuple(actions),
            group=group,
            groups_config=request.groups_config.expanduser().resolve(),
            groups_text=groups_text,
        )

    @staticmethod
    def _groups_text(path: Path, group: str, zone_name: str) -> str | None:
        """Zbuduj kandydat groups.yaml bez modyfikowania pliku."""
        if group.casefold() == "pozostałe".casefold():
            return None

        text = path.expanduser().read_text(encoding="utf-8") if path.exists() else "groups:\n"
        lines = text.splitlines()
        heading = f"  {group}:"
        try:
            start = next(
                index for index, line in enumerate(lines)
                if line.strip().casefold() == f"{group}:".casefold()
                and len(line) - len(line.lstrip(" ")) == 2
            )
        except StopIteration:
            if lines and lines[-1].strip():
                lines.append("")
            lines.extend((heading, f"    - {zone_name}"))
        else:
            end = len(lines)
            for index in range(start + 1, len(lines)):
                line = lines[index]
                if (
                    line.strip().endswith(":")
                    and len(line) - len(line.lstrip(" ")) == 2
                ):
                    end = index
                    break
            if any(line.strip() == f"- {zone_name}" for line in lines[start + 1:end]):
                raise ZoneLifecycleError(
                    f"Strefa {zone_name} jest już przypisana do grupy {group}"
                )
            lines.insert(end, f"    - {zone_name}")

        return "\n".join(lines) + "\n"

    @staticmethod
    def _address(value: str | None, version: int) -> str | None:
        if value is None:
            return None
        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise ZoneLifecycleError(
                f"Nieprawidłowy adres IPv{version}: {value}"
            ) from exc
        if address.version != version:
            raise ZoneLifecycleError(
                f"Oczekiwano adresu IPv{version}: {value}"
            )
        return str(address)

    @staticmethod
    def _zone_text(
        request: ZoneCreateRequest,
        primary_ns: str,
        admin: str,
        nameservers: tuple[str, ...],
        serial: int,
        ipv4: str | None,
        ipv6: str | None,
    ) -> str:
        lines = [
            f"$TTL {request.default_ttl}",
            "",
            f"@ IN SOA {primary_ns} {admin} (",
            f"    {serial} ; serial",
            f"    {request.refresh} ; refresh",
            f"    {request.retry} ; retry",
            f"    {request.expire} ; expire",
            f"    {request.negative_ttl} ; negative TTL",
            ")",
            "",
        ]
        lines.extend(f"@ IN NS {server}" for server in nameservers)
        if ipv4:
            lines.append(f"@ IN A {ipv4}")
        if ipv6:
            lines.append(f"@ IN AAAA {ipv6}")
        if request.add_www:
            lines.append("@ IN TXT \"ZoneCTL: www records below\"")
            if ipv4:
                lines.append(f"www IN A {ipv4}")
            if ipv6:
                lines.append(f"www IN AAAA {ipv6}")
        return "\n".join(lines) + "\n"
