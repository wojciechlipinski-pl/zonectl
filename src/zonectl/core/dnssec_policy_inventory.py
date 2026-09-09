"""Privacy-safe, read-only inventory of BIND DNSSEC/KASP policies."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .discovery import BindConfigDiscovery, BindDiscoveryError


BUILT_IN_POLICIES = ("default", "insecure", "none")
RECOMMENDED_ALGORITHMS = {
    "ECDSAP256SHA256",
    "ECDSAP384SHA384",
    "ED25519",
    "ED448",
}
SUPPORTED_ALGORITHMS = RECOMMENDED_ALGORITHMS | {"RSASHA256", "RSASHA512"}
OBSOLETE_ALGORITHMS = {
    "RSASHA1",
    "NSEC3RSASHA1",
    "DSA",
    "DSA-NSEC3-SHA1",
}


@dataclass(frozen=True, slots=True)
class PolicyKey:
    """Allowlisted public parameters of one KASP key template."""

    role: str
    algorithm: str
    lifetime: str
    size: int | None = None
    storage: str | None = None


@dataclass(frozen=True, slots=True)
class PolicyTiming:
    """Allowlisted publication, propagation and signature timing parameters."""

    dnskey_ttl: str | None = None
    parent_ds_ttl: str | None = None
    publish_safety: str | None = None
    retire_safety: str | None = None
    zone_propagation_delay: str | None = None
    parent_propagation_delay: str | None = None
    signatures_refresh: str | None = None
    signatures_validity: str | None = None
    signatures_validity_dnskey: str | None = None
    max_zone_ttl: str | None = None


@dataclass(frozen=True, slots=True)
class DnssecPolicy:
    """One named policy without raw configuration or private material."""

    name: str
    built_in: bool
    keys: tuple[PolicyKey, ...]
    inline_signing: bool | None
    nsec3: bool
    nsec3_iterations: int | None
    nsec3_optout: bool | None
    timing: PolicyTiming
    cds_digest_types: tuple[str, ...]
    cdnskey: bool | None
    offline_ksk: bool | None
    status: str
    warnings: tuple[str, ...]
    zones: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a stable JSON-safe, allowlisted representation."""

        return asdict(self)


