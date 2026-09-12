"""Pure presentation helpers for the read-only DNSSEC policy inventory."""

from __future__ import annotations

from dataclasses import asdict

from ..core.dnssec_policy_inventory import DnssecPolicyInventory


def dnssec_policy_lines(
    inventory: DnssecPolicyInventory, *, zone_name: str | None = None
) -> tuple[str, ...]:
    """Build scrollable TUI lines without exposing raw BIND configuration."""

    policies = list(inventory.policies)
    if zone_name is not None:
        used = [policy for policy in policies if zone_name in policy.zones]
        unused = [policy for policy in policies if zone_name not in policy.zones]
        policies = used + unused

    lines = ["POLITYKI DNSSEC/KASP — TYLKO ODCZYT"]
    capabilities = inventory.bind_capabilities
    if capabilities is None:
        lines.append("BIND: zgodność nie została sprawdzona")
    else:
        lines.append(
            f"BIND: {capabilities.version or 'nieznany'} [{capabilities.status}]"
        )
        for finding in capabilities.findings:
            lines.append(f"  UWAGA: {finding}")
    lines.append("")
    for policy in policies:
        source = "wbudowana" if policy.built_in else "nazwana"
        marker = " [STREFA]" if zone_name and zone_name in policy.zones else ""
        lines.append(f"[{policy.status}] {policy.name} ({source}){marker}")
        lines.append(f"  Zgodność z BIND: {policy.bind_compatibility}")
        lines.append("  Strefy: " + (", ".join(policy.zones) or "-"))
        for key in policy.keys:
            size = f"/{key.size}" if key.size is not None else ""
            lines.append(
                f"  {key.role}: {key.algorithm}{size}; lifetime={key.lifetime}"
            )
        timing = [
            f"{name.replace('_', '-')}={value}"
            for name, value in asdict(policy.timing).items()
            if value is not None
        ]
        if timing:
            lines.append("  Czasy: " + ", ".join(timing))
        if policy.cds_digest_types:
            lines.append("  CDS: " + ", ".join(policy.cds_digest_types))
        for warning in policy.warnings:
            lines.append(f"  UWAGA: {warning}")
        for finding in policy.compatibility_findings:
            lines.append(f"  ZGODNOŚĆ: {finding}")
        lines.append("")
    if inventory.undefined_references:
        lines.append(
            "BŁĄD: niezdefiniowane polityki: "
            + ", ".join(inventory.undefined_references)
        )
    lines.append("Raport odczytowy — niczego nie zmieniono.")
    return tuple(lines)
