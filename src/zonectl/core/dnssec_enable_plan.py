"""Pozbawiony skutków ubocznych plan włączenia DNSSEC w BIND."""

from __future__ import annotations

import difflib
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .discovery import BindConfigDiscovery, ZoneConfig
from .dnssec_policy_inventory import (
    DnssecPolicy,
    DnssecPolicyInventory,
    PolicyKey,
    PolicyTiming,
)
from .runner import run


class DnssecEnablePlanError(ValueError):
    """Plan włączenia DNSSEC jest niebezpieczny albo niejednoznaczny."""


@dataclass(frozen=True, slots=True)
class DnssecEnablePlan:
    zone: str
    source_zone_file: Path
    target_zone_file: Path
    migration_required: bool
    declaration_file: Path
    key_directory: Path
    policy: str
    policy_safety: str
    bind_compatibility: str
    key_model: str
    algorithms: tuple[str, ...]
    rollover: tuple[str, ...]
    publication: tuple[str, ...]
    ds_guidance: str
    policy_warnings: tuple[str, ...]
    compatibility_findings: tuple[str, ...]
    review_acknowledged: bool
    candidate_validation: str
    candidate_validation_message: str
    original_text: str
    candidate_text: str
    unified_diff: str
    actions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        for field in (
            "source_zone_file",
            "target_zone_file",
            "declaration_file",
            "key_directory",
        ):
            payload[field] = str(payload[field])
        return payload