@dataclass(frozen=True, slots=True)
class DnssecPolicyInventory:
    """Complete read-only inventory for one BIND configuration tree."""

    root_config: Path
    policies: tuple[DnssecPolicy, ...]
    undefined_references: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a stable JSON-safe, allowlisted representation."""

        return {
            "root_config": str(self.root_config),
            "policies": [policy.to_dict() for policy in self.policies],
            "undefined_references": list(self.undefined_references),
        }


class DnssecPolicyInventoryReader:
    """Discover policy definitions and their zone use without changing BIND."""

    _policy_start = re.compile(
        r"\bdnssec-policy\s+(?P<name>\"[^\"]+\"|'[^']+'|[A-Za-z0-9_.-]+)\s*\{",
        re.IGNORECASE,
    )
    _keys_start = re.compile(r"\bkeys\s*\{", re.IGNORECASE)
    _key = re.compile(
        r"\b(?P<role>csk|ksk|zsk)\b(?P<middle>[^;]*?)"
        r"\blifetime\s+(?P<lifetime>[^\s;]+)\s+"
        r"algorithm\s+(?P<algorithm>[A-Za-z0-9_-]+)"
        r"(?:\s+(?P<size>[0-9]+))?\s*;",
        re.IGNORECASE,
    )
    _inline = re.compile(r"\binline-signing\s+(yes|no)\s*;", re.IGNORECASE)
    _nsec3 = re.compile(r"\bnsec3param\b(?P<value>[^;]*);", re.IGNORECASE)
    _iterations = re.compile(r"\biterations\s+([0-9]+)", re.IGNORECASE)
    _optout = re.compile(r"\boptout\s+(yes|no)", re.IGNORECASE)
    _storage = re.compile(
        r"\b(key-directory|key-store\s+(?:\"[^\"]+\"|'[^']+'|[A-Za-z0-9_.-]+))\b",
        re.IGNORECASE,
    )
    _duration_directives = {
        "dnskey_ttl": "dnskey-ttl",
        "parent_ds_ttl": "parent-ds-ttl",
        "publish_safety": "publish-safety",
        "retire_safety": "retire-safety",
        "zone_propagation_delay": "zone-propagation-delay",
        "parent_propagation_delay": "parent-propagation-delay",
        "signatures_refresh": "signatures-refresh",
        "signatures_validity": "signatures-validity",
        "signatures_validity_dnskey": "signatures-validity-dnskey",
        "max_zone_ttl": "max-zone-ttl",
    }

    def __init__(self, root_config: Path) -> None:
        self.root_config = root_config

    def read(self) -> DnssecPolicyInventory:
        """Read includes, definitions and zone references using no subprocesses."""

        discovery = BindConfigDiscovery(self.root_config).discover()
        definitions: dict[str, tuple[str, str, tuple[PolicyKey, ...]]] = {}

        for path in discovery.config_files:
            try:
                raw = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                raise BindDiscoveryError(
                    f"Nie można odczytać konfiguracji BIND {path}: {exc}"
                ) from exc
            text = BindConfigDiscovery._strip_comments(raw)
            for name, body in self._policy_blocks(text, path):
                folded = name.casefold()
                if folded in definitions:
                    raise BindDiscoveryError(
                        f'Polityka DNSSEC "{name}" ma więcej niż jedną definicję'
                    )
                definitions[folded] = (
                    name,
                    body,
                    self._parse_keys(body, path),
                )

        zones_by_policy: dict[str, list[str]] = {}
        for zone in discovery.zones:
            if zone.dnssec_policy:
                zones_by_policy.setdefault(zone.dnssec_policy.casefold(), []).append(
                    zone.name
                )

        policies: list[DnssecPolicy] = []
        for built_in in BUILT_IN_POLICIES:
            policies.append(self._built_in(built_in, zones_by_policy.get(built_in, [])))
        for folded, (name, body, keys) in sorted(definitions.items()):
            inline = self._parse_inline(body)
            nsec3 = self._parse_nsec3(body)
            warnings, status = self._classify(keys, nsec3)
            iterations, optout = self._nsec3_values(nsec3)
            policies.append(
                DnssecPolicy(
                    name=name,
                    built_in=False,
                    keys=keys,
                    inline_signing=inline,
                    nsec3=nsec3 is not None,
                    nsec3_iterations=iterations,
                    nsec3_optout=optout,
                    timing=self._parse_timing(body),
                    cds_digest_types=self._parse_words(body, "cds-digest-types"),
                    cdnskey=self._parse_yes_no(body, "cdnskey"),
                    offline_ksk=self._parse_yes_no(body, "offline-ksk"),
                    status=status,
                    warnings=warnings,
                    zones=tuple(
                        sorted(zones_by_policy.get(folded, []), key=str.casefold)
                    ),
                )
            )

        known = set(definitions) | set(BUILT_IN_POLICIES)
        undefined = tuple(
            sorted(
                (name for name in zones_by_policy if name not in known),
                key=str.casefold,
            )
        )
        return DnssecPolicyInventory(discovery.root_config, tuple(policies), undefined)

    def _policy_blocks(self, text: str, path: Path) -> list[tuple[str, str]]:
        blocks: list[tuple[str, str]] = []
        position = 0
        while match := self._policy_start.search(text, position):
            opening = text.find("{", match.start(), match.end())
            closing = BindConfigDiscovery._find_block_end(text, opening, path)
            name = match.group("name").strip("\"'")
            blocks.append((name, text[opening + 1 : closing]))
            position = closing + 1
        return blocks

    def _parse_keys(self, body: str, path: Path) -> tuple[PolicyKey, ...]:
        match = self._keys_start.search(body)
        if not match:
            return ()
        opening = body.find("{", match.start(), match.end())
        closing = BindConfigDiscovery._find_block_end(body, opening, path)
        result: list[PolicyKey] = []
        for key in self._key.finditer(body[opening + 1 : closing]):
            storage_match = self._storage.search(key.group("middle"))
            result.append(
                PolicyKey(
                    role=key.group("role").upper(),
                    algorithm=key.group("algorithm").upper(),
                    lifetime=key.group("lifetime"),
                    size=int(key.group("size")) if key.group("size") else None,
                    storage=storage_match.group(0) if storage_match else None,
                )
            )
        return tuple(result)

    def _parse_inline(self, body: str) -> bool | None:
        match = self._inline.search(body)
        return None if not match else match.group(1).casefold() == "yes"

    def _parse_nsec3(self, body: str) -> str | None:
        match = self._nsec3.search(body)
        return match.group("value") if match else None

    def _parse_timing(self, body: str) -> PolicyTiming:
        values: dict[str, str | None] = {}
        for field, directive in self._duration_directives.items():
            match = re.search(
                rf"\b{re.escape(directive)}\s+([^\s;]+)\s*;", body, re.IGNORECASE
            )
            values[field] = match.group(1) if match else None
        return PolicyTiming(**values)

    @staticmethod
    def _parse_words(body: str, directive: str) -> tuple[str, ...]:
        match = re.search(rf"\b{re.escape(directive)}\s+([^;]+);", body, re.IGNORECASE)
        return (
            () if not match else tuple(word.upper() for word in match.group(1).split())
        )

    @staticmethod
    def _parse_yes_no(body: str, directive: str) -> bool | None:
        match = re.search(
            rf"\b{re.escape(directive)}\s+(yes|no)\s*;", body, re.IGNORECASE
        )
        return None if not match else match.group(1).casefold() == "yes"

    def _nsec3_values(self, value: str | None) -> tuple[int | None, bool | None]:
        if value is None:
            return None, None
        iterations = self._iterations.search(value)
        optout = self._optout.search(value)
        return (
            int(iterations.group(1)) if iterations else None,
            None if not optout else optout.group(1).casefold() == "yes",
        )

    def _classify(
        self, keys: tuple[PolicyKey, ...], nsec3: str | None
    ) -> tuple[tuple[str, ...], str]:
        warnings: list[str] = []
        if not keys:
            warnings.append("Brak rozpoznawalnej definicji kluczy")
        algorithms = {key.algorithm for key in keys}
        obsolete = sorted(algorithms & OBSOLETE_ALGORITHMS)
        unknown = sorted(algorithms - SUPPORTED_ALGORITHMS - OBSOLETE_ALGORITHMS)
        if obsolete:
            warnings.append("Przestarzały algorytm: " + ", ".join(obsolete))
        if unknown:
            warnings.append("Nierozpoznany algorytm: " + ", ".join(unknown))
        iterations, _ = self._nsec3_values(nsec3)
        if iterations not in {None, 0}:
            warnings.append("NSEC3 iterations musi wynosić 0 według wymagań BIND 9.20")
        if obsolete or unknown or iterations not in {None, 0} or not keys:
            return tuple(warnings), "BLOCKED"
        if algorithms - RECOMMENDED_ALGORITHMS:
            warnings.append("Algorytm wspierany, ale wymaga świadomej oceny operatora")
            return tuple(warnings), "WARN"
        return (), "PASS"

    @staticmethod
    def _built_in(name: str, zones: list[str]) -> DnssecPolicy:
        keys: tuple[PolicyKey, ...]
        warnings: tuple[str, ...]
        if name == "default":
            keys = (PolicyKey("CSK", "ECDSAP256SHA256", "unlimited"),)
            status, warnings = "PASS", ()
        elif name == "insecure":
            keys, status = (), "TRANSITIONAL"
            warnings = ("Polityka przejściowa do kontrolowanego wycofania DNSSEC",)
        else:
            keys, status = (), "UNSIGNED"
            warnings = ("Polityka nie włącza podpisywania DNSSEC",)
        return DnssecPolicy(
            name=name,
            built_in=True,
            keys=keys,
            inline_signing=True if name in {"default", "insecure"} else None,
            nsec3=False,
            nsec3_iterations=None,
            nsec3_optout=None,
            timing=PolicyTiming(),
            cds_digest_types=(),
            cdnskey=None,
            offline_ksk=None,
            status=status,
            warnings=warnings,
            zones=tuple(sorted(zones, key=str.casefold)),
        )
