"""Odczytowy raport gotowości istniejącego BIND do importu przez ZoneCTL."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .bind_access_inventory import BindAccessInventoryReader
from .bind_environment_report import BindEnvironmentReporter
from .managed_zone_migration import ManagedZoneMigrationPlanner


@dataclass(frozen=True, slots=True)
class OnboardingClass:
    state: str
    count: int
    description: str


@dataclass(frozen=True, slots=True)
class OnboardingCandidate:
    name: str
    zone_type: str
    declaration: str
    zone_file: str | None


@dataclass(frozen=True, slots=True)
class BindOnboardingReport:
    root_config: str
    config_files: int
    zones: int
    dnssec_zones: int
    classes: tuple[OnboardingClass, ...]
    acl_definitions: int
    secondary_groups: int
    rpz_integrations: int
    rpz_modes: tuple[str, ...]
    candidates: tuple[OnboardingCandidate, ...]
    import_candidates: int
    blocked: int
    next_action: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class BindOnboardingReporter:
    """Łączy istniejące inwentaryzacje bez modyfikowania konfiguracji."""

    _descriptions = {
        "MANAGED": "deklaracje już zarządzane przez ZoneCTL",
        "LEGACY": "kandydaci do planowanego importu",
        "EXTERNAL": "konfiguracja pozostająca pod zarządem zewnętrznym",
        "BLOCKED": "elementy wymagające osobnego profilu lub decyzji",
    }

    def __init__(self, root_config: Path = Path("/etc/bind/named.conf")) -> None:
        self.root_config = root_config

    def collect(self) -> BindOnboardingReport:
        environment = BindEnvironmentReporter(self.root_config).collect()
        migration = ManagedZoneMigrationPlanner(root_config=self.root_config).inventory()
        access = BindAccessInventoryReader(self.root_config).collect()
        counts = {state: 0 for state in self._descriptions}
        for item in migration:
            state = self._normalise_state(item.state)
            counts[state] += 1
        secondary_groups = sum(
            item.kind.casefold() in {"primaries", "masters"}
            for item in access.definitions
        )
        classes = tuple(
            OnboardingClass(state, counts[state], description)
            for state, description in self._descriptions.items()
        )
        candidates = counts["LEGACY"]
        candidate_items = tuple(
            OnboardingCandidate(
                name=item.name,
                zone_type=item.zone_type,
                declaration=str(item.config_file),
                zone_file=str(item.source_file) if item.source_file else None,
            )
            for item in migration
            if self._normalise_state(item.state) == "LEGACY"
        )
        next_action = (
            "Przejrzyj kandydatów i utwórz osobne plany importu; nic nie jest importowane automatycznie."
            if candidates
            else "Nie wykryto zwykłych stref wymagających importu."
        )
        return BindOnboardingReport(
            root_config=environment.root_config,
            config_files=len(environment.config_files),
            zones=environment.zone_count,
            dnssec_zones=environment.dnssec_count,
            classes=classes,
            acl_definitions=sum(item.kind.casefold() == "acl" for item in access.definitions),
            secondary_groups=secondary_groups,
            rpz_integrations=len(environment.rpz),
            rpz_modes=tuple(sorted({item.mode for item in environment.rpz})),
            candidates=candidate_items,
            import_candidates=candidates,
            blocked=counts["BLOCKED"],
            next_action=next_action,
        )

    @staticmethod
    def _normalise_state(state: str) -> str:
        value = state.casefold()
        if value == "managed":
            return "MANAGED"
        if value == "legacy_primary":
            return "LEGACY"
        if value.startswith("external"):
            return "EXTERNAL"
        return "BLOCKED"
