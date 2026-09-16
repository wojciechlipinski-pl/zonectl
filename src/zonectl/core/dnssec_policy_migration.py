"""Transactional and resumable DNSSEC policy migration workflow."""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .dnssec_enable_transaction import DnssecEnableStep
from .audit_store import AuditStore, ResourceKind, Risk
from .family_audit_adapter import FamilyAuditAdapter
from .dnssec_policy_migration_plan import DnssecPolicyMigrationPlan
from .dnssec_policy_migration_state import (
    DnssecPolicyMigrationState,
    DnssecPolicyMigrationStore,
    MigrationEvidence,
    MigrationPhase,
)
from .edit_lock import ZoneEditLock
from .runner import run


MigrationAction = Callable[[str], DnssecEnableStep]
ConfigAction = Callable[[Path], DnssecEnableStep]
EvidenceCollector = Callable[[DnssecPolicyMigrationState], MigrationEvidence]
SourceDsCollector = Callable[[str], tuple[str, ...]]


def ds_key_identifiers(records: tuple[str, ...]) -> frozenset[str]:
    """Extract privacy-safe key-tag/algorithm identities from valid DS RDATA."""

    identifiers: set[str] = set()
    for record in records:
        fields = record.split()
        if len(fields) != 4 or not all(field.isdigit() for field in fields[:3]):
            continue
        key_tag, algorithm, digest_type = (int(field) for field in fields[:3])
        digest = fields[3]
        digest_lengths = {1: 40, 2: 64, 4: 96}
        if (
            key_tag > 65535
            or algorithm > 255
            or len(digest) != digest_lengths.get(digest_type)
            or any(character not in "0123456789abcdefABCDEF" for character in digest)
        ):
            continue
        identifiers.add(f"{key_tag}:{algorithm}")
    return frozenset(identifiers)


def migration_ds_identity_evidence(
    source_key_ids: tuple[str, ...],
    expected_ds: tuple[str, ...],
    resolver_observations: tuple[tuple[str, tuple[str, ...]], ...],
) -> tuple[bool, bool, bool]:
    """Classify source/target DS visibility without retaining DNS material."""

    source_ids = frozenset(source_key_ids)
    target_ids = ds_key_identifiers(expected_ds) - source_ids
    usable = bool(resolver_observations) and all(
        status not in {"MISSING", "ERROR"} for status, _ in resolver_observations
    )
    enough = len(resolver_observations) >= 2
    observed = tuple(
        ds_key_identifiers(records) for _, records in resolver_observations
    )
    target_observed = (
        bool(target_ids)
        and enough
        and usable
        and all(bool(records & target_ids) for records in observed)
    )
    source_observed = (
        bool(source_ids)
        and enough
        and usable
        and all(bool(records & source_ids) for records in observed)
    )
    return usable, target_observed, source_observed


