"""Read-only plan for relocating an already managed BIND zone file."""

from __future__ import annotations

import difflib
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .discovery import BindConfigDiscovery, BindDiscoveryError
from .zone_lifecycle import ZoneLifecycleError, normalize_zone_name


class ManagedZoneRelocationError(RuntimeError):
    """A managed zone file cannot be relocated safely."""


@dataclass(frozen=True, slots=True)
class ManagedZoneRelocationPlan:
    zone: str
    declaration_file: Path
    source_file: Path
    target_file: Path
    declaration_original: str
    declaration_candidate: str
    declaration_diff: str
    actions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        for field in ("declaration_file", "source_file", "target_file"):
            payload[field] = str(payload[field])
        payload["actions"] = list(self.actions)
        return payload


class ManagedZoneRelocationPlanner:
    """Plan relocation without changing the declaration, file or BIND."""

    _file_re = re.compile(
        r'(?P<prefix>\bfile\s+["\'])(?P<path>[^"\']+)(?P<suffix>["\']\s*;)',
        re.IGNORECASE,
    )

    def __init__(
        self,
        *,
        root_config: Path = Path("/etc/bind/named.conf"),
        managed_zone_directory: Path = Path("/etc/bind/zonectl-zones.d"),
        target_directory: Path = Path("/var/lib/bind/Primary"),
    ) -> None:
        self.root_config = root_config.expanduser().resolve()
        self.managed_zone_directory = managed_zone_directory.expanduser().resolve()
        self.target_directory = target_directory.expanduser().resolve()

    def plan(self, zone_name: str) -> ManagedZoneRelocationPlan:
        try:
            wanted = normalize_zone_name(zone_name)
            zone = BindConfigDiscovery(self.root_config).discover().zone(wanted)
        except (ZoneLifecycleError, BindDiscoveryError) as exc:
            raise ManagedZoneRelocationError(str(exc)) from exc

        declaration = zone.config_file.resolve()
        if declaration.parent != self.managed_zone_directory:
            raise ManagedZoneRelocationError(
                "Relokacja dotyczy wyłącznie deklaracji w zonectl-zones.d"
            )
        if not zone.is_primary or zone.source_file is None:
            raise ManagedZoneRelocationError("Strefa nie jest strefą primary z plikiem")
        source = zone.source_file.resolve()
        target = (self.target_directory / source.name).resolve()
        if source.parent == self.target_directory:
            raise ManagedZoneRelocationError("Plik strefy jest już w katalogu docelowym")
        if not source.is_file():
            raise ManagedZoneRelocationError(f"Brak pliku źródłowego: {source}")
        if target.exists():
            raise ManagedZoneRelocationError(f"Plik docelowy już istnieje: {target}")

        original = declaration.read_text(encoding="utf-8")
        matches = list(self._file_re.finditer(original))
        if len(matches) != 1 or Path(matches[0].group("path")).resolve() != source:
            raise ManagedZoneRelocationError(
                "Nie można jednoznacznie zmienić dyrektywy file w deklaracji"
            )
        candidate = self._file_re.sub(
            lambda match: match.group("prefix") + str(target) + match.group("suffix"),
            original,
            count=1,
        )
        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                candidate.splitlines(keepends=True),
                fromfile=str(declaration),
                tofile=f"{declaration} (po relokacji)",
            )
        )
        return ManagedZoneRelocationPlan(
            wanted,
            declaration,
            source,
            target,
            original,
            candidate,
            diff,
            (
                "wykonaj backup deklaracji i źródłowego pliku strefy",
                f"skopiuj plik kandydacki do {target}",
                f"zweryfikuj kandydat przez named-checkzone {wanted}",
                "zmień wyłącznie dyrektywę file w zarządzanej deklaracji",
                "wykonaj named-checkconf i rndc reconfig",
                "potwierdź ścieżkę i stan strefy przez rndc zonestatus",
                "po sukcesie usuń starą kopię; po błędzie wykonaj rollback",
            ),
        )