class DnssecEnablePlanner:
    """Buduje plan zmiany deklaracji strefy, ale niczego nie zapisuje."""

    _zone_start = re.compile(
        r'\bzone\s+["\'](?P<name>[^"\']+)["\']\s*(?:IN\s*)?\{',
        re.IGNORECASE,
    )
    _policy = re.compile(r"\bdnssec-policy\s+[^;]+;", re.IGNORECASE)
    _inline = re.compile(r"\binline-signing\s+(?:yes|no)\s*;", re.IGNORECASE)
    _file = re.compile(r'\bfile\s+["\'][^"\']+["\']\s*;', re.IGNORECASE)

    def __init__(
        self,
        root_config: Path | None = None,
        *,
        candidate_validator: Callable[[Path, Path, str, Path, Path], tuple[bool, str]]
        | None = None,
    ) -> None:
        self.root_config = root_config
        self.candidate_validator = candidate_validator or self._validate_candidate

    @staticmethod
    def _select_policy(
        inventory: DnssecPolicyInventory | None,
        name: str,
        acknowledge_review: bool,
    ) -> DnssecPolicy:
        policy: DnssecPolicy | None
        if inventory is None:
            if name != "default":
                raise DnssecEnablePlanError(
                    "Nazwana polityka musi pochodzić z wykrytego inwentarza BIND"
                )
            # Compatibility shim for callers of the historic public API. CLI and TUI
            # always pass a discovered inventory.
            policy = DnssecPolicy(
                "default",
                True,
                (PolicyKey("CSK", "ECDSAP256SHA256", "unlimited"),),
                True,
                False,
                None,
                None,
                PolicyTiming(),
                (),
                None,
                None,
                "PASS",
                (),
                (),
                "COMPATIBLE",
                (),
            )
        else:
            policy = next(
                (
                    item
                    for item in inventory.policies
                    if item.name.casefold() == name.casefold()
                ),
                None,
            )
            if policy is None:
                raise DnssecEnablePlanError(
                    f"Polityka {name} nie występuje w wykrytym inwentarzu BIND"
                )
        if policy.name in {"insecure", "none"} or policy.status in {
            "BLOCKED",
            "TRANSITIONAL",
            "UNSIGNED",
        }:
            raise DnssecEnablePlanError(
                f"Polityka {policy.name} ma klasyfikację bezpieczeństwa {policy.status}"
            )
        if policy.bind_compatibility in {"BLOCKED", "UNKNOWN", "NOT_CHECKED"}:
            raise DnssecEnablePlanError(
                f"Zgodność polityki {policy.name} z BIND: {policy.bind_compatibility}"
            )
        if policy.bind_compatibility == "REVIEW" and not acknowledge_review:
            raise DnssecEnablePlanError(
                "Polityka REVIEW wymaga jawnego --acknowledge-policy-review"
            )
        return policy

    @staticmethod
    def _key_model(policy: DnssecPolicy) -> str:
        roles = {key.role for key in policy.keys}
        if roles == {"CSK"}:
            return "CSK"
        if "KSK" in roles and "ZSK" in roles:
            return "KSK+ZSK"
        return "+".join(sorted(roles)) or "UNKNOWN"

    @staticmethod
    def _facts(policy: DnssecPolicy) -> tuple[tuple[str, ...], tuple[str, ...]]:
        rollover = tuple(f"{key.role}: lifetime={key.lifetime}" for key in policy.keys)
        timing = policy.timing
        publication = tuple(
            item
            for item in (
                f"DNSKEY TTL={timing.dnskey_ttl}" if timing.dnskey_ttl else None,
                f"parent DS TTL={timing.parent_ds_ttl}"
                if timing.parent_ds_ttl
                else None,
                f"publish safety={timing.publish_safety}"
                if timing.publish_safety
                else None,
                f"parent propagation={timing.parent_propagation_delay}"
                if timing.parent_propagation_delay
                else None,
                "CDNSKEY=tak" if policy.cdnskey is True else None,
                "CDS=" + ",".join(policy.cds_digest_types)
                if policy.cds_digest_types
                else None,
            )
            if item is not None
        )
        return rollover, publication

    @staticmethod
    def _display_lines(text: str) -> list[str]:
        """Normalizuje wyłącznie końcowe spacje na potrzeby czytelnego diffu."""
        result: list[str] = []
        for line in text.splitlines(keepends=True):
            ending = "\n" if line.endswith("\n") else ""
            content = line[:-1] if ending else line
            result.append(content.rstrip(" \t\r") + ending)
        return result

    @staticmethod
    def _unified_range(start: int, stop: int) -> str:
        length = stop - start
        if length == 1:
            return str(start + 1)
        if length == 0:
            start -= 1
        return f"{start + 1},{length}"

    @classmethod
    def _unified_diff(
        cls,
        original: str,
        candidate: str,
        *,
        fromfile: str,
        tofile: str,
    ) -> str:
        """Tworzy diff bez heurystyki autojunk mylącej powtarzalne bloki BIND."""
        before = cls._display_lines(original)
        after = cls._display_lines(candidate)
        matcher = difflib.SequenceMatcher(None, before, after, autojunk=False)
        groups = list(matcher.get_grouped_opcodes(3))
        if not groups:
            return ""
        output = [f"--- {fromfile}\n", f"+++ {tofile}\n"]
        for group in groups:
            first, last = group[0], group[-1]
            output.append(
                "@@ -"
                + cls._unified_range(first[1], last[2])
                + " +"
                + cls._unified_range(first[3], last[4])
                + " @@\n"
            )
            for tag, old_start, old_stop, new_start, new_stop in group:
                if tag in {"equal", "delete", "replace"}:
                    prefix = " " if tag == "equal" else "-"
                    output.extend(prefix + line for line in before[old_start:old_stop])
                if tag in {"insert", "replace"}:
                    output.extend("+" + line for line in after[new_start:new_stop])
        return "".join(output)

    @staticmethod
    def _matching_brace(text: str, opening: int) -> int | None:
        depth = 0
        quote: str | None = None
        escaped = False
        for index in range(opening, len(text)):
            character = text[index]
            if quote is not None:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == quote:
                    quote = None
                continue
            if character in {'"', "'"}:
                quote = character
            elif character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    return index
        return None

    @classmethod
    def _target_block(cls, text: str, zone: str) -> tuple[int, int]:
        wanted = zone.rstrip(".").casefold()
        matches: list[tuple[int, int]] = []
        position = 0
        while match := cls._zone_start.search(text, position):
            opening = text.find("{", match.start(), match.end())
            closing = cls._matching_brace(text, opening)
            if closing is None:
                raise DnssecEnablePlanError("Niedomknięty blok strefy w konfiguracji")
            if match.group("name").rstrip(".").casefold() == wanted:
                matches.append((opening, closing))
            position = closing + 1
        if not matches:
            raise DnssecEnablePlanError(
                f"Nie znaleziono deklaracji strefy {zone} w wskazanym pliku"
            )
        if len(matches) > 1:
            raise DnssecEnablePlanError(
                f"Deklaracja strefy {zone} występuje w pliku więcej niż raz"
            )
        return matches[0]

    def plan(
        self,
        zone: ZoneConfig,
        *,
        policy: str = "default",
        policy_inventory: DnssecPolicyInventory | None = None,
        acknowledge_policy_review: bool = False,
        key_directory: Path = Path("/var/lib/bind/keys"),
        zone_directory: Path = Path("/var/lib/bind/Primary"),
    ) -> DnssecEnablePlan:
        if not zone.is_primary:
            raise DnssecEnablePlanError("DNSSEC można włączyć tylko dla strefy primary")
        if zone.source_file is None or not zone.source_exists:
            raise DnssecEnablePlanError("Brak aktywnego pliku źródłowego strefy")
        if zone.dnssec_policy or zone.inline_signing:
            raise DnssecEnablePlanError("Strefa ma już konfigurację DNSSEC")
        policy = policy.strip()
        if not policy or not re.fullmatch(r"[A-Za-z0-9_.-]+", policy):
            raise DnssecEnablePlanError("Niepoprawna nazwa dnssec-policy")
        selected = self._select_policy(
            policy_inventory, policy, acknowledge_policy_review
        )
        policy = selected.name
        key_directory = key_directory.expanduser()
        if not key_directory.is_absolute():
            raise DnssecEnablePlanError("Katalog kluczy musi być ścieżką absolutną")
        zone_directory = zone_directory.expanduser()
        if not zone_directory.is_absolute():
            raise DnssecEnablePlanError("Katalog stref musi być ścieżką absolutną")
        source_zone_file = zone.source_file.resolve()
        target_zone_file = (zone_directory / zone.name.rstrip(".")).resolve()
        migration_required = source_zone_file != target_zone_file
        if migration_required and target_zone_file.exists():
            raise DnssecEnablePlanError(
                f"Docelowy plik strefy już istnieje: {target_zone_file}"
            )
        declaration = zone.config_file
        if not declaration.is_file():
            raise DnssecEnablePlanError(f"Brak pliku deklaracji: {declaration}")

        original = declaration.read_text(encoding="utf-8")
        opening, closing = self._target_block(original, zone.name)
        body = original[opening + 1 : closing]
        if self._policy.search(body) or self._inline.search(body):
            raise DnssecEnablePlanError(
                "Deklaracja zawiera już częściową konfigurację DNSSEC"
            )

        candidate_body = body
        if migration_required:
            if not self._file.search(candidate_body):
                raise DnssecEnablePlanError(
                    "Deklaracja strefy nie zawiera dyrektywy file"
                )
            candidate_body = self._file.sub(
                lambda _match: f'file "{target_zone_file}";',
                candidate_body,
                count=1,
            )
        prefix = "" if not candidate_body or candidate_body.endswith("\n") else "\n"
        addition = (
            f"{prefix}    dnssec-policy {policy};\n"
            "    inline-signing yes;\n"
            f'    key-directory "{key_directory}";\n'
        )
        candidate = (
            original[: opening + 1] + candidate_body + addition + original[closing:]
        )
        diff = self._unified_diff(
            original,
            candidate,
            fromfile=str(declaration),
            tofile=f"{declaration} (kandydat DNSSEC)",
        )
        validation, validation_message = "NOT_RUN", "Nie wskazano root_config"
        if self.root_config is not None:
            ok, validation_message = self.candidate_validator(
                self.root_config,
                declaration,
                candidate,
                source_zone_file,
                target_zone_file,
            )
            validation = "PASS" if ok else "BLOCKED"
            if not ok:
                raise DnssecEnablePlanError(
                    f"named-checkconf odrzucił kandydacką konfigurację: {validation_message}"
                )
        rollover, publication = self._facts(selected)
        algorithms = tuple(dict.fromkeys(key.algorithm for key in selected.keys))
        return DnssecEnablePlan(
            zone=zone.name,
            source_zone_file=source_zone_file,
            target_zone_file=target_zone_file,
            migration_required=migration_required,
            declaration_file=declaration,
            key_directory=key_directory,
            policy=policy,
            policy_safety=selected.status,
            bind_compatibility=selected.bind_compatibility,
            key_model=self._key_model(selected),
            algorithms=algorithms,
            rollover=rollover,
            publication=publication,
            ds_guidance=(
                "Po pojawieniu się DNSKEY oblicz DS SHA-256, opublikuj go ręcznie "
                "u rejestratora i potwierdź propagację; ZoneCTL nie zmienia DS."
            ),
            policy_warnings=selected.warnings,
            compatibility_findings=selected.compatibility_findings,
            review_acknowledged=acknowledge_policy_review,
            candidate_validation=validation,
            candidate_validation_message=validation_message,
            original_text=original,
            candidate_text=candidate,
            unified_diff=diff,
            actions=(
                f"wykonaj backup {declaration}",
                *(
                    (
                        f"wykonaj backup {source_zone_file}",
                        f"skopiuj atomowo strefę do {target_zone_file}",
                        "zachowaj oryginalny plik do zakończenia całej transakcji",
                    )
                    if migration_required
                    else ()
                ),
                f"przygotuj chroniony katalog kluczy {key_directory}",
                f"dodaj dnssec-policy {policy}, inline-signing i key-directory",
                "wykonaj named-checkconf na kandydackiej konfiguracji",
                "zastosuj konfigurację atomowo i wykonaj rndc reconfig",
                f"poczekaj na DNSKEY i RRSIG strefy {zone.name}",
                "oblicz DS SHA-256 i pokaż operatorowi do publikacji",
                "nie publikuj ani nie usuwaj DS automatycznie",
            ),
        )

    @staticmethod
    def _validate_candidate(
        root_config: Path,
        declaration: Path,
        candidate: str,
        source_zone_file: Path,
        target_zone_file: Path,
    ) -> tuple[bool, str]:
        temporary = Path(tempfile.mkdtemp(prefix="zonectl-dnssec-plan-"))
        try:
            config_root = root_config.parent.resolve()
            paths = BindConfigDiscovery(root_config).discover().config_files
            for path in paths:
                target = temporary / path.resolve().relative_to(config_root)
                target.parent.mkdir(parents=True, exist_ok=True)
                copied = path.read_text(encoding="utf-8", errors="replace").replace(
                    str(config_root), str(temporary)
                )
                target.write_text(copied, encoding="utf-8")
            declaration_copy = temporary / declaration.resolve().relative_to(
                config_root
            )
            target_copy = temporary / "zone-data" / target_zone_file.name
            candidate_copy = candidate.replace(str(config_root), str(temporary))
            candidate_copy = candidate_copy.replace(
                str(target_zone_file), str(target_copy)
            )
            declaration_copy.write_text(candidate_copy, encoding="utf-8")
            if target_zone_file != source_zone_file:
                target_copy.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_zone_file, target_copy)
            root_copy = temporary / root_config.resolve().relative_to(config_root)
            outcome = run(["named-checkconf", str(root_copy)], 30)
            detail = (outcome.stdout or outcome.stderr).strip() or (
                f"kod {outcome.returncode}"
            )
            return outcome.returncode == 0, detail
        except (OSError, ValueError) as exc:
            return False, str(exc)
        finally:
            shutil.rmtree(temporary, ignore_errors=True)
