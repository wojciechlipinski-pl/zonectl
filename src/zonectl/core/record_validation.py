from __future__ import annotations

import base64
import binascii
import ipaddress
import re
import shlex
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .zone_parser import DNSRecord


class ValidationSeverity(str, Enum):
    ERROR = "ERROR"
    WARN = "WARN"
    INFO = "INFO"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    severity: ValidationSeverity
    code: str
    message: str
    owner: str | None = None

    @property
    def key(self) -> tuple[str, str, str | None]:
        return self.code, self.message, self.owner


SUPPORTED_RECORD_TYPES = (
    "A",
    "AAAA",
    "CAA",
    "CNAME",
    "DNSKEY",
    "DS",
    "HTTPS",
    "MX",
    "NAPTR",
    "NS",
    "PTR",
    "SOA",
    "SRV",
    "SSHFP",
    "SVCB",
    "TLSA",
    "TXT",
)

_HEX = re.compile(r"^[0-9A-Fa-f]+$")
_CAA_TAG = re.compile(r"^[A-Za-z0-9-]{1,15}$")


def is_valid_dns_name(value: str, *, allow_root: bool = True) -> bool:
    name = value.strip()
    if allow_root and name == ".":
        return True
    if name == "@":
        return True

    name = name.rstrip(".")
    if not name or len(name) > 253:
        return False

    for label in name.split("."):
        if not label or len(label) > 63:
            return False
        if label.startswith("-") or label.endswith("-"):
            return False
        if not all(character.isalnum() or character in "-_" for character in label):
            return False
    return True


def _integer(
    text: str,
    label: str,
    minimum: int,
    maximum: int,
) -> tuple[int | None, str | None]:
    try:
        value = int(text)
    except ValueError:
        return None, f"{label} musi być liczbą."
    if not minimum <= value <= maximum:
        return None, f"{label} musi mieć zakres {minimum}–{maximum}."
    return value, None


def _hex_error(value: str, label: str, lengths: set[int] | None = None) -> str | None:
    if not value or len(value) % 2 or _HEX.fullmatch(value) is None:
        return f"{label} musi zawierać parzystą liczbę cyfr szesnastkowych."
    if lengths and len(value) not in lengths:
        expected = ", ".join(str(item) for item in sorted(lengths))
        return f"{label} musi mieć długość: {expected} znaków."
    return None


