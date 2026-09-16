"""Read-only planning for migration between named BIND KASP policies."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .discovery import ZoneConfig
from .dnssec_enable_plan import DnssecEnablePlanner
from .dnssec_policy_inventory import DnssecPolicy, DnssecPolicyInventory


class DnssecPolicyMigrationPlanError(ValueError):
    """A policy migration request is unsafe, ambiguous, or inconsistent."""


@dataclass(frozen=True, slots=True)
class PolicyMigrationProfile:
    """Allowlisted policy facts used by a migration plan."""

    name: str
    safety: str
    bind_compatibility: str
    key_model: str
    algorithms: tuple[str, ...]
    roles: tuple[str, ...]
    lifetimes: tuple[str, ...]
    publication_timing: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DnssecPolicyMigrationPlan:
    """Side-effect-free declaration change and trust-impact description."""

    zone: str
    declaration_file: Path
    source: PolicyMigrationProfile
    target: PolicyMigrationProfile
    ds_impact: str
    ds_guidance: str
    safety_status: str
    warnings: tuple[str, ...]
    review_acknowledged: bool
    candidate_validation: str
    candidate_validation_message: str
    original_text: str
    candidate_text: str
    unified_diff: str
    differences: tuple[str, ...]
    actions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a stable JSON-safe plan."""

        payload = asdict(self)
        payload["declaration_file"] = str(self.declaration_file)
        return payload


