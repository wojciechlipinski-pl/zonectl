"""Privacy-safe storage primitives for the ZoneCTL audit v1 registry."""

from __future__ import annotations

import fcntl
import json
import os
import re
import stat
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from uuid import UUID


AUDIT_SCHEMA = "zonectl.audit/v1"
MAX_RECORD_BYTES = 64 * 1024
MAX_AUDIT_BYTES = 64 * 1024 * 1024
MAX_RESULTS = 10_000
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")
_OPERATION = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SENSITIVE = re.compile(
    r"(?:private[-_ ]?key|begin [^-]*private key|password|passphrase|"
    r"token|secret\s+[\"'])",
    re.IGNORECASE,
)


class AuditValidationError(ValueError):
    """Raised when a record does not satisfy the audit v1 contract."""


class AuditStorageError(RuntimeError):
    """Raised when the registry cannot be accessed without weakening safety."""


class RecordKind(StrEnum):
    """Kinds of records stored in the audit registry."""

    START = "START"
    RESULT = "RESULT"


class Outcome(StrEnum):
    """Canonical outcomes accepted by the audit v1 contract."""

    STARTED = "STARTED"
    PASS = "PASS"
    NO_CHANGE = "NO_CHANGE"
    DRY_RUN = "DRY_RUN"
    COMMITTED = "COMMITTED"
    ROLLED_BACK = "ROLLED_BACK"
    ROLLBACK_FAILED = "ROLLBACK_FAILED"
    BLOCKED = "BLOCKED"
    READ_ONLY = "READ_ONLY"
    FAILED = "FAILED"