def validate_rdata(rtype: str, rdata: str) -> str | None:
    kind = rtype.strip().upper()
    value = rdata.strip()
    if not value:
        return "Dane rekordu nie mogą być puste."

    if kind == "A":
        try:
            ipaddress.IPv4Address(value)
        except ipaddress.AddressValueError:
            return "Rekord A wymaga poprawnego adresu IPv4."
    elif kind == "AAAA":
        try:
            ipaddress.IPv6Address(value)
        except ipaddress.AddressValueError:
            return "Rekord AAAA wymaga poprawnego adresu IPv6."
    elif kind in {"CNAME", "NS", "PTR"}:
        if not is_valid_dns_name(value):
            return f"Rekord {kind} wymaga poprawnej nazwy DNS."
    elif kind == "MX":
        fields = value.split()
        if len(fields) != 2:
            return "MX: oczekiwany format „priorytet serwer”."
        _, error = _integer(fields[0], "Priorytet MX", 0, 65535)
        if error:
            return error
        if not is_valid_dns_name(fields[1]):
            return "MX zawiera niepoprawną nazwę serwera."
    elif kind == "SRV":
        fields = value.split()
        if len(fields) != 4:
            return "SRV: oczekiwany format „priorytet waga port serwer”."
        for field, label in zip(
            fields[:3],
            ("Priorytet SRV", "Waga SRV", "Port SRV"),
        ):
            _, error = _integer(field, label, 0, 65535)
            if error:
                return error
        if not is_valid_dns_name(fields[3]):
            return "SRV zawiera niepoprawną nazwę serwera."
    elif kind == "CAA":
        try:
            fields = shlex.split(value)
        except ValueError as exc:
            return f"CAA zawiera nieprawidłowe cudzysłowy: {exc}"
        if len(fields) != 3:
            return 'CAA: oczekiwany format „0 issue "ca.example"”.'
        _, error = _integer(fields[0], "Flagi CAA", 0, 255)
        if error:
            return error
        if _CAA_TAG.fullmatch(fields[1]) is None:
            return "Tag CAA jest niepoprawny."
        if not fields[2]:
            return "Wartość CAA nie może być pusta."
    elif kind == "TLSA":
        fields = value.split()
        if len(fields) != 4:
            return "TLSA: oczekiwany format „usage selector matching-type dane”."
        usage, error = _integer(fields[0], "TLSA usage", 0, 3)
        if error:
            return error
        selector, error = _integer(fields[1], "TLSA selector", 0, 1)
        if error:
            return error
        matching, error = _integer(fields[2], "TLSA matching-type", 0, 2)
        if error:
            return error
        del usage, selector
        lengths = {64} if matching == 1 else {128} if matching == 2 else None
        return _hex_error(fields[3], "Dane TLSA", lengths)
    elif kind == "DS":
        fields = value.split()
        if len(fields) != 4:
            return "DS: oczekiwany format „key-tag algorytm digest-type digest”."
        for field, label, maximum in (
            (fields[0], "DS key-tag", 65535),
            (fields[1], "Algorytm DS", 255),
            (fields[2], "Typ digestu DS", 255),
        ):
            _, error = _integer(field, label, 0, maximum)
            if error:
                return error
        digest_type = int(fields[2])
        lengths = {1: {40}, 2: {64}, 4: {96}}.get(digest_type)
        return _hex_error(fields[3], "Digest DS", lengths)
    elif kind == "DNSKEY":
        fields = value.split()
        if len(fields) != 4:
            return "DNSKEY: oczekiwany format „flagi protokół algorytm klucz”."
        _, error = _integer(fields[0], "Flagi DNSKEY", 0, 65535)
        if error:
            return error
        protocol, error = _integer(fields[1], "Protokół DNSKEY", 0, 255)
        if error:
            return error
        if protocol != 3:
            return "Protokół DNSKEY musi mieć wartość 3."
        _, error = _integer(fields[2], "Algorytm DNSKEY", 0, 255)
        if error:
            return error
        try:
            base64.b64decode(fields[3], validate=True)
        except (binascii.Error, ValueError):
            return "Klucz publiczny DNSKEY nie jest poprawnym Base64."
    elif kind == "SSHFP":
        fields = value.split()
        if len(fields) != 3:
            return "SSHFP: oczekiwany format „algorytm typ fingerprint”."
        _, error = _integer(fields[0], "Algorytm SSHFP", 1, 4)
        if error:
            return error
        fp_type, error = _integer(fields[1], "Typ fingerprintu SSHFP", 1, 2)
        if error:
            return error
        lengths = {40} if fp_type == 1 else {64}
        return _hex_error(fields[2], "Fingerprint SSHFP", lengths)
    elif kind == "SOA":
        fields = value.replace("(", " ").replace(")", " ").split()
        if len(fields) != 7:
            return "SOA wymaga: primary hostmaster serial refresh retry expire minimum."
        if not is_valid_dns_name(fields[0]) or not is_valid_dns_name(fields[1]):
            return "SOA zawiera niepoprawną nazwę primary lub hostmaster."
        for field, label, maximum in (
            (fields[2], "Serial SOA", 4294967295),
            (fields[3], "Refresh SOA", 2147483647),
            (fields[4], "Retry SOA", 2147483647),
            (fields[5], "Expire SOA", 2147483647),
            (fields[6], "Minimum SOA", 2147483647),
        ):
            _, error = _integer(field, label, 0, maximum)
            if error:
                return error
    elif kind == "NAPTR":
        try:
            fields = shlex.split(value)
        except ValueError as exc:
            return f"NAPTR zawiera nieprawidłowe cudzysłowy: {exc}"
        if len(fields) != 6:
            return "NAPTR wymaga: order preference flags service regexp replacement."
        for field, label in zip(fields[:2], ("Order NAPTR", "Preference NAPTR")):
            _, error = _integer(field, label, 0, 65535)
            if error:
                return error
        if not is_valid_dns_name(fields[5]):
            return "NAPTR zawiera niepoprawną nazwę replacement."
    elif kind in {"SVCB", "HTTPS"}:
        fields = value.split()
        if len(fields) < 2:
            return f"{kind} wymaga co najmniej „priorytet cel”."
        priority, error = _integer(fields[0], f"Priorytet {kind}", 0, 65535)
        if error:
            return error
        if not is_valid_dns_name(fields[1]):
            return f"{kind} zawiera niepoprawną nazwę celu."
        if priority == 0 and len(fields) > 2:
            return f"{kind} w AliasMode (priorytet 0) nie może mieć parametrów."
        keys = [item.split("=", 1)[0].casefold() for item in fields[2:]]
        if len(keys) != len(set(keys)):
            return f"{kind} zawiera powtórzony parametr."
    elif kind == "TXT":
        try:
            fields = shlex.split(value)
        except ValueError as exc:
            return f"TXT zawiera nieprawidłowe cudzysłowy: {exc}"
        if not fields:
            return "TXT musi zawierać co najmniej jeden fragment tekstu."

    return None


def validate_record(record: DNSRecord) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    rtype = record.rtype.strip().upper()

    if rtype not in SUPPORTED_RECORD_TYPES:
        issues.append(
            ValidationIssue(
                ValidationSeverity.ERROR,
                "unsupported-type",
                f"Nieobsługiwany typ rekordu: {rtype or '(pusty)'}",
                record.owner,
            )
        )
    if record.ttl is not None and not 0 <= record.ttl <= 2147483647:
        issues.append(
            ValidationIssue(
                ValidationSeverity.ERROR,
                "invalid-ttl",
                "TTL musi mieć zakres 0–2147483647.",
                record.owner,
            )
        )
    error = validate_rdata(rtype, record.rdata)
    if error:
        issues.append(
            ValidationIssue(
                ValidationSeverity.ERROR,
                "invalid-rdata",
                error,
                record.owner,
            )
        )
    return issues