@dataclass(slots=True)
class DnssecPolicyMigrationResult:
    """Stable result returned by start, check, advance, finalize, and rollback."""

    transaction_id: str
    zone: str
    operation: str
    status: str
    phase: str
    next_action: str
    committed: bool = False
    rolled_back: bool = False
    state_file: str | None = None
    steps: list[DnssecEnableStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe result."""

        return asdict(self)


class DnssecPolicyMigrationWorkflow:
    """Apply policy declarations and drive evidence-gated phase transitions."""

    def __init__(
        self,
        backup_root: Path,
        state_directory: Path,
        *,
        root_config: Path = Path("/etc/bind/named.conf"),
        lock_directory: Path | None = None,
        config_validator: ConfigAction | None = None,
        activator: MigrationAction | None = None,
        loaded_verifier: MigrationAction | None = None,
        kasp_verifier: MigrationAction | None = None,
        evidence_collector: EvidenceCollector | None = None,
        source_ds_collector: SourceDsCollector | None = None,
        audit_store: AuditStore | None = None,
    ) -> None:
        self.backup_root = backup_root
        self.store = DnssecPolicyMigrationStore(state_directory)
        self.root_config = root_config
        self.lock_directory = lock_directory or state_directory / "locks"
        self.config_validator = config_validator or self._validate_config
        self.activator = activator or self._activate
        self.loaded_verifier = loaded_verifier or self._loaded
        self.kasp_verifier = kasp_verifier or self._kasp
        self.evidence_collector = evidence_collector
        self.source_ds_collector = source_ds_collector
        self.audit_v1 = FamilyAuditAdapter(
            audit_store or FamilyAuditAdapter.default_store(state_directory),
            manifest_directory=state_directory,
            backup_root=backup_root,
        )

    def _audited(
        self, result: DnssecPolicyMigrationResult, *, risk: Risk
    ) -> DnssecPolicyMigrationResult:
        """Append privacy-safe START/RESULT records for one workflow action."""

        operation = f"dnssec.policy_migration_{result.operation}"
        self.audit_v1.start(
            result.transaction_id,
            operation,
            ResourceKind.ZONE,
            result.zone,
            risk=risk,
        )
        self.audit_v1.finish_result(result)
        return result

    def start(
        self,
        plan: DnssecPolicyMigrationPlan,
        *,
        commit: bool = False,
        activate: bool = False,
        confirmation: str | None = None,
    ) -> DnssecPolicyMigrationResult:
        """Dry-run by default; atomically apply after all three acknowledgements."""

        txid = (
            datetime.now().strftime("%Y%m%d-%H%M%S")
            + f"-policy-migration-{uuid.uuid4().hex[:8]}"
        )
        result = DnssecPolicyMigrationResult(
            txid,
            plan.zone,
            "start",
            "DRY-RUN",
            MigrationPhase.PLANNED.value,
            "Uruchom ponownie z commit, activate i pełną nazwą strefy.",
        )
        if not commit:
            result.steps.append(
                DnssecEnableStep(
                    "dry-run", True, "Nie zmieniono BIND ani stanu migracji"
                )
            )
            return self._audited(result, risk=Risk.LOW)
        if (
            not activate
            or (confirmation or "").rstrip(".").casefold()
            != plan.zone.rstrip(".").casefold()
        ):
            result.status = "REJECTED"
            result.steps.append(
                DnssecEnableStep(
                    "confirmation",
                    False,
                    "Wymagane commit, activate i pełna nazwa strefy",
                )
            )
            return self._audited(result, risk=Risk.CRITICAL)
        if plan.candidate_validation in {"BLOCKED", "NOT_RUN"}:
            result.status = "REJECTED"
            result.steps.append(
                DnssecEnableStep(
                    "candidate-validation",
                    False,
                    "Kandydat wymaga udanej walidacji named-checkconf",
                )
            )
            return self._audited(result, risk=Risk.CRITICAL)
        if self.source_ds_collector is None:
            result.status = "REJECTED"
            result.steps.append(
                DnssecEnableStep(
                    "source-key-identity",
                    False,
                    "Nie można wiarygodnie ustalić źródłowych identyfikatorów KSK",
                )
            )
            return self._audited(result, risk=Risk.CRITICAL)
        source_key_ids = tuple(
            sorted(ds_key_identifiers(self.source_ds_collector(plan.zone)))
        )
        if not source_key_ids:
            result.status = "REJECTED"
            result.steps.append(
                DnssecEnableStep(
                    "source-key-identity",
                    False,
                    "Nie można wiarygodnie ustalić źródłowych identyfikatorów KSK",
                )
            )
            return self._audited(result, risk=Risk.CRITICAL)
        with ZoneEditLock(self.lock_directory, plan.zone):
            existing = self.store.path_for(plan.zone)
            if existing.exists():
                try:
                    old = self.store.load(plan.zone)
                except ValueError as exc:
                    result.status = "REJECTED"
                    result.steps.append(DnssecEnableStep("state", False, str(exc)))
                    return self._audited(result, risk=Risk.CRITICAL)
                if old.phase not in {
                    MigrationPhase.COMPLETE,
                    MigrationPhase.ROLLED_BACK,
                    MigrationPhase.FAILED,
                }:
                    result.status = "CONFLICT"
                    result.steps.append(
                        DnssecEnableStep(
                            "state", False, "Migracja tej strefy jest już aktywna"
                        )
                    )
                    return self._audited(result, risk=Risk.CRITICAL)
            if plan.declaration_file.read_text(encoding="utf-8") != plan.original_text:
                result.status = "CONFLICT"
                result.steps.append(
                    DnssecEnableStep(
                        "preflight",
                        False,
                        "Deklaracja zmieniła się od utworzenia planu",
                    )
                )
                return self._audited(result, risk=Risk.CRITICAL)
            try:
                declaration_file = plan.declaration_file.resolve().relative_to(
                    self.root_config.parent.resolve()
                )
            except ValueError:
                result.status = "REJECTED"
                result.steps.append(
                    DnssecEnableStep(
                        "declaration",
                        False,
                        "Deklaracja jest poza katalogiem konfiguracji",
                    )
                )
                return self._audited(result, risk=Risk.CRITICAL)
            backup_dir = self.backup_root / txid
            backup = backup_dir / "bind-declaration.conf"
            stat = plan.declaration_file.stat()
            wrote = False
            state = DnssecPolicyMigrationState(
                schema_version=1,
                transaction_id=txid,
                zone=plan.zone,
                source_policy=plan.source.name,
                target_policy=plan.target.name,
                ds_impact=plan.ds_impact,
                phase=MigrationPhase.PLANNED,
                next_action="Zastosuj i zweryfikuj kandydacką konfigurację.",
                source_key_ids=source_key_ids,
                declaration_file=declaration_file.as_posix(),
                backup_file="bind-declaration.conf",
                history=[
                    {
                        "phase": MigrationPhase.PLANNED.value,
                        "at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    }
                ],
            )
            try:
                backup_dir.mkdir(parents=True, mode=0o750)
                shutil.copy2(plan.declaration_file, backup)
                os.chmod(backup, 0o640)
                result.steps.append(
                    DnssecEnableStep(
                        "backup", True, "Utworzono chroniony backup deklaracji"
                    )
                )
                self._atomic_write(
                    plan.declaration_file,
                    plan.candidate_text,
                    stat.st_mode & 0o777,
                    stat.st_uid,
                    stat.st_gid,
                )
                wrote = True
                result.steps.append(
                    DnssecEnableStep(
                        "policy",
                        True,
                        f"Zastosowano {plan.source.name} -> {plan.target.name}",
                    )
                )
                for action in (
                    lambda _zone: self.config_validator(self.root_config),
                    self.activator,
                    self.loaded_verifier,
                    self.kasp_verifier,
                ):
                    step = action(plan.zone)
                    result.steps.append(step)
                    if not step.ok:
                        raise RuntimeError(step.message)
                state.transition(
                    MigrationPhase.POLICY_APPLIED,
                    "Sprawdź DNSKEY, RRSIG i stan KASP; następnie użyj check/advance.",
                )
                path = self.store.save(state)
                result.status = "POLICY_APPLIED"
                result.phase = state.phase.value
                result.next_action = state.next_action
                result.committed = True
                result.state_file = str(path)
                return self._audited(result, risk=Risk.CRITICAL)
            except Exception as exc:
                result.steps.append(DnssecEnableStep("transaction", False, str(exc)))
                if wrote:
                    self._restore_start_failure(
                        state, result, plan.declaration_file, backup, stat
                    )
                else:
                    result.status = "FAILED"
                    result.phase = MigrationPhase.FAILED.value
                return self._audited(result, risk=Risk.CRITICAL)

    def check(self, zone: str) -> DnssecPolicyMigrationResult:
        """Collect read-only evidence and persist only its privacy-safe summary."""

        state = self.store.load(zone)
        result = self._result(state, "check", "OBSERVED")
        if self.evidence_collector is None:
            result.status = "NOT_CHECKED"
            result.next_action = (
                "Brak skonfigurowanego kolektora dowodów; stan nie został zmieniony."
            )
            return self._audited(result, risk=Risk.LOW)
        evidence = self._fresh_evidence(self.evidence_collector(state))
        state.evidence = evidence
        state.updated_at = datetime.now().astimezone().isoformat(timespec="seconds")
        self.store.save(state)
        result.next_action = self._next_action(state, evidence)
        result.steps.append(
            DnssecEnableStep(
                "evidence", True, "Zebrano zanonimizowane dowody DNSKEY/RRSIG/KASP/DS"
            )
        )
        return self._audited(result, risk=Risk.LOW)

    def status(self, zone: str) -> DnssecPolicyMigrationResult:
        """Return persisted state without DNS or BIND subprocesses."""

        return self._audited(
            self._result(self.store.load(zone), "status", "OK"), risk=Risk.LOW
        )

    def advance(self, zone: str) -> DnssecPolicyMigrationResult:
        """Advance one phase only when current observations satisfy its gate."""

        with ZoneEditLock(self.lock_directory, zone):
            state = self.store.load(zone)
            evidence = (
                self._fresh_evidence(self.evidence_collector(state))
                if self.evidence_collector
                else state.evidence
            )
            old_phase = state.phase
            if old_phase in {
                MigrationPhase.POLICY_APPLIED,
                MigrationPhase.WAITING_DNSKEY,
            }:
                if not (
                    evidence.loaded
                    and evidence.kasp_target_policy
                    and evidence.dnskey_present
                    and evidence.rrsig_present
                ):
                    state.transition(
                        MigrationPhase.WAITING_DNSKEY,
                        "Poczekaj na nowe DNSKEY, RRSIG i zgodny stan KASP.",
                        evidence,
                    )
                else:
                    state.transition(
                        MigrationPhase.WAITING_DS,
                        "Zmień DS ręcznie u rejestratora zgodnie z planem, potem sprawdź co najmniej dwa resolvery.",
                        evidence,
                    )
            elif old_phase == MigrationPhase.WAITING_DS:
                if evidence.resolver_count < 2:
                    state.next_action = "Wymagane są co najmniej dwa skonfigurowane publiczne resolvery."
                    state.evidence = evidence
                elif evidence.target_ds_observed and evidence.resolvers_consistent:
                    state.point_of_no_return = True
                    state.rollback_allowed = False
                    state.transition(
                        MigrationPhase.WAITING_PROPAGATION,
                        "Nie wolno już wykonywać rollbacku. Potwierdź pełną propagację i serwery autorytatywne.",
                        evidence,
                    )
                else:
                    state.next_action = "Nie zmieniaj KASP; poczekaj na zgodny docelowy DS na wszystkich resolverach."
                    state.evidence = evidence
            elif old_phase == MigrationPhase.WAITING_PROPAGATION:
                ds_ok = (
                    evidence.resolver_count >= 2
                    and evidence.resolvers_consistent
                    and evidence.target_ds_observed
                )
                if (
                    evidence.authoritative_consistent
                    and evidence.dnskey_present
                    and evidence.rrsig_present
                    and ds_ok
                ):
                    state.transition(
                        MigrationPhase.READY_TO_FINALIZE,
                        "Uruchom finalize z jawnym potwierdzeniem pełnej nazwy strefy.",
                        evidence,
                    )
                else:
                    state.next_action = "Powtórz kontrolę DNSKEY, RRSIG, KASP, autorytatywnych serwerów i DS."
                    state.evidence = evidence
            else:
                return self._audited(
                    self._result(state, "advance", "NO_CHANGE"), risk=Risk.HIGH
                )
            path = self.store.save(state)
            result = self._result(
                state, "advance", "ADVANCED" if state.phase != old_phase else "WAITING"
            )
            result.state_file = str(path)
            return self._audited(result, risk=Risk.HIGH)

    def finalize(
        self, zone: str, *, commit: bool = False, confirmation: str | None = None
    ) -> DnssecPolicyMigrationResult:
        """Mark an evidence-ready migration complete; this never changes registrar DS."""

        with ZoneEditLock(self.lock_directory, zone):
            state = self.store.load(zone)
            result = self._result(state, "finalize", "DRY-RUN")
            if not commit:
                return self._audited(result, risk=Risk.LOW)
            if (confirmation or "").rstrip(".").casefold() != state.zone.rstrip(
                "."
            ).casefold() or state.phase != MigrationPhase.READY_TO_FINALIZE:
                result.status = "REJECTED"
                result.steps.append(
                    DnssecEnableStep(
                        "gate",
                        False,
                        "Wymagana faza READY_TO_FINALIZE i pełna nazwa strefy",
                    )
                )
                return self._audited(result, risk=Risk.CRITICAL)
            state.rollback_allowed = False
            state.transition(
                MigrationPhase.COMPLETE,
                "Migracja zakończona; kontynuuj zwykły monitoring DNSSEC.",
            )
            result = self._result(state, "finalize", "COMPLETE")
            result.committed = True
            result.state_file = str(self.store.save(state))
            return self._audited(result, risk=Risk.CRITICAL)

    def rollback(self, zone: str, *, confirmation: str) -> DnssecPolicyMigrationResult:
        """Restore the declaration only before target DS creates a trust boundary."""

        with ZoneEditLock(self.lock_directory, zone):
            state = self.store.load(zone)
            result = self._result(state, "rollback", "REJECTED")
            if confirmation.rstrip(".").casefold() != state.zone.rstrip(".").casefold():
                result.steps.append(
                    DnssecEnableStep(
                        "confirmation", False, "Niepoprawna pełna nazwa strefy"
                    )
                )
                return self._audited(result, risk=Risk.CRITICAL)
            if (
                not state.rollback_allowed
                or state.point_of_no_return
                or state.evidence.target_ds_observed
            ):
                result.steps.append(
                    DnssecEnableStep(
                        "trust-boundary",
                        False,
                        "Rollback zablokowany po zaobserwowaniu docelowego DS",
                    )
                )
                return self._audited(result, risk=Risk.CRITICAL)
            if not state.backup_file:
                result.steps.append(
                    DnssecEnableStep("backup", False, "Manifest nie wskazuje backupu")
                )
                return self._audited(result, risk=Risk.CRITICAL)
            backup_directory = (self.backup_root / state.transaction_id).resolve()
            backup = backup_directory / state.backup_file
            try:
                backup_directory.relative_to(self.backup_root.resolve())
            except ValueError:
                result.steps.append(
                    DnssecEnableStep(
                        "backup", False, "Niebezpieczna referencja backupu"
                    )
                )
                return self._audited(result, risk=Risk.CRITICAL)
            if backup.is_symlink() or not backup.is_file():
                result.steps.append(
                    DnssecEnableStep("backup", False, "Brak chronionego backupu")
                )
                return self._audited(result, risk=Risk.CRITICAL)
            declaration = self._declaration_path(state)
            try:
                stat = declaration.stat()
                self._atomic_write(
                    declaration,
                    backup.read_text(encoding="utf-8"),
                    stat.st_mode & 0o777,
                    stat.st_uid,
                    stat.st_gid,
                )
                result.steps.append(
                    DnssecEnableStep(
                        "declaration-restore", True, "Przywrócono deklarację atomowo"
                    )
                )
            except (OSError, UnicodeError) as exc:
                return self._rollback_failed(state, result, "declaration-restore", exc)
            actions: tuple[Callable[[], DnssecEnableStep], ...] = (
                lambda: self.config_validator(self.root_config),
                lambda: self.activator(state.zone),
                lambda: self.loaded_verifier(state.zone),
                lambda: self.kasp_verifier(state.zone),
            )
            for action in actions:
                try:
                    step = action()
                except Exception as exc:
                    return self._rollback_failed(
                        state, result, "rollback-verification", exc
                    )
                result.steps.append(step)
                if not step.ok:
                    return self._rollback_failed(state, result, step.name)
            state.transition(
                MigrationPhase.ROLLED_BACK,
                "Przywrócono politykę źródłową; sprawdź DNSSEC.",
            )
            result = self._result(state, "rollback", "ROLLED_BACK")
            result.rolled_back = True
            result.state_file = str(self.store.save(state))
            return self._audited(result, risk=Risk.CRITICAL)

    def _declaration_path(self, state: DnssecPolicyMigrationState) -> Path:
        declaration = (self.root_config.parent / state.declaration_file).resolve()
        try:
            declaration.relative_to(self.root_config.parent.resolve())
        except ValueError as exc:
            raise ValueError("Niebezpieczna referencja deklaracji") from exc
        return declaration

    def _restore_start_failure(
        self,
        state: DnssecPolicyMigrationState,
        result: DnssecPolicyMigrationResult,
        declaration: Path,
        backup: Path,
        stat: os.stat_result,
    ) -> None:
        """Restore and fully verify a candidate write before reporting rollback."""

        failed_step: str | None = None
        try:
            self._atomic_write(
                declaration,
                backup.read_text(encoding="utf-8"),
                stat.st_mode & 0o777,
                stat.st_uid,
                stat.st_gid,
            )
            result.steps.append(
                DnssecEnableStep(
                    "declaration-restore", True, "Przywrócono deklarację atomowo"
                )
            )
        except Exception:
            failed_step = "declaration-restore"

        actions: tuple[Callable[[], DnssecEnableStep], ...] = (
            lambda: self.config_validator(self.root_config),
            lambda: self.activator(state.zone),
            lambda: self.loaded_verifier(state.zone),
            lambda: self.kasp_verifier(state.zone),
        )
        if failed_step is None:
            for action in actions:
                try:
                    step = action()
                    result.steps.append(step)
                    if not step.ok:
                        failed_step = step.name
                        break
                except Exception:
                    failed_step = "rollback-verification"
                    break

        if failed_step is None:
            state.failure = None
            state.transition(
                MigrationPhase.ROLLED_BACK,
                "Przywrócono politykę źródłową; sprawdź DNSSEC.",
            )
            result.status = MigrationPhase.ROLLED_BACK.value
            result.phase = state.phase.value
            result.next_action = state.next_action
            result.rolled_back = True
        else:
            safe_step = (
                failed_step
                if all(
                    character.isalnum() or character in "._-"
                    for character in failed_step
                )
                else "rollback"
            )
            state.failure = f"Rollback failed at {safe_step}"
            state.transition(
                MigrationPhase.FAILED,
                "Napraw źródłową konfigurację i zweryfikuj BIND ręcznie.",
            )
            result.steps.append(DnssecEnableStep(safe_step, False, state.failure))
            result.status = MigrationPhase.FAILED.value
            result.phase = state.phase.value
            result.next_action = state.next_action
            result.rolled_back = False
        result.state_file = str(self.store.save(state))

    @staticmethod
    def _fresh_evidence(evidence: MigrationEvidence) -> MigrationEvidence:
        if evidence.checked_at is not None:
            return evidence
        return replace(
            evidence,
            checked_at=datetime.now(timezone.utc)
            .astimezone()
            .isoformat(timespec="seconds"),
        )

    def _rollback_failed(
        self,
        state: DnssecPolicyMigrationState,
        result: DnssecPolicyMigrationResult,
        step_name: str,
        _error: Exception | None = None,
    ) -> DnssecPolicyMigrationResult:
        safe_step = (
            step_name
            if all(c.isalnum() or c in "._-" for c in step_name)
            else "rollback"
        )
        state.failure = f"Rollback failed at {safe_step}"
        state.transition(
            MigrationPhase.FAILED,
            "Napraw źródłową konfigurację i zweryfikuj BIND ręcznie.",
        )
        result = self._result(state, "rollback", "FAILED")
        result.state_file = str(self.store.save(state))
        result.steps.append(DnssecEnableStep(safe_step, False, state.failure))
        return self._audited(result, risk=Risk.CRITICAL)

    @staticmethod
    def _next_action(
        state: DnssecPolicyMigrationState, evidence: MigrationEvidence
    ) -> str:
        if state.phase == MigrationPhase.WAITING_DS and evidence.resolver_count < 2:
            return (
                "Skonfiguruj co najmniej dwa publiczne resolvery; nie przechodź dalej."
            )
        return state.next_action

    @staticmethod
    def _result(
        state: DnssecPolicyMigrationState, operation: str, status: str
    ) -> DnssecPolicyMigrationResult:
        return DnssecPolicyMigrationResult(
            state.transaction_id,
            state.zone,
            operation,
            status,
            state.phase.value,
            state.next_action,
        )

    @staticmethod
    def _atomic_write(path: Path, content: str, mode: int, uid: int, gid: int) -> None:
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, mode)
            if hasattr(os, "chown"):
                os.chown(temporary, uid, gid)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _validate_config(root: Path) -> DnssecEnableStep:
        outcome = run(["named-checkconf", str(root)], 30)
        return DnssecEnableStep(
            "named-checkconf",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}",
        )

    @staticmethod
    def _activate(zone: str) -> DnssecEnableStep:
        outcome = run(["rndc", "reconfig"], 30)
        return DnssecEnableStep(
            "rndc-reconfig",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}",
        )

    @staticmethod
    def _loaded(zone: str) -> DnssecEnableStep:
        outcome = run(["rndc", "zonestatus", zone], 15)
        return DnssecEnableStep(
            "loaded-zone",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}",
        )

    @staticmethod
    def _kasp(zone: str) -> DnssecEnableStep:
        outcome = run(["rndc", "dnssec", "-status", zone], 15)
        return DnssecEnableStep(
            "kasp",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}",
        )