class Risk(StrEnum):
    """Risk labels available to operation adapters."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ResourceKind(StrEnum):
    """Logical resource types supported by the v1 registry."""

    ZONE = "zone"
    ACL = "acl"
    SECONDARY_GROUP = "secondary_group"
    RPZ = "rpz"
    BIND_ENVIRONMENT = "bind_environment"


@dataclass(frozen=True, slots=True)
class AuditResource:
    """Logical resource affected by an audited operation."""

    kind: ResourceKind
    name: str


@dataclass(frozen=True, slots=True)
class AuditRollback:
    """Rollback attempt and its canonical result."""

    attempted: bool = False
    outcome: Outcome | None = None


@dataclass(frozen=True, slots=True)
class AuditActor:
    """Minimal operator identity deliberately excluding host information."""

    uid: int
    label: str | None = None


@dataclass(frozen=True, slots=True)
class AuditSummary:
    """Allowlisted aggregate information about an operation."""

    changed_file_count: int | None = None
    changed_record_count: int | None = None
    resource_count: int | None = None
    validation_gates: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AuditRecord:
    """Validated representation of one ``zonectl.audit/v1`` JSONL record."""

    record_id: str
    transaction_id: str
    recorded_at: str
    record_kind: RecordKind
    operation: str
    resource: AuditResource
    outcome: Outcome
    committed: bool
    rollback: AuditRollback
    started_at: str | None = None
    duration_ms: int | None = None
    actor: AuditActor | None = None
    risk: Risk | None = None
    reason: str | None = None
    summary: AuditSummary | None = None
    manifest_ref: str | None = None
    backup_ref: str | None = None

    def __post_init__(self) -> None:
        """Validate values before the record can reach serialization."""
        _validate_uuid(self.record_id)
        _validate_id("transaction_id", self.transaction_id)
        _validate_timestamp("recorded_at", self.recorded_at)
        if not _OPERATION.fullmatch(self.operation):
            raise AuditValidationError("operation has an invalid format")
        _validate_text("resource.name", self.resource.name, 253)
        if self.record_kind is RecordKind.START and self.outcome is not Outcome.STARTED:
            raise AuditValidationError("START records require STARTED outcome")
        if self.record_kind is RecordKind.RESULT and self.outcome is Outcome.STARTED:
            raise AuditValidationError("RESULT records cannot use STARTED outcome")
        if self.rollback.attempted != (self.rollback.outcome is not None):
            raise AuditValidationError("rollback outcome must match attempted state")
        if self.started_at is not None:
            _validate_timestamp("started_at", self.started_at)
        if self.duration_ms is not None and self.duration_ms < 0:
            raise AuditValidationError("duration_ms cannot be negative")
        if self.actor is not None:
            if self.actor.uid < 0:
                raise AuditValidationError("actor.uid cannot be negative")
            if self.actor.label is not None:
                _validate_text("actor.label", self.actor.label, 80)
        if self.reason is not None:
            _validate_text("reason", self.reason, 500)
        if self.summary is not None:
            _validate_summary(self.summary)
        for field_name, reference in (
            ("manifest_ref", self.manifest_ref),
            ("backup_ref", self.backup_ref),
        ):
            if reference is not None:
                _validate_reference(field_name, reference)

    def to_dict(self) -> dict[str, Any]:
        """Return the stable, allowlisted JSON representation of the record."""
        payload = asdict(self)
        payload["schema"] = AUDIT_SCHEMA
        payload["record_kind"] = self.record_kind.value
        payload["outcome"] = self.outcome.value
        payload["resource"]["kind"] = self.resource.kind.value
        if self.rollback.outcome is not None:
            payload["rollback"]["outcome"] = self.rollback.outcome.value
        if self.risk is not None:
            payload["risk"] = self.risk.value
        return {key: value for key, value in payload.items() if value is not None}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> AuditRecord:
        """Parse and validate an untrusted JSON mapping."""
        if payload.get("schema") != AUDIT_SCHEMA:
            raise AuditValidationError("unsupported schema")
        required = {
            "record_id",
            "transaction_id",
            "recorded_at",
            "record_kind",
            "operation",
            "resource",
            "outcome",
            "committed",
            "rollback",
        }
        missing = sorted(required.difference(payload))
        if missing:
            raise AuditValidationError(f"missing required fields: {', '.join(missing)}")
        resource = _mapping(payload["resource"], "resource")
        rollback = _mapping(payload["rollback"], "rollback")
        actor_data = payload.get("actor")
        summary_data = payload.get("summary")
        return cls(
            record_id=_string(payload["record_id"], "record_id"),
            transaction_id=_string(payload["transaction_id"], "transaction_id"),
            recorded_at=_string(payload["recorded_at"], "recorded_at"),
            record_kind=RecordKind(payload["record_kind"]),
            operation=_string(payload["operation"], "operation"),
            resource=AuditResource(
                ResourceKind(_string(resource.get("kind"), "resource.kind")),
                _string(resource.get("name"), "resource.name"),
            ),
            outcome=Outcome(payload["outcome"]),
            committed=_boolean(payload["committed"], "committed"),
            rollback=AuditRollback(
                _boolean(rollback.get("attempted"), "rollback.attempted"),
                Outcome(rollback["outcome"])
                if rollback.get("outcome") is not None
                else None,
            ),
            started_at=_optional_string(payload.get("started_at"), "started_at"),
            duration_ms=_optional_int(payload.get("duration_ms"), "duration_ms"),
            actor=_parse_actor(actor_data),
            risk=Risk(payload["risk"]) if payload.get("risk") is not None else None,
            reason=_optional_string(payload.get("reason"), "reason"),
            summary=_parse_summary(summary_data),
            manifest_ref=_optional_string(payload.get("manifest_ref"), "manifest_ref"),
            backup_ref=_optional_string(payload.get("backup_ref"), "backup_ref"),
        )


@dataclass(frozen=True, slots=True)
class AuditIssue:
    """Safe diagnostic for one rejected line."""

    line_number: int
    reason: str


@dataclass(frozen=True, slots=True)
class AuditReadResult:
    """Healthy records and bounded diagnostics returned by a read."""

    records: tuple[AuditRecord, ...]
    issues: tuple[AuditIssue, ...]


@dataclass(frozen=True, slots=True)
class RetentionPlan:
    """Explicit dry-run result for audit record retention."""

    keep_record_ids: tuple[str, ...]
    remove_record_ids: tuple[str, ...]
    source_size: int


class AuditStore:
    """Append, read and explicitly compact a protected audit JSONL file."""

    def __init__(self, path: Path):
        self.path = path
        self.lock_path = path.with_name(f".{path.name}.lock")

    def append(self, record: AuditRecord) -> None:
        """Append one fully validated record under an inter-process lock."""
        encoded = _encode(record)
        self._prepare_parent()
        with self._locked():
            self._reject_unsafe_target()
            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
            flags |= getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(self.path, flags, 0o640)
            try:
                mode = stat.S_IMODE(os.fstat(fd).st_mode)
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise AuditStorageError("audit target is not a regular file")
                if mode != 0o640:
                    os.fchmod(fd, 0o640)
                _write_all(fd, encoded)
                os.fsync(fd)
            finally:
                os.close(fd)

    def read(self, *, limit: int = MAX_RESULTS) -> AuditReadResult:
        """Read valid records while reporting bounded, non-sensitive issues."""
        if limit < 1 or limit > MAX_RESULTS:
            raise ValueError(f"limit must be between 1 and {MAX_RESULTS}")
        if not self.path.exists():
            return AuditReadResult((), ())
        self._reject_unsafe_target()
        if self.path.stat().st_size > MAX_AUDIT_BYTES:
            raise AuditStorageError("audit registry exceeds the safe read limit")
        records: list[AuditRecord] = []
        issues: list[AuditIssue] = []
        with self.path.open("rb") as handle:
            for line_number, line in enumerate(handle, 1):
                if len(line) > MAX_RECORD_BYTES:
                    issues.append(AuditIssue(line_number, "record exceeds size limit"))
                    continue
                try:
                    decoded = json.loads(line.decode("utf-8"))
                    if not isinstance(decoded, dict):
                        raise AuditValidationError("record is not an object")
                    records.append(AuditRecord.from_dict(decoded))
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                    issues.append(AuditIssue(line_number, _safe_reason(exc)))
        records.sort(key=lambda item: (item.recorded_at, item.record_id), reverse=True)
        if len(records) > limit:
            issues.append(AuditIssue(0, "result limit exceeded"))
        return AuditReadResult(tuple(records[:limit]), tuple(issues))

    def plan_retention(self, *, max_records: int) -> RetentionPlan:
        """Create a dry-run plan while protecting each resource's newest result."""
        if max_records < 1:
            raise ValueError("max_records must be positive")
        result = self.read()
        if result.issues:
            raise AuditStorageError("retention blocked by invalid audit records")
        protected: set[str] = set()
        seen_resources: set[tuple[ResourceKind, str]] = set()
        for record in result.records:
            key = (record.resource.kind, record.resource.name)
            if record.record_kind is RecordKind.RESULT and key not in seen_resources:
                protected.add(record.record_id)
                seen_resources.add(key)
        keep = list(result.records[:max_records])
        keep_ids = {record.record_id for record in keep}
        keep.extend(
            record
            for record in result.records
            if record.record_id in protected and record.record_id not in keep_ids
        )
        final_keep = {record.record_id for record in keep}
        remove = tuple(
            record.record_id
            for record in result.records
            if record.record_id not in final_keep
        )
        return RetentionPlan(
            tuple(record.record_id for record in keep), remove, len(result.records)
        )

    def apply_retention(self, plan: RetentionPlan, *, confirm: bool = False) -> int:
        """Atomically apply an unchanged plan only after explicit confirmation."""
        if not confirm:
            raise AuditStorageError("retention requires explicit confirmation")
        self._prepare_parent()
        with self._locked():
            current = self.read()
            if current.issues:
                raise AuditStorageError("retention blocked by invalid audit records")
            if len(current.records) != plan.source_size:
                raise AuditStorageError(
                    "audit registry changed after retention planning"
                )
            current_ids = {record.record_id for record in current.records}
            if current_ids != set(plan.keep_record_ids) | set(plan.remove_record_ids):
                raise AuditStorageError("retention plan no longer matches the registry")
            keep_ids = set(plan.keep_record_ids)
            ordered = [
                record
                for record in reversed(current.records)
                if record.record_id in keep_ids
            ]
            fd, temp_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.", dir=self.path.parent
            )
            temp_path = Path(temp_name)
            try:
                os.fchmod(fd, 0o640)
                for record in ordered:
                    _write_all(fd, _encode(record))
                os.fsync(fd)
                os.close(fd)
                fd = -1
                os.replace(temp_path, self.path)
                directory_fd = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                if fd >= 0:
                    os.close(fd)
                temp_path.unlink(missing_ok=True)
        return len(plan.remove_record_ids)

    def _prepare_parent(self) -> None:
        self.path.parent.mkdir(parents=True, mode=0o750, exist_ok=True)
        if self.path.parent.is_symlink() or not self.path.parent.is_dir():
            raise AuditStorageError("audit directory is unsafe")
        os.chmod(self.path.parent, 0o750)

    def _reject_unsafe_target(self) -> None:
        try:
            target = self.path.lstat()
        except FileNotFoundError:
            return
        if stat.S_ISLNK(target.st_mode) or not stat.S_ISREG(target.st_mode):
            raise AuditStorageError("audit target must be a regular non-symlink file")

    def _locked(self) -> Any:
        flags = os.O_RDWR | os.O_CREAT
        flags |= getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(self.lock_path, flags, 0o640)
        os.fchmod(fd, 0o640)
        return _FileLock(fd)