def _absolute_name(value: str, zone_name: str) -> str:
    name = value.strip()
    zone = zone_name.rstrip(".")
    if name in {"", "@"}:
        return zone.casefold()
    if name == ".":
        return "."
    if name.endswith("."):
        return name.rstrip(".").casefold()
    return f"{name}.{zone}".casefold()


def _target(record: DNSRecord) -> str | None:
    fields = record.rdata.split()
    kind = record.rtype.upper()
    if kind in {"CNAME", "NS"} and fields:
        return fields[0]
    if kind == "MX" and len(fields) == 2:
        return fields[1]
    if kind == "SRV" and len(fields) == 4:
        return fields[3]
    return None


def validate_zone(
    zone_name: str,
    records: Iterable[DNSRecord],
) -> list[ValidationIssue]:
    items = list(records)
    issues = [issue for record in items for issue in validate_record(record)]
    zone = zone_name.rstrip(".").casefold()
    by_owner: dict[str, list[DNSRecord]] = {}

    for record in items:
        owner = _absolute_name(record.owner, zone_name)
        by_owner.setdefault(owner, []).append(record)

    apex = by_owner.get(zone, [])
    soa_count = sum(record.rtype.upper() == "SOA" for record in apex)
    if soa_count != 1:
        issues.append(
            ValidationIssue(
                ValidationSeverity.ERROR,
                "soa-count",
                f"Apex strefy musi zawierać dokładnie jeden SOA (jest: {soa_count}).",
                zone_name,
            )
        )
    if not any(record.rtype.upper() == "NS" for record in apex):
        issues.append(
            ValidationIssue(
                ValidationSeverity.ERROR,
                "apex-ns",
                "Apex strefy musi zawierać co najmniej jeden rekord NS.",
                zone_name,
            )
        )

    seen: set[tuple[str, str, str]] = set()
    cname_targets: dict[str, str] = {}

    for owner, owner_records in by_owner.items():
        cnames = [record for record in owner_records if record.rtype.upper() == "CNAME"]
        other = [
            record
            for record in owner_records
            if record.rtype.upper() not in {"CNAME", "RRSIG", "NSEC"}
        ]
        if cnames and other:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.ERROR,
                    "cname-conflict",
                    "Właściciel CNAME nie może mieć innych rekordów.",
                    owner,
                )
            )
        targets = {_absolute_name(record.rdata, zone_name) for record in cnames}
        if len(targets) > 1:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.ERROR,
                    "multiple-cname",
                    "Właściciel ma więcej niż jeden cel CNAME.",
                    owner,
                )
            )
        if targets:
            cname_targets[owner] = next(iter(targets))

        for record in owner_records:
            identity = (
                owner,
                record.rtype.upper(),
                " ".join(record.rdata.split()).casefold(),
            )
            if identity in seen:
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.WARN,
                        "duplicate-record",
                        "Strefa zawiera duplikat rekordu.",
                        owner,
                    )
                )
            seen.add(identity)

    for start in cname_targets:
        visited: set[str] = set()
        current = start
        while current in cname_targets:
            if current in visited:
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.ERROR,
                        "cname-loop",
                        "Wykryto pętlę rekordów CNAME.",
                        start,
                    )
                )
                break
            visited.add(current)
            current = cname_targets[current]

    for record in items:
        kind = record.rtype.upper()
        target_text = _target(record)
        if not target_text or target_text == ".":
            continue
        target = _absolute_name(target_text, zone_name)
        in_zone = target == zone or target.endswith("." + zone)
        if not in_zone:
            continue

        target_records = by_owner.get(target, [])
        target_types = {item.rtype.upper() for item in target_records}
        if not target_records:
            severity = (
                ValidationSeverity.ERROR if kind == "NS" else ValidationSeverity.WARN
            )
            issues.append(
                ValidationIssue(
                    severity,
                    "missing-local-target",
                    f"Lokalny cel {target_text} nie istnieje w strefie.",
                    record.owner,
                )
            )
            continue
        if kind in {"MX", "NS", "SRV"} and "CNAME" in target_types:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.ERROR,
                    "alias-service-target",
                    f"Cel rekordu {kind} nie może być CNAME.",
                    record.owner,
                )
            )
        if kind in {"MX", "NS", "SRV"} and not target_types.intersection({"A", "AAAA"}):
            severity = (
                ValidationSeverity.ERROR if kind == "NS" else ValidationSeverity.WARN
            )
            issues.append(
                ValidationIssue(
                    severity,
                    "missing-address-target",
                    f"Lokalny cel {kind} nie ma rekordu A ani AAAA.",
                    record.owner,
                )
            )

    return issues
