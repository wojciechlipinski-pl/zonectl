"""Persistent privacy-safe state for DNSSEC policy migration."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path


class MigrationPhase(StrEnum):
    """Explicit resumable phases of a policy migration."""

    PLANNED = "PLANNED"
    POLICY_APPLIED = "POLICY_APPLIED"
    WAITING_DNSKEY = "WAITING_DNSKEY"
    WAITING_DS = "WAITING_DS"
    WAITING_PROPAGATION = "WAITING_PROPAGATION"
    READY_TO_FINALIZE = "READY_TO_FINALIZE"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


@dataclass(frozen=True, slots=True)
class MigrationEvidence:
    """Allowlisted observation summary; never stores keys, hashes, or addresses."""

    loaded: bool = False
    kasp_target_policy: bool = False
    dnskey_present: bool = False
    rrsig_present: bool = False
    authoritative_consistent: bool = False
    resolver_count: int = 0
    resolvers_consistent: bool = False
    target_ds_observed: bool = False
    source_ds_observed: bool = False
    checked_at: str | None = None


@dataclass(slots=True)
class DnssecPolicyMigrationState:
    """Durable migration manifest containing only operational metadata."""

    schema_version: int
    transaction_id: str
    zone: str
    source_policy: str
    target_policy: str
    ds_impact: str
    phase: MigrationPhase
    next_action: str
    source_key_ids: tuple[str, ...]
    declaration_file: str
    backup_file: str | None = None
    rollback_allowed: bool = True
    point_of_no_return: bool = False
    failure: str | None = None
    evidence: MigrationEvidence = field(default_factory=MigrationEvidence)
    updated_at: str = field(default_factory=lambda: _now())
    history: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return the stable, privacy-safe manifest representation."""

        payload = asdict(self)
        payload["phase"] = self.phase.value
        return payload

    def transition(
        self,
        phase: MigrationPhase,
        next_action: str,
        evidence: MigrationEvidence | None = None,
    ) -> None:
        """Record one explicit phase transition."""

        self.phase = phase
        self.next_action = next_action
        self.updated_at = _now()
        if evidence is not None:
            self.evidence = evidence
        if len(self.history) >= 128:
            self.history = self.history[-127:]
        self.history.append({"phase": phase.value, "at": self.updated_at})


class MigrationStateError(ValueError):
    """A migration manifest is corrupt, unsafe, or has an unsupported schema."""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


_TOP_LEVEL_FIELDS = {
    "schema_version",
    "transaction_id",
    "zone",
    "source_policy",
    "target_policy",
    "ds_impact",
    "phase",
    "next_action",
    "source_key_ids",
    "declaration_file",
    "backup_file",
    "rollback_allowed",
    "point_of_no_return",
    "failure",
    "evidence",
    "updated_at",
    "history",
}
_EVIDENCE_FIELDS = {item.name for item in fields(MigrationEvidence)}
_HISTORY_FIELDS = {"phase", "at"}
_TXID = re.compile(r"[0-9]{8}-[0-9]{6}-policy-migration-[0-9a-f]{8}")
_ZONE = re.compile(
    r"(?=.{1,253}\Z)(?:[A-Za-z0-9_](?:[A-Za-z0-9_-]{0,62})\.)*[A-Za-z0-9_](?:[A-Za-z0-9_-]{0,62})\.?"
)
_POLICY = re.compile(r"[A-Za-z0-9_.-]{1,128}")
_KEY_ID = re.compile(r"(?:0|[1-9][0-9]{0,4}):(?:0|[1-9][0-9]{0,2})")
_DS_IMPACTS = {"CHANGE_REQUIRED", "REVIEW_REQUIRED"}


