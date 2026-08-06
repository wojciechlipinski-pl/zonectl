"""Side-effect-free plan for safely withdrawing DNSSEC from a BIND zone."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .discovery import ZoneConfig
from .dnssec_enable_plan import DnssecEnablePlanner


class DnssecDisablePlanError(ValueError):
    """The requested DNSSEC withdrawal is unsafe or ambiguous."""


@dataclass(frozen=True, slots=True)
class DnssecDisablePlan:
    zone: str
    zone_file: Path
    declaration_file: Path
    key_directory: Path | None
    key_files: tuple[Path, ...]
    signing_artifacts: tuple[Path, ...]
    policy: str
    original_text: str
    candidate_text: str
    unified_diff: str
    actions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        for field in ("zone_file", "declaration_file", "key_directory"):
            value = payload[field]
            payload[field] = str(value) if value is not None else None
        payload["key_files"] = [str(path) for path in self.key_files]
        payload["signing_artifacts"] = [
            str(path) for path in self.signing_artifacts
        ]
        return payload


class DnssecDisablePlanner:
    """Build the final unsigned configuration without changing the system."""

    _policy = re.compile(
        r"(?m)^[ \t]*dnssec-policy\s+[^;]+;[ \t]*(?:\r?\n)?",
        re.IGNORECASE,
    )
    _inline = re.compile(
        r"(?m)^[ \t]*inline-signing\s+yes\s*;[ \t]*(?:\r?\n)?",
        re.IGNORECASE,
    )
    _key_directory = re.compile(
        r"(?m)^[ \t]*key-directory\s+[\"'][^\"']+[\"']\s*;"
        r"[ \t]*(?:\r?\n)?",
        re.IGNORECASE,
    )

    @staticmethod
    def _artifacts(zone_file: Path) -> tuple[Path, ...]:
        candidates = (
            zone_file.with_name(zone_file.name + ".jbk"),
            zone_file.with_name(zone_file.name + ".jnl"),
            zone_file.with_name(zone_file.name + ".signed"),
            zone_file.with_name(zone_file.name + ".signed.jnl"),
        )
        return tuple(path for path in candidates if path.exists())

    def plan(self, zone: ZoneConfig) -> DnssecDisablePlan:
        if not zone.is_primary:
            raise DnssecDisablePlanError(
                "DNSSEC można wycofać tylko na strefie primary"
            )
        if zone.source_file is None or not zone.source_exists:
            raise DnssecDisablePlanError("Brak aktywnego pliku strefy")
        if not zone.dnssec_policy or not zone.inline_signing:
            raise DnssecDisablePlanError(
                "Strefa nie ma pełnej konfiguracji dnssec-policy i inline-signing"
            )
        if not zone.config_file.is_file():
            raise DnssecDisablePlanError(
                f"Brak pliku deklaracji: {zone.config_file}"
            )

        original = zone.config_file.read_text(encoding="utf-8")
        try:
            opening, closing = DnssecEnablePlanner._target_block(
                original, zone.name
            )
        except ValueError as exc:
            raise DnssecDisablePlanError(str(exc)) from exc
        body = original[opening + 1 : closing]
        if not self._policy.search(body) or not self._inline.search(body):
            raise DnssecDisablePlanError(
                "Deklaracja strefy nie zawiera oczekiwanej konfiguracji DNSSEC"
            )

        candidate_body = self._policy.sub("", body, count=1)
        candidate_body = self._inline.sub("", candidate_body, count=1)
        candidate_body = self._key_directory.sub("", candidate_body, count=1)
        candidate = (
            original[: opening + 1]
            + candidate_body
            + original[closing:]
        )
        diff = DnssecEnablePlanner._unified_diff(
            original,
            candidate,
            fromfile=str(zone.config_file),
            tofile=f"{zone.config_file} (kandydat po wycofaniu DNSSEC)",
        )

        key_directory = zone.key_directory
        key_files = (
            tuple(sorted(key_directory.glob(f"K{zone.name.rstrip('.')}.*")))
            if key_directory is not None and key_directory.is_dir()
            else ()
        )
        zone_file = zone.source_file.resolve()
        return DnssecDisablePlan(
            zone=zone.name,
            zone_file=zone_file,
            declaration_file=zone.config_file,
            key_directory=key_directory,
            key_files=key_files,
            signing_artifacts=self._artifacts(zone_file),
            policy=zone.dnssec_policy,
            original_text=original,
            candidate_text=candidate,
            unified_diff=diff,
            actions=(
                "sprawdź aktywny łańcuch zaufania i zgodność DS",
                "wykonaj backup deklaracji, pliku strefy, kluczy i artefaktów podpisywania",
                "usuń DS u rejestratora; ZoneCTL nie zrobi tego automatycznie",
                "poczekaj, aż DS zniknie ze wszystkich kontrolowanych resolverów",
                "potwierdź stan withdrawn w KASP dopiero po pełnej kontroli",
                "poczekaj na bezpieczny stan KASP ze schowanymi DNSKEY i podpisami",
                "dopiero wtedy zastosuj pokazany diff konfiguracji BIND",
                "wykonaj named-checkconf, rndc reconfig i sprawdź strefę",
                "zachowaj pakiet odtworzeniowy; nie usuwaj automatycznie kluczy",
            ),
        )