class _FileLock:
    def __init__(self, fd: int):
        self.fd = fd

    def __enter__(self) -> _FileLock:
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *_args: object) -> None:
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        os.close(self.fd)


def _encode(record: AuditRecord) -> bytes:
    encoded = (
        json.dumps(
            record.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        + "\n"
    ).encode("utf-8")
    if len(encoded) > MAX_RECORD_BYTES:
        raise AuditValidationError("record exceeds size limit")
    return encoded


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise AuditStorageError("audit write made no progress")
        view = view[written:]


def _validate_uuid(value: str) -> None:
    try:
        if str(UUID(value)) != value.lower():
            raise ValueError
    except (ValueError, AttributeError) as exc:
        raise AuditValidationError("record_id must be a canonical UUID") from exc


def _validate_id(name: str, value: str) -> None:
    if not _SAFE_ID.fullmatch(value):
        raise AuditValidationError(f"{name} has an invalid format")


def _validate_timestamp(name: str, value: str) -> None:
    if not value.endswith("Z"):
        raise AuditValidationError(f"{name} must be UTC with Z suffix")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise AuditValidationError(f"{name} is not RFC 3339") from exc
    if parsed.tzinfo != timezone.utc:
        raise AuditValidationError(f"{name} must use UTC")


def _validate_text(name: str, value: str, max_length: int) -> None:
    if not value or len(value) > max_length or _CONTROL.search(value):
        raise AuditValidationError(f"{name} contains invalid text")
    if _SENSITIVE.search(value):
        raise AuditValidationError(f"{name} contains sensitive material")


def _validate_reference(name: str, value: str) -> None:
    _validate_text(name, value, 500)
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value.startswith("~"):
        raise AuditValidationError(f"{name} must be a safe relative path")


def _validate_summary(summary: AuditSummary) -> None:
    for name in ("changed_file_count", "changed_record_count", "resource_count"):
        value = getattr(summary, name)
        if value is not None and value < 0:
            raise AuditValidationError(f"summary.{name} cannot be negative")
    if len(summary.validation_gates) > 32:
        raise AuditValidationError("too many validation gates")
    for gate in summary.validation_gates:
        _validate_id("validation gate", gate)


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise AuditValidationError(f"{name} must be an object")
    return value


def _string(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise AuditValidationError(f"{name} must be a string")
    return value


def _optional_string(value: Any, name: str) -> str | None:
    return None if value is None else _string(value, name)


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise AuditValidationError(f"{name} must be a boolean")
    return value


def _optional_int(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise AuditValidationError(f"{name} must be an integer")
    return value


def _parse_actor(value: Any) -> AuditActor | None:
    if value is None:
        return None
    actor = _mapping(value, "actor")
    uid = _optional_int(actor.get("uid"), "actor.uid")
    if uid is None:
        raise AuditValidationError("actor.uid is required")
    return AuditActor(uid, _optional_string(actor.get("label"), "actor.label"))


def _parse_summary(value: Any) -> AuditSummary | None:
    if value is None:
        return None
    summary = _mapping(value, "summary")
    gates = summary.get("validation_gates", ())
    if not isinstance(gates, (list, tuple)) or not all(
        isinstance(item, str) for item in gates
    ):
        raise AuditValidationError("summary.validation_gates must be a string list")
    return AuditSummary(
        _optional_int(summary.get("changed_file_count"), "summary.changed_file_count"),
        _optional_int(
            summary.get("changed_record_count"), "summary.changed_record_count"
        ),
        _optional_int(summary.get("resource_count"), "summary.resource_count"),
        tuple(gates),
    )


def _safe_reason(error: Exception) -> str:
    if isinstance(error, AuditValidationError):
        return str(error)[:160]
    if isinstance(error, UnicodeDecodeError):
        return "record is not valid UTF-8"
    return "record is not valid JSON"
