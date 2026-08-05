"""Odczytowy raport konfiguracji i stanu DNSSEC strefy."""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .dnssec_guidance import build_dnssec_guidance
from .models import Zone
from .runner import CommandResult, run


@dataclass(frozen=True, slots=True)
class DnssecReport:
    zone: str
    status: str
    configured: bool
    dnssec_policy: str | None
    inline_signing: bool
    loaded: bool | None
    signing: bool | None
    rndc_status: tuple[str, ...]
    key_directory: str | None
    key_files: tuple[str, ...]
    dnskey_records: tuple[str, ...]
    rrsig_records: tuple[str, ...]
    calculated_ds: tuple[str, ...]
    parent_ds_records: tuple[str, ...]
    parent_ds_matches: bool | None
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    next_key_event: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["guidance"] = build_dnssec_guidance(self).to_dict()
        return payload


def _dns_name_wire(name: str) -> bytes:
    labels = name.rstrip(".").casefold().split(".")
    wire = bytearray()
    for label in labels:
        encoded = label.encode("idna")
        if not encoded or len(encoded) > 63:
            raise ValueError(f"Niepoprawna etykieta DNS: {label!r}")
        wire.append(len(encoded))
        wire.extend(encoded)
    wire.append(0)
    return bytes(wire)


def _key_tag(rdata: bytes) -> int:
    accumulator = 0
    for index, octet in enumerate(rdata):
        accumulator += octet if index & 1 else octet << 8
    accumulator += (accumulator >> 16) & 0xFFFF
    return accumulator & 0xFFFF


def dnskey_to_ds(zone: str, dnskey: str, digest_type: int = 2) -> str:
    """Oblicz RDATA rekordu DS z tekstowego RDATA DNSKEY (RFC 4034)."""
    fields = dnskey.split()
    if len(fields) < 4:
        raise ValueError("DNSKEY ma niepełne RDATA")
    flags, protocol, algorithm = (int(fields[index]) for index in range(3))
    if protocol != 3:
        raise ValueError(f"Niepoprawny protokół DNSKEY: {protocol}")
    public_key = base64.b64decode("".join(fields[3:]), validate=True)
    rdata = (
        flags.to_bytes(2, "big")
        + protocol.to_bytes(1, "big")
        + algorithm.to_bytes(1, "big")
        + public_key
    )
    if digest_type != 2:
        raise ValueError(f"Nieobsługiwany typ digestu DS: {digest_type}")
    digest = hashlib.sha256(_dns_name_wire(zone) + rdata).hexdigest().upper()
    return f"{_key_tag(rdata)} {algorithm} {digest_type} {digest}"


def _answer_rdata(output: str, rtype: str) -> tuple[str, ...]:
    wanted = rtype.upper()
    records: list[str] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(";"):
            continue
        fields = line.split()
        try:
            rrclass = next(
                position
                for position, field in enumerate(fields)
                if field.upper() in {"IN", "CH", "HS"}
            )
        except StopIteration:
            continue
        type_index = rrclass + 1
        if (
            type_index < len(fields)
            and fields[type_index].upper() == wanted
            and type_index + 1 < len(fields)
        ):
            rdata = fields[type_index + 1 :]
            if wanted in {"DNSKEY", "DS"} and len(rdata) >= 4:
                records.append(" ".join((*rdata[:3], "".join(rdata[3:]))))
            else:
                records.append(" ".join(rdata))
    return tuple(records)