def _text(value: object, field_name: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value or len(value) > 1000:
        raise MigrationStateError(f"Niepoprawne pole {field_name}")
    if any(ord(character) < 32 for character in value):
        raise MigrationStateError(f"Niepoprawne pole {field_name}")
    return value


def _timestamp(value: object, field_name: str) -> str:
    text = _text(value, field_name)
    assert text is not None
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MigrationStateError(f"Niepoprawne pole {field_name}") from exc
    return text


def _relative_declaration(value: object) -> str:
    text = _text(value, "declaration_file")
    assert text is not None
    path = Path(text)
    if path.is_absolute() or not 1 <= len(path.parts) <= 8 or ".." in path.parts:
        raise MigrationStateError("Niepoprawne pole declaration_file")
    if len(text) > 512 or any(
        not re.fullmatch(r"[A-Za-z0-9_.-]{1,255}", part) for part in path.parts
    ):
        raise MigrationStateError("Niepoprawne pole declaration_file")
    return path.as_posix()


class DnssecPolicyMigrationStore:
    """Atomically save and strictly load per-zone migration manifests."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    @staticmethod
    def _safe_zone(zone: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", zone.rstrip(".")).strip("._") or "zone"

    def path_for(self, zone: str) -> Path:
        """Return the deterministic state path for a zone."""

        return self.directory / f"{self._safe_zone(zone)}.json"

    def save(self, state: DnssecPolicyMigrationState) -> Path:
        """Persist state atomically with restrictive permissions."""

        self.directory.mkdir(parents=True, exist_ok=True, mode=0o750)
        os.chmod(self.directory, 0o750)
        self._decode(state.to_dict(), expected_zone=state.zone)
        path = self.path_for(state.zone)
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=self.directory)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(state.to_dict(), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o640)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return path

    def load(self, zone: str) -> DnssecPolicyMigrationState:
        """Load and validate a manifest without accepting unknown structures."""

        path = self.path_for(zone)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            state = self._decode(payload, expected_zone=zone)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            if isinstance(exc, MigrationStateError):
                raise
            raise MigrationStateError(
                f"Nie można odczytać stanu migracji: {exc}"
            ) from exc
        if state.zone.rstrip(".").casefold() != zone.rstrip(".").casefold():
            raise MigrationStateError("Manifest należy do innej strefy")
        return state

    @staticmethod
    def _decode(payload: object, *, expected_zone: str) -> DnssecPolicyMigrationState:
        if not isinstance(payload, dict) or set(payload) != _TOP_LEVEL_FIELDS:
            raise MigrationStateError("Niepoprawny zestaw pól manifestu")
        if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
            raise MigrationStateError("Nieobsługiwana lub uszkodzona wersja manifestu")
        transaction_id = _text(payload["transaction_id"], "transaction_id")
        zone = _text(payload["zone"], "zone")
        source_policy = _text(payload["source_policy"], "source_policy")
        target_policy = _text(payload["target_policy"], "target_policy")
        assert transaction_id and zone and source_policy and target_policy
        if not _TXID.fullmatch(transaction_id):
            raise MigrationStateError("Niepoprawny identyfikator transakcji")
        if (
            not _ZONE.fullmatch(zone)
            or zone.rstrip(".").casefold() != expected_zone.rstrip(".").casefold()
        ):
            raise MigrationStateError("Niepoprawna lub obca strefa manifestu")
        if not _POLICY.fullmatch(source_policy) or not _POLICY.fullmatch(target_policy):
            raise MigrationStateError("Niepoprawna nazwa polityki")
        if payload["ds_impact"] not in _DS_IMPACTS:
            raise MigrationStateError("Niepoprawny wpływ DS")
        raw_ids = payload["source_key_ids"]
        if not isinstance(raw_ids, (list, tuple)) or not raw_ids:
            raise MigrationStateError("Brak zaufanych identyfikatorów źródłowych KSK")
        source_key_ids = tuple(raw_ids)
        if len(source_key_ids) > 32 or len(set(source_key_ids)) != len(source_key_ids):
            raise MigrationStateError("Niepoprawne identyfikatory źródłowych KSK")
        for item in source_key_ids:
            if not isinstance(item, str) or not _KEY_ID.fullmatch(item):
                raise MigrationStateError("Niepoprawne identyfikatory źródłowych KSK")
            tag, algorithm = (int(part) for part in item.split(":"))
            if tag > 65535 or algorithm > 255:
                raise MigrationStateError("Niepoprawne identyfikatory źródłowych KSK")
        backup_file = payload["backup_file"]
        if backup_file is not None and backup_file != "bind-declaration.conf":
            raise MigrationStateError("Niepoprawna nazwa backupu")
        for field_name in ("rollback_allowed", "point_of_no_return"):
            if type(payload[field_name]) is not bool:
                raise MigrationStateError(f"Niepoprawne pole {field_name}")
        evidence_raw = payload["evidence"]
        if not isinstance(evidence_raw, dict) or set(evidence_raw) != _EVIDENCE_FIELDS:
            raise MigrationStateError("Niepoprawne pola evidence")
        for field_name in _EVIDENCE_FIELDS - {"resolver_count", "checked_at"}:
            if type(evidence_raw[field_name]) is not bool:
                raise MigrationStateError(f"Niepoprawne evidence.{field_name}")
        if (
            type(evidence_raw["resolver_count"]) is not int
            or not 0 <= evidence_raw["resolver_count"] <= 64
        ):
            raise MigrationStateError("Niepoprawne evidence.resolver_count")
        if evidence_raw["checked_at"] is not None:
            _timestamp(evidence_raw["checked_at"], "evidence.checked_at")
        history_raw = payload["history"]
        if not isinstance(history_raw, list) or not 1 <= len(history_raw) <= 128:
            raise MigrationStateError("Niepoprawna historia manifestu")
        history: list[dict[str, str]] = []
        for item in history_raw:
            if not isinstance(item, dict) or set(item) != _HISTORY_FIELDS:
                raise MigrationStateError("Niepoprawny wpis historii")
            phase = MigrationPhase(item["phase"])
            history.append(
                {"phase": phase.value, "at": _timestamp(item["at"], "history.at")}
            )
        return DnssecPolicyMigrationState(
            schema_version=1,
            transaction_id=transaction_id,
            zone=zone,
            source_policy=source_policy,
            target_policy=target_policy,
            ds_impact=str(payload["ds_impact"]),
            phase=MigrationPhase(payload["phase"]),
            next_action=_text(payload["next_action"], "next_action") or "",
            source_key_ids=source_key_ids,
            declaration_file=_relative_declaration(payload["declaration_file"]),
            backup_file=backup_file,
            rollback_allowed=payload["rollback_allowed"],
            point_of_no_return=payload["point_of_no_return"],
            failure=_text(payload["failure"], "failure", nullable=True),
            evidence=MigrationEvidence(**evidence_raw),
            updated_at=_timestamp(payload["updated_at"], "updated_at"),
            history=history,
        )
