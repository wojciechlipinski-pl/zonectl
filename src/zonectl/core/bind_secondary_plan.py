"""Read-only validated plan for changing one BIND secondary group."""

from __future__ import annotations

import difflib
import ipaddress
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .bind_access_inventory import BindAccessInventoryReader
from .bind_access_impact import BindAccessImpactReport, BindAccessImpactReporter
from .bind_secondary_report import BindSecondaryReporter
from .discovery import BindConfigDiscovery
from .runner import run


class BindSecondaryPlanError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BindSecondaryPlan:
    name: str
    kind: str
    source: Path
    old_addresses: tuple[str, ...]
    new_addresses: tuple[str, ...]
    roles: tuple[str, ...]
    zones: tuple[str, ...]
    original_text: str
    candidate_text: str
    diff: str
    validation_ok: bool
    validation_message: str
    operational_addresses: tuple[str, ...] = ()
    impact: BindAccessImpactReport | None = None

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["source"] = str(self.source)
        for field in ("old_addresses", "new_addresses", "roles", "zones"):
            data[field] = list(data[field])
        return data


class BindSecondaryPlanner:
    _definition = re.compile(
        r'\b(?P<kind>acl|primaries|masters)\s+'
        r'(?:["\'](?P<quoted>[^"\']+)["\']|(?P<plain>[A-Za-z0-9_.-]+))\s*\{',
        re.IGNORECASE,
    )

    def __init__(self, root_config: Path = Path("/etc/bind/named.conf")) -> None:
        self.root_config = root_config.expanduser().resolve()

    def plan(self, name: str, addresses: list[str] | tuple[str, ...]) -> BindSecondaryPlan:
        normalized = self._validate_addresses(addresses)
        inventory = BindAccessInventoryReader(self.root_config).collect()
        definitions = [
            item for item in inventory.definitions
            if item.name.casefold() == name.casefold()
        ]
        if len(definitions) != 1:
            raise BindSecondaryPlanError(
                f"Grupa {name} ma {len(definitions)} aktywnych definicji; wymagano jednej"
            )
        definition = definitions[0]
        report = BindSecondaryReporter().build(inventory)
        group = next(
            (item for item in report.groups if item.name.casefold() == name.casefold()),
            None,
        )
        if group is None:
            raise BindSecondaryPlanError(
                f"Definicja {name} nie jest używaną grupą secondary"
            )
        original = definition.source.read_text(encoding="utf-8", errors="replace")
        masked = BindAccessInventoryReader._mask_comments(original)
        match = next(
            (
                item for item in self._definition.finditer(masked)
                if (item.group("quoted") or item.group("plain")).casefold()
                == name.casefold()
            ),
            None,
        )
        if match is None:
            raise BindSecondaryPlanError(f"Nie można wydzielić grupy {name}")
        opening = masked.find("{", match.start(), match.end())
        closing = BindConfigDiscovery._find_block_end(masked, opening, definition.source)
        body = original[opening + 1 : closing]
        replacement_body = self._format_body(body, normalized)
        candidate = original[: opening + 1] + replacement_body + original[closing:]
        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                candidate.splitlines(keepends=True),
                fromfile=str(definition.source),
                tofile=f"{definition.source} (kandydat secondary)",
            )
        )
        validation_ok, validation_message = self._validate_candidate(
            definition.source, candidate
        )
        impact = BindAccessImpactReporter().build(
            inventory, definition.name, normalized
        )
        if impact.blockers:
            validation_ok = False
            validation_message = (
                validation_message + "; " if validation_message else ""
            ) + "raport wpływu: " + "; ".join(impact.blockers)
        return BindSecondaryPlan(
            name=definition.name,
            kind=definition.kind,
            source=definition.source,
            old_addresses=definition.entries,
            new_addresses=normalized,
            roles=group.roles,
            zones=group.zones,
            operational_addresses=(normalized if "notify" in group.roles else ()),
            original_text=original,
            candidate_text=candidate,
            diff=diff,
            validation_ok=validation_ok,
            validation_message=validation_message,
            impact=impact,
        )

    @staticmethod
    def _validate_addresses(addresses) -> tuple[str, ...]:
        if not addresses:
            raise BindSecondaryPlanError("Grupa secondary nie może być pusta")
        result: list[str] = []
        seen: set[str] = set()
        for raw in addresses:
            try:
                value = str(ipaddress.ip_address(raw.strip()))
            except ValueError as exc:
                raise BindSecondaryPlanError(
                    f"Nieprawidłowy adres serwera secondary: {raw}"
                ) from exc
            if value in seen:
                raise BindSecondaryPlanError(f"Powtórzony adres: {value}")
            seen.add(value)
            result.append(value)
        return tuple(result)

    @staticmethod
    def _format_body(body: str, addresses: tuple[str, ...]) -> str:
        multiline = "\n" in body or "\r" in body
        if not multiline:
            leading = body[: len(body) - len(body.lstrip())]
            trailing = body[len(body.rstrip()) :]
            return leading + " ".join(f"{item};" for item in addresses) + trailing
        newline = "\r\n" if "\r\n" in body else "\n"
        lines = body.splitlines()
        indent = "    "
        for line in lines:
            if line.strip():
                indent = line[: len(line) - len(line.lstrip())]
                break
        prefix = newline if body.startswith(("\n", "\r\n")) else ""
        suffix = newline + (lines[-1] if lines and not lines[-1].strip() else "")
        return prefix + newline.join(f"{indent}{item};" for item in addresses) + suffix

    def _validate_candidate(self, source: Path, candidate: str) -> tuple[bool, str]:
        temporary = Path(tempfile.mkdtemp(prefix="zonectl-secondary-plan-"))
        try:
            config_root = self.root_config.parent
            paths = BindConfigDiscovery(self.root_config).discover().config_files
            for path in paths:
                target = temporary / path.relative_to(config_root)
                target.parent.mkdir(parents=True, exist_ok=True)
                text = path.read_text(encoding="utf-8", errors="replace").replace(
                    str(config_root), str(temporary)
                )
                target.write_text(text, encoding="utf-8")
            target_source = temporary / source.relative_to(config_root)
            target_source.write_text(
                candidate.replace(str(config_root), str(temporary)), encoding="utf-8"
            )
            target_root = temporary / self.root_config.relative_to(config_root)
            outcome = run(["named-checkconf", str(target_root)], 30)
            detail = (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}"
            return outcome.returncode == 0, detail
        except (OSError, ValueError) as exc:
            return False, str(exc)
        finally:
            shutil.rmtree(temporary, ignore_errors=True)