class DnssecPolicyMigrationPlanner:
    """Build a validated plan without changing BIND or registrar data."""

    _name = re.compile(r"[A-Za-z0-9_.-]+")
    _policy = re.compile(r"\bdnssec-policy\s+(?P<name>[^;\s]+)\s*;", re.I)

    def __init__(self, root_config: Path | None = None) -> None:
        self.root_config = root_config

    @staticmethod
    def _find(inventory: DnssecPolicyInventory, name: str) -> DnssecPolicy:
        policy = next(
            (
                item
                for item in inventory.policies
                if item.name.casefold() == name.casefold()
            ),
            None,
        )
        if policy is None:
            raise DnssecPolicyMigrationPlanError(
                f"Polityka {name} nie występuje w wykrytym inwentarzu BIND"
            )
        return policy

    @staticmethod
    def _profile(policy: DnssecPolicy) -> PolicyMigrationProfile:
        roles = tuple(dict.fromkeys(key.role for key in policy.keys))
        role_set = set(roles)
        model = (
            "CSK"
            if role_set == {"CSK"}
            else "KSK+ZSK"
            if {"KSK", "ZSK"}.issubset(role_set)
            else "+".join(roles) or "UNKNOWN"
        )
        timing = policy.timing
        publication = tuple(
            value
            for value in (
                f"dnskey-ttl={timing.dnskey_ttl}" if timing.dnskey_ttl else None,
                f"parent-ds-ttl={timing.parent_ds_ttl}"
                if timing.parent_ds_ttl
                else None,
                f"publish-safety={timing.publish_safety}"
                if timing.publish_safety
                else None,
                f"retire-safety={timing.retire_safety}"
                if timing.retire_safety
                else None,
                f"zone-propagation-delay={timing.zone_propagation_delay}"
                if timing.zone_propagation_delay
                else None,
                f"parent-propagation-delay={timing.parent_propagation_delay}"
                if timing.parent_propagation_delay
                else None,
            )
            if value is not None
        )
        return PolicyMigrationProfile(
            name=policy.name,
            safety=policy.status,
            bind_compatibility=policy.bind_compatibility,
            key_model=model,
            algorithms=tuple(dict.fromkeys(key.algorithm for key in policy.keys)),
            roles=roles,
            lifetimes=tuple(f"{key.role}={key.lifetime}" for key in policy.keys),
            publication_timing=publication,
            warnings=policy.warnings + policy.compatibility_findings,
        )

    @staticmethod
    def _gate(policy: DnssecPolicy, *, target: bool, acknowledged: bool) -> None:
        blocked_safety = {
            "BLOCKED",
            "UNKNOWN",
            "NOT_CHECKED",
            "TRANSITIONAL",
            "UNSIGNED",
        }
        if policy.name.casefold() in {"none", "insecure"}:
            raise DnssecPolicyMigrationPlanError(
                f"Polityka {policy.name} nie jest podpisującą polityką migracji"
            )
        if policy.status in blocked_safety:
            raise DnssecPolicyMigrationPlanError(
                f"Bezpieczeństwo polityki {policy.name}: {policy.status}"
            )
        if policy.bind_compatibility in {"BLOCKED", "UNKNOWN", "NOT_CHECKED"}:
            raise DnssecPolicyMigrationPlanError(
                f"Zgodność polityki {policy.name} z BIND: {policy.bind_compatibility}"
            )
        if target and policy.bind_compatibility == "REVIEW" and not acknowledged:
            raise DnssecPolicyMigrationPlanError(
                "Docelowa polityka REVIEW wymaga jawnego potwierdzenia"
            )

    def plan(
        self,
        zone: ZoneConfig,
        *,
        source_policy: str,
        target_policy: str,
        policy_inventory: DnssecPolicyInventory,
        acknowledge_policy_review: bool = False,
    ) -> DnssecPolicyMigrationPlan:
        """Compare policies and validate a candidate declaration."""

        source_policy, target_policy = source_policy.strip(), target_policy.strip()
        if not self._name.fullmatch(source_policy) or not self._name.fullmatch(
            target_policy
        ):
            raise DnssecPolicyMigrationPlanError("Niepoprawna nazwa dnssec-policy")
        if source_policy.casefold() == target_policy.casefold():
            raise DnssecPolicyMigrationPlanError(
                "Polityka docelowa musi różnić się od źródłowej"
            )
        if not zone.is_primary or not zone.dnssec_policy or not zone.inline_signing:
            raise DnssecPolicyMigrationPlanError(
                "Migracja wymaga aktywnej, podpisanej strefy primary z inline-signing"
            )
        if zone.dnssec_policy.casefold() != source_policy.casefold():
            raise DnssecPolicyMigrationPlanError(
                f"Jawna polityka źródłowa {source_policy} nie odpowiada deklaracji {zone.dnssec_policy}"
            )
        source = self._find(policy_inventory, source_policy)
        target = self._find(policy_inventory, target_policy)
        self._gate(source, target=False, acknowledged=True)
        self._gate(target, target=True, acknowledged=acknowledge_policy_review)
        original = zone.config_file.read_text(encoding="utf-8")
        opening, closing = DnssecEnablePlanner._target_block(original, zone.name)
        body = original[opening + 1 : closing]
        matches = list(self._policy.finditer(body))
        if (
            len(matches) != 1
            or matches[0].group("name").strip("\"'").casefold()
            != source_policy.casefold()
        ):
            raise DnssecPolicyMigrationPlanError(
                "Deklaracja nie zawiera dokładnie jednej oczekiwanej polityki"
            )
        candidate_body = self._policy.sub(
            f"dnssec-policy {target.name};", body, count=1
        )
        candidate = original[: opening + 1] + candidate_body + original[closing:]
        validation, message = "NOT_RUN", "Nie wskazano root_config"
        if self.root_config is not None:
            source_file = zone.source_file or zone.config_file
            ok, message = DnssecEnablePlanner._validate_candidate(
                self.root_config, zone.config_file, candidate, source_file, source_file
            )
            validation = "PASS" if ok else "BLOCKED"
            if not ok:
                raise DnssecPolicyMigrationPlanError(
                    f"named-checkconf odrzucił kandydata: {message}"
                )
        old, new = self._profile(source), self._profile(target)
        differences = tuple(
            f"{label}: {left or ('-',)} -> {right or ('-',)}"
            for label, left, right in (
                ("algorithms", old.algorithms, new.algorithms),
                ("roles", old.roles, new.roles),
                ("lifetimes", old.lifetimes, new.lifetimes),
                ("publication", old.publication_timing, new.publication_timing),
            )
            if left != right
        )
        ds_impact = (
            "CHANGE_REQUIRED"
            if old.algorithms != new.algorithms or old.key_model != new.key_model
            else "REVIEW_REQUIRED"
        )
        return DnssecPolicyMigrationPlan(
            zone=zone.name,
            declaration_file=zone.config_file,
            source=old,
            target=new,
            ds_impact=ds_impact,
            ds_guidance=(
                "ZoneCTL nigdy nie zmienia DS u rejestratora. Po pojawieniu się nowych "
                "DNSKEY porównaj oczekiwany DS i wykonaj wskazaną zmianę ręcznie; "
                "przejście wymaga zgodnej obserwacji wielu publicznych resolverów."
            ),
            safety_status="REVIEW" if target.bind_compatibility == "REVIEW" else "PASS",
            warnings=tuple(dict.fromkeys(old.warnings + new.warnings)),
            review_acknowledged=acknowledge_policy_review,
            candidate_validation=validation,
            candidate_validation_message=message,
            original_text=original,
            candidate_text=candidate,
            unified_diff=DnssecEnablePlanner._unified_diff(
                original,
                candidate,
                fromfile=str(zone.config_file),
                tofile=f"{zone.config_file} (migracja {source.name} -> {target.name})",
            ),
            differences=differences,
            actions=(
                "utwórz chroniony backup deklaracji",
                "zapisz deklarację atomowo i uruchom named-checkconf",
                "wykonaj rndc reconfig i potwierdź załadowanie strefy oraz KASP",
                "obserwuj DNSKEY, RRSIG, KASP i DS bez przechodzenia na podstawie czasu",
                "zatrzymaj się bezpiecznie i wznów po wymaganej czynności operatora",
            ),
        )
