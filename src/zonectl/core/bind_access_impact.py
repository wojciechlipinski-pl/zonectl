"""Read-only dependency and change-impact report for BIND named lists."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .bind_access_inventory import BindAccessInventory, BindListUsage


class BindAccessImpactError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BindAccessImpactUsage:
    directive: str
    role: str
    source: str
    line: int
    zone: str | None
    via: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["via"] = list(self.via)
        return data


@dataclass(frozen=True, slots=True)
class BindAccessImpactReport:
    name: str
    kind: str
    source: str
    line: int
    current_entries: tuple[str, ...]
    candidate_entries: tuple[str, ...]
    added_entries: tuple[str, ...]
    removed_entries: tuple[str, ...]
    roles: tuple[str, ...]
    zones: tuple[str, ...]
    usages: tuple[BindAccessImpactUsage, ...]
    dependent_definitions: tuple[str, ...]
    risk: str
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        for field in (
            "current_entries", "candidate_entries", "added_entries",
            "removed_entries", "roles", "zones", "dependent_definitions",
            "blockers",
        ):
            data[field] = list(data[field])
        data["usages"] = [usage.to_dict() for usage in self.usages]
        return data


class BindAccessImpactReporter:
    ROLE_BY_DIRECTIVE = {
        "allow-update": "administration",
        "allow-recursion": "recursion",
        "allow-query-cache": "recursion",
        "allow-query": "query",
        "allow-transfer": "transfer",
        "allow-notify": "notify",
        "also-notify": "notify",
        "primaries": "primaries",
    }

    def build(
        self,
        inventory: BindAccessInventory,
        name: str,
        candidate_entries: tuple[str, ...] | list[str] | None = None,
    ) -> BindAccessImpactReport:
        definitions = {
            item.name.casefold(): item for item in inventory.definitions
        }
        key = name.casefold()
        definition = definitions.get(key)
        if definition is None:
            raise BindAccessImpactError(f"Nie znaleziono definicji: {name}")
        if sum(1 for item in inventory.definitions if item.name.casefold() == key) != 1:
            raise BindAccessImpactError(
                f"Definicja {name} nie jest jednoznaczna"
            )

        graph = {
            item.name.casefold(): tuple(
                value.lstrip("!").casefold()
                for value in item.entries
                if value.lstrip("!").casefold() in definitions
            )
            for item in inventory.definitions
        }
        blockers = self._cycle_blockers(graph, key, definitions)
        dependents = self._reverse_closure(graph, key)
        affected = {key, *dependents}
        usages: list[BindAccessImpactUsage] = []
        for usage in inventory.usages:
            referenced = {
                value.lstrip("!").casefold() for value in usage.values
            }
            matches = sorted(referenced & affected)
            if not matches:
                continue
            usages.append(
                BindAccessImpactUsage(
                    directive=usage.directive,
                    role=self.ROLE_BY_DIRECTIVE.get(usage.directive, "other"),
                    source=str(usage.source),
                    line=usage.line,
                    zone=usage.zone,
                    via=tuple(definitions[item].name for item in matches),
                )
            )

        current = definition.entries
        candidate = tuple(candidate_entries) if candidate_entries is not None else current
        current_keys = {self._normalize(item): item for item in current}
        candidate_keys = {self._normalize(item): item for item in candidate}
        added = tuple(
            item for item in candidate
            if self._normalize(item) not in current_keys
        )
        removed = tuple(
            item for item in current
            if self._normalize(item) not in candidate_keys
        )
        roles = tuple(sorted({usage.role for usage in usages}))
        zones = tuple(sorted({usage.zone for usage in usages if usage.zone}))
        if blockers:
            risk = "INDETERMINATE"
        elif not added and not removed:
            risk = "NONE"
        elif removed and "administration" in roles:
            risk = "HIGH"
        elif removed and usages:
            risk = "MEDIUM"
        elif usages:
            risk = "LOW"
        else:
            risk = "NONE"
        return BindAccessImpactReport(
            name=definition.name,
            kind=definition.kind,
            source=str(definition.source),
            line=definition.line,
            current_entries=current,
            candidate_entries=candidate,
            added_entries=added,
            removed_entries=removed,
            roles=roles,
            zones=zones,
            usages=tuple(usages),
            dependent_definitions=tuple(
                definitions[item].name for item in sorted(dependents)
            ),
            risk=risk,
            blockers=tuple(blockers),
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().casefold()

    @staticmethod
    def _reverse_closure(graph: dict[str, tuple[str, ...]], target: str) -> set[str]:
        result: set[str] = set()
        pending = [target]
        while pending:
            wanted = pending.pop()
            for parent, children in graph.items():
                if wanted in children and parent not in result and parent != target:
                    result.add(parent)
                    pending.append(parent)
        return result

    @staticmethod
    def _cycle_blockers(graph, target, definitions) -> list[str]:
        blockers: list[str] = []

        def visit(node: str, path: tuple[str, ...]) -> None:
            if node in path:
                cycle = path[path.index(node):] + (node,)
                label = " -> ".join(definitions[item].name for item in cycle)
                message = f"Cykliczne odwołanie ACL: {label}"
                if message not in blockers:
                    blockers.append(message)
                return
            for child in graph.get(node, ()):
                visit(child, path + (node,))

        visit(target, ())
        return blockers
