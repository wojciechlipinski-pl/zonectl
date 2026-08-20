"""Plan assignment of one primary zone to logical secondary groups."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path

from .bind_access_impact import BindAccessImpactReport
from .bind_access_inventory import BindAccessInventoryReader
from .bind_secondary_plan import BindSecondaryPlan, BindSecondaryPlanner
from .bind_secondary_report import BindSecondaryReporter
from .discovery import BindConfigDiscovery, BindDiscoveryError
from .managed_zone_migration import ManagedZoneMigrationPlanner


class BindZoneSecondaryError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BindZoneSecondaryPlan:
    zone: str
    source: Path
    old_pairs: tuple[str, ...]
    new_pairs: tuple[str, ...]
    original_text: str
    candidate_text: str
    diff: str
    validation_ok: bool
    validation_message: str
    operational_addresses: tuple[str, ...]
    impact: BindAccessImpactReport

    def transaction_plan(self) -> BindSecondaryPlan:
        return BindSecondaryPlan(
            name=f"zone-{self.zone}", kind="zone-assignment", source=self.source,
            old_addresses=self.old_pairs, new_addresses=self.new_pairs,
            roles=("notify", "transfer"), zones=(self.zone,),
            original_text=self.original_text, candidate_text=self.candidate_text,
            diff=self.diff, validation_ok=self.validation_ok,
            validation_message=self.validation_message,
            operational_addresses=self.operational_addresses,
            impact=self.impact,
        )


class BindZoneSecondaryPlanner:
    _directive = re.compile(r"\b(?P<name>also-notify|allow-transfer)\s*\{", re.I)

    def __init__(self, root_config: Path = Path("/etc/bind/named.conf")) -> None:
        self.root_config = root_config.expanduser().resolve()

    def available_pairs(self):
        inventory = BindAccessInventoryReader(self.root_config).collect()
        return tuple(pair for pair in BindSecondaryReporter().build(inventory).pairs if pair.status == "PASS")

    def plan(self, zone_name: str, pair_names: list[str] | tuple[str, ...]) -> BindZoneSecondaryPlan:
        wanted = zone_name.rstrip(".").casefold()
        try:
            zone = BindConfigDiscovery(self.root_config).discover().zone(wanted)
        except BindDiscoveryError as exc:
            raise BindZoneSecondaryError(str(exc)) from exc
        if not zone.is_primary:
            raise BindZoneSecondaryError("Przypisanie dotyczy wyłącznie stref primary")
        if "rpz" in wanted or "rpz" in {part.casefold() for part in zone.config_file.parts}:
            raise BindZoneSecondaryError("Zmiana przypisań RPZ jest zablokowana")
        pairs = {pair.name.casefold(): pair for pair in self.available_pairs()}
        selected = []
        for raw in pair_names:
            key = raw.casefold()
            if key not in pairs:
                raise BindZoneSecondaryError(f"Nieznana lub niepełna para secondary: {raw}")
            if key in selected:
                raise BindZoneSecondaryError(f"Powtórzona para secondary: {raw}")
            selected.append(key)
        original = zone.config_file.read_text(encoding="utf-8", errors="replace")
        spans = [s for s in ManagedZoneMigrationPlanner._zone_spans(original, zone.config_file) if s.name.casefold() == wanted]
        if len(spans) != 1:
            raise BindZoneSecondaryError("Nie można jednoznacznie wydzielić deklaracji strefy")
        span = spans[0]
        block = span.text
        current = tuple(sorted(
            pair.name for pair in pairs.values()
            if any(group in self._directive_values(block, "also-notify") for group in pair.notify_groups)
            and any(group in self._directive_values(block, "allow-transfer") for group in pair.transfer_groups)
        ))
        notify = [group for key in selected for group in pairs[key].notify_groups]
        transfer = [group for key in selected for group in pairs[key].transfer_groups]
        operational_addresses = tuple(dict.fromkeys(
            address
            for key in selected
            for address in pairs[key].notify_addresses
        ))
        candidate_block = self._set_directive(block, "also-notify", notify)
        candidate_block = self._set_directive(candidate_block, "allow-transfer", transfer)
        candidate = original[:span.start] + candidate_block + original[span.start + len(block):]
        diff = "".join(difflib.unified_diff(
            original.splitlines(keepends=True), candidate.splitlines(keepends=True),
            fromfile=str(zone.config_file), tofile=f"{zone.config_file} (kandydat secondary strefy)",
        ))
        ok, message = BindSecondaryPlanner(self.root_config)._validate_candidate(zone.config_file, candidate)
        current_keys = {item.casefold() for item in current}
        selected_keys = {item.casefold() for item in selected}
        added = tuple(item for item in selected if item.casefold() not in current_keys)
        removed = tuple(item for item in current if item.casefold() not in selected_keys)
        if removed and not selected:
            risk = "HIGH"
        elif removed:
            risk = "MEDIUM"
        elif added:
            risk = "LOW"
        else:
            risk = "NONE"
        impact = BindAccessImpactReport(
            name=f"zone-{wanted}", kind="zone-assignment",
            source=str(zone.config_file),
            line=original.count("\n", 0, span.start) + 1,
            current_entries=current, candidate_entries=tuple(selected),
            added_entries=added, removed_entries=removed,
            roles=("notify", "transfer"), zones=(wanted,), usages=(),
            dependent_definitions=(), risk=risk, blockers=(),
        )
        return BindZoneSecondaryPlan(
            zone=wanted, source=zone.config_file, old_pairs=current,
            new_pairs=tuple(selected), original_text=original,
            candidate_text=candidate, diff=diff,
            validation_ok=ok, validation_message=message,
            operational_addresses=operational_addresses,
            impact=impact,
        )

    @classmethod
    def _directive_values(cls, block: str, name: str) -> tuple[str, ...]:
        masked = ManagedZoneMigrationPlanner._mask_comments(block)
        match = next((m for m in cls._directive.finditer(masked) if m.group("name").casefold() == name), None)
        if match is None:
            return ()
        opening = masked.find("{", match.start(), match.end())
        closing = BindConfigDiscovery._find_block_end(masked, opening, Path("zone"))
        return tuple(value.strip() for value in block[opening + 1:closing].split(";") if value.strip())

    @classmethod
    def _set_directive(cls, block: str, name: str, values: list[str]) -> str:
        masked = ManagedZoneMigrationPlanner._mask_comments(block)
        match = next((m for m in cls._directive.finditer(masked) if m.group("name").casefold() == name), None)
        rendered = "\n".join(f"        {value};" for value in values)
        if match is not None:
            opening = masked.find("{", match.start(), match.end())
            closing = BindConfigDiscovery._find_block_end(masked, opening, Path("zone"))
            return block[:opening + 1] + ("\n" + rendered + "\n    " if values else " ") + block[closing:]
        if not values:
            return block
        closing = block.rfind("}")
        addition = f"\n    {name} {{\n{rendered}\n    }};\n"
        return block[:closing] + addition + block[closing:]
