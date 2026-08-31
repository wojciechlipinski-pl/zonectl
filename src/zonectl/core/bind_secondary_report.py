"""Read-only impact report for BIND secondary/notify groups."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .bind_access_inventory import BindAccessInventory


@dataclass(frozen=True, slots=True)
class SecondaryGroupReport:
    name: str
    kind: str
    entries: tuple[str, ...]
    roles: tuple[str, ...]
    zones: tuple[str, ...]
    usage_count: int
    source: str
    line: int

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["entries"] = list(self.entries)
        data["roles"] = list(self.roles)
        data["zones"] = list(self.zones)
        return data


@dataclass(frozen=True, slots=True)
class SecondaryPairReport:
    name: str
    notify_groups: tuple[str, ...]
    transfer_groups: tuple[str, ...]
    notify_addresses: tuple[str, ...]
    transfer_addresses: tuple[str, ...]
    zones: tuple[str, ...]
    status: str

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        for field in (
            "notify_groups",
            "transfer_groups",
            "notify_addresses",
            "transfer_addresses",
            "zones",
        ):
            data[field] = list(data[field])
        return data


@dataclass(frozen=True, slots=True)
class BindSecondaryReport:
    groups: tuple[SecondaryGroupReport, ...]
    pairs: tuple[SecondaryPairReport, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "groups": [item.to_dict() for item in self.groups],
            "pairs": [item.to_dict() for item in self.pairs],
        }


class BindSecondaryReporter:
    NOTIFY_DIRECTIVES = {"also-notify", "allow-notify"}
    TRANSFER_DIRECTIVES = {"allow-transfer", "primaries"}

    def build(self, inventory: BindAccessInventory) -> BindSecondaryReport:
        definitions = {item.name.casefold(): item for item in inventory.definitions}
        roles: dict[str, set[str]] = {}
        zones: dict[str, set[str]] = {}
        counts: dict[str, int] = {}
        for usage in inventory.usages:
            role = self._role(usage.directive)
            if role is None:
                continue
            for value in usage.values:
                key = value.lstrip("!").casefold()
                if key not in definitions:
                    continue
                roles.setdefault(key, set()).add(role)
                counts[key] = counts.get(key, 0) + 1
                if usage.zone:
                    zones.setdefault(key, set()).add(usage.zone)

        relevant = [
            item
            for item in inventory.definitions
            if item.name.casefold() in roles
            or self._base_name(item.name) != item.name.casefold()
        ]
        groups = tuple(
            SecondaryGroupReport(
                name=item.name,
                kind=item.kind,
                entries=item.entries,
                roles=tuple(sorted(roles.get(item.name.casefold(), set()))),
                zones=tuple(sorted(zones.get(item.name.casefold(), set()))),
                usage_count=counts.get(item.name.casefold(), 0),
                source=str(item.source),
                line=item.line,
            )
            for item in sorted(relevant, key=lambda value: value.name.casefold())
        )

        by_base: dict[str, list[SecondaryGroupReport]] = {}
        for group in groups:
            by_base.setdefault(self._base_name(group.name), []).append(group)
        pairs: list[SecondaryPairReport] = []
        for base, members in sorted(by_base.items()):
            notify = [group for group in members if "notify" in group.roles]
            transfer = [group for group in members if "transfer" in group.roles]
            all_zones = sorted({zone for group in members for zone in group.zones})
            status = "PASS" if notify and transfer else "WARN"
            pairs.append(
                SecondaryPairReport(
                    name=base,
                    notify_groups=tuple(group.name for group in notify),
                    transfer_groups=tuple(group.name for group in transfer),
                    notify_addresses=tuple(
                        dict.fromkeys(
                            entry for group in notify for entry in group.entries
                        )
                    ),
                    transfer_addresses=tuple(
                        dict.fromkeys(
                            entry for group in transfer for entry in group.entries
                        )
                    ),
                    zones=tuple(all_zones),
                    status=status,
                )
            )
        return BindSecondaryReport(groups, tuple(pairs))

    def _role(self, directive: str) -> str | None:
        if directive in self.NOTIFY_DIRECTIVES:
            return "notify"
        if directive in self.TRANSFER_DIRECTIVES:
            return "transfer"
        return None

    @staticmethod
    def _base_name(name: str) -> str:
        return re.sub(r"[-_.](?:notify|transfer|secondary|slave)$", "", name.casefold())
