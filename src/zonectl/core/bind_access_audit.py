"""Safety audit for BIND ACLs and secondary server groups."""

from __future__ import annotations

import ipaddress
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from .bind_access_inventory import BindAccessInventory, BindListDefinition


@dataclass(frozen=True, slots=True)
class BindAccessFinding:
    severity: str
    code: str
    message: str
    source: Path | None = None
    line: int | None = None
    zones: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["source"] = str(self.source) if self.source else None
        data["zones"] = list(self.zones)
        return data


@dataclass(frozen=True, slots=True)
class BindAccessAudit:
    status: str
    findings: tuple[BindAccessFinding, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "findings": [item.to_dict() for item in self.findings],
        }


class BindAccessAuditor:
    BUILTINS = {"any", "none", "localhost", "localnets"}

    def audit(self, inventory: BindAccessInventory) -> BindAccessAudit:
        findings: list[BindAccessFinding] = []
        definitions = {item.name.casefold(): item for item in inventory.definitions}
        used_names: set[str] = set()
        affected: dict[str, set[str]] = {}

        for usage in inventory.usages:
            for value in usage.values:
                reference = self._reference(value)
                if reference and usage.zone:
                    affected.setdefault(reference.casefold(), set()).add(usage.zone)

        for definition in inventory.definitions:
            findings.extend(
                self._definition_findings(
                    definition,
                    tuple(sorted(affected.get(definition.name.casefold(), set()))),
                    set(definitions),
                )
            )

        for usage in inventory.usages:
            for value in usage.values:
                reference = self._reference(value)
                if reference is None:
                    continue
                key = reference.casefold()
                if key in definitions:
                    used_names.add(key)
                elif key not in self.BUILTINS:
                    findings.append(
                        BindAccessFinding(
                            "ERROR",
                            "UNKNOWN_REFERENCE",
                            f"{usage.directive} odwołuje się do niezdefiniowanej nazwy: {reference}",
                            usage.source,
                            usage.line,
                            (usage.zone,) if usage.zone else (),
                        )
                    )

        for definition in inventory.definitions:
            if definition.name.casefold() not in used_names:
                findings.append(
                    BindAccessFinding(
                        "WARN",
                        "UNUSED_DEFINITION",
                        f"Definicja {definition.kind} {definition.name} nie ma aktywnego użycia",
                        definition.source,
                        definition.line,
                    )
                )

        for name, count in Counter(
            item.name.casefold() for item in inventory.definitions
        ).items():
            if count > 1:
                item = definitions[name]
                findings.append(
                    BindAccessFinding(
                        "ERROR",
                        "DUPLICATE_DEFINITION",
                        f"Nazwa {item.name} ma {count} aktywne definicje",
                        item.source,
                        item.line,
                    )
                )

        rank = {"ERROR": 0, "WARN": 1, "INFO": 2}
        findings.sort(key=lambda item: (rank[item.severity], item.code, item.message))
        status = (
            "FAIL"
            if any(x.severity == "ERROR" for x in findings)
            else ("WARN" if findings else "PASS")
        )
        return BindAccessAudit(status, tuple(findings))

    def _definition_findings(
        self,
        definition: BindListDefinition,
        zones: tuple[str, ...],
        defined_names: set[str],
    ) -> list[BindAccessFinding]:
        findings: list[BindAccessFinding] = []
        normalized: list[str] = []
        for raw in definition.entries:
            value = raw.lstrip("!").strip()
            reference = self._reference(value)
            if reference is not None:
                normalized.append(
                    ("!" if raw.startswith("!") else "") + reference.casefold()
                )
                if reference.casefold() not in self.BUILTINS | defined_names:
                    findings.append(
                        BindAccessFinding(
                            "ERROR",
                            "UNKNOWN_REFERENCE",
                            f"{definition.name} zawiera niezdefiniowaną nazwę: {reference}",
                            definition.source,
                            definition.line,
                            zones,
                        )
                    )
                continue
            try:
                parsed = ipaddress.ip_network(value, strict=False)
            except ValueError:
                findings.append(
                    BindAccessFinding(
                        "ERROR",
                        "INVALID_ADDRESS",
                        f"Nieprawidłowy adres lub prefiks w {definition.name}: {raw}",
                        definition.source,
                        definition.line,
                        zones,
                    )
                )
                normalized.append(raw.casefold())
                continue
            canonical = str(parsed)
            normalized.append(("!" if raw.startswith("!") else "") + canonical)
            if value != canonical and "/" in value:
                findings.append(
                    BindAccessFinding(
                        "WARN",
                        "NON_CANONICAL_NETWORK",
                        f"Niekanoniczny prefiks w {definition.name}: {raw}; kanonicznie {canonical}",
                        definition.source,
                        definition.line,
                        zones,
                    )
                )
        for entry, count in Counter(normalized).items():
            if count > 1:
                findings.append(
                    BindAccessFinding(
                        "WARN",
                        "DUPLICATE_ENTRY",
                        f"Powtórzony wpis w {definition.name}: {entry} ({count} razy)",
                        definition.source,
                        definition.line,
                        zones,
                    )
                )
        return findings

    @staticmethod
    def _reference(value: str) -> str | None:
        candidate = value.lstrip("!").strip()
        try:
            ipaddress.ip_address(candidate)
            return None
        except ValueError:
            pass
        if "/" in candidate:
            try:
                ipaddress.ip_network(candidate, strict=False)
                return None
            except ValueError:
                return None
        return candidate if candidate else None