class DnssecReporter:
    """Zbiera stan DNSSEC bez wykonywania operacji zmieniających system."""

    def __init__(
        self,
        *,
        local_server: str = "127.0.0.1",
        resolver: str = "1.1.1.1",
        timeout: int = 3,
        command_runner: Callable[[list[str], int], CommandResult] = run,
    ) -> None:
        self.local_server = local_server
        self.resolver = resolver
        self.timeout = timeout
        self.command_runner = command_runner

    def _command(
        self,
        command: list[str],
        timeout: int | None = None,
    ) -> CommandResult:
        return self.command_runner(command, timeout or self.timeout + 3)

    def _dig(self, server: str, zone: str, rtype: str) -> CommandResult:
        return self._command(
            [
                "dig",
                f"@{server}",
                zone,
                rtype,
                "+dnssec",
                "+noall",
                "+answer",
                f"+time={self.timeout}",
                "+tries=1",
            ]
        )

    @staticmethod
    def _key_files(zone: str, directory: Path | None) -> tuple[str, ...]:
        if directory is None or not directory.is_dir():
            return ()
        prefix = f"K{zone.rstrip('.')}.+"
        return tuple(
            str(path)
            for path in sorted(directory.iterdir(), key=lambda item: item.name)
            if path.is_file()
            and path.name.startswith(prefix)
            and path.suffix in {".key", ".private", ".state"}
        )

    @staticmethod
    def _signing_state(output: str) -> bool | None:
        text = output.casefold()
        negative = (
            "zone signing is disabled",
            "signing disabled",
            "does not have dnssec-policy",
        )
        positive = (
            "zone signing is enabled",
            "state: active",
        )
        if re.search(r"\bzone signing:\s*no\b", text):
            return False
        if re.search(r"\bzone signing:\s*yes\b", text):
            return True
        if any(marker in text for marker in negative):
            return False
        if any(marker in text for marker in positive):
            return True
        return None

    def collect(
        self,
        zone: Zone,
        key_directory: Path | None = None,
    ) -> DnssecReport:
        errors: list[str] = []
        warnings: list[str] = []
        configured = bool(zone.dnssec_policy or zone.inline_signing)

        loaded_result = self._command(["rndc", "zonestatus", zone.name], 8)
        loaded = loaded_result.returncode == 0
        next_key_match = re.search(
            r"^next key event:\s*(.+?)\s*$",
            loaded_result.stdout,
            re.MULTILINE | re.IGNORECASE,
        )
        next_key_event = next_key_match.group(1) if next_key_match else None
        if not loaded:
            errors.append("Strefa nie jest załadowana przez BIND.")

        signing_result = self._command(["rndc", "dnssec", "-status", zone.name], 8)
        rndc_text = (signing_result.stdout + signing_result.stderr).strip()
        rndc_status = tuple(
            line.rstrip()
            for line in rndc_text.splitlines()
            if line.strip()
        )
        signing: bool | None
        if signing_result.returncode != 0:
            signing = None
            warnings.append("Nie udało się odczytać stanu podpisywania przez rndc.")
        else:
            signing = self._signing_state(rndc_text)
            if signing is None:
                warnings.append("Wynik rndc nie określa jednoznacznie stanu podpisywania.")

        dnskey_result = self._dig(self.local_server, zone.name, "DNSKEY")
        dnskeys = _answer_rdata(dnskey_result.stdout, "DNSKEY")
        rrsigs = _answer_rdata(dnskey_result.stdout, "RRSIG")
        if dnskey_result.returncode != 0:
            errors.append("Zapytanie o lokalne DNSKEY zakończyło się błędem.")

        calculated: list[str] = []
        for dnskey in dnskeys:
            try:
                flags = int(dnskey.split()[0])
                if flags & 1:
                    calculated.append(dnskey_to_ds(zone.name, dnskey))
            except (ValueError, IndexError) as exc:
                warnings.append(f"Nie można obliczyć DS z DNSKEY: {exc}")

        parent_result = self._dig(self.resolver, zone.name, "DS")
        parent_ds = _answer_rdata(parent_result.stdout, "DS")
        if parent_result.returncode != 0:
            parent_match: bool | None = None
            warnings.append("Nie udało się odczytać DS przez publiczny resolver.")
        elif not parent_ds:
            parent_match = False if configured else None
            if configured:
                warnings.append("Brak rekordu DS widocznego przez publiczny resolver.")
        else:
            expected = {item.casefold() for item in calculated}
            published = {item.casefold() for item in parent_ds}
            parent_match = bool(expected & published) if expected else None
            if parent_match is False:
                errors.append("Opublikowany DS nie odpowiada lokalnemu DNSKEY.")
            elif not configured:
                errors.append("Publiczny DS istnieje dla niepodpisanej strefy.")

        if configured and signing is False:
            errors.append("DNSSEC jest skonfigurowany, ale BIND nie raportuje podpisywania.")
        if configured and not dnskeys:
            errors.append("DNSSEC jest skonfigurowany, ale brak lokalnego DNSKEY.")
        if configured and not rrsigs:
            errors.append("DNSSEC jest skonfigurowany, ale brak RRSIG dla DNSKEY.")

        if errors:
            status = "FAIL"
        elif not configured:
            status = "UNSIGNED"
        elif warnings:
            status = "WARN"
        else:
            status = "PASS"

        return DnssecReport(
            zone=zone.name,
            status=status,
            configured=configured,
            dnssec_policy=zone.dnssec_policy,
            inline_signing=zone.inline_signing,
            loaded=loaded,
            signing=signing,
            rndc_status=rndc_status,
            key_directory=str(key_directory) if key_directory else None,
            key_files=self._key_files(zone.name, key_directory),
            dnskey_records=dnskeys,
            rrsig_records=rrsigs,
            calculated_ds=tuple(calculated),
            parent_ds_records=parent_ds,
            parent_ds_matches=parent_match,
            warnings=tuple(warnings),
            errors=tuple(errors),
            next_key_event=next_key_event,
        )
