"""Transactional application of a validated BIND secondary-group plan."""

from __future__ import annotations

import json
import getpass
import hashlib
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .bind_access_inventory import BindAccessInventoryReader
from .bind_audit_manifest import safe_manifest_payload
from .bind_secondary_health import BindSecondaryHealthGate
from .bind_secondary_plan import BindSecondaryPlan
from .audit_store import AuditStore, ResourceKind
from .family_audit_adapter import FamilyAuditAdapter, FamilyAuditContext, risk_from_text
from .runner import run


@dataclass(slots=True)
class BindSecondaryStep:
    name: str
    ok: bool
    message: str


@dataclass(slots=True)
class BindSecondaryResult:
    transaction_id: str
    group: str
    status: str
    roles: tuple[str, ...] = ()
    old_addresses: tuple[str, ...] = ()
    new_addresses: tuple[str, ...] = ()
    zones: tuple[str, ...] = ()
    committed: bool = False
    rolled_back: bool = False
    backup: str | None = None
    manifest: str | None = None
    operator: str = ""
    reason: str = ""
    risk: str = "NONE"
    state_before: dict[str, object] = field(default_factory=dict)
    state_after: dict[str, object] = field(default_factory=dict)
    steps: list[BindSecondaryStep] = field(default_factory=list)


ConfigValidator = Callable[[Path], BindSecondaryStep]
Activator = Callable[[], BindSecondaryStep]
PostValidator = Callable[[BindSecondaryPlan], BindSecondaryStep]
OperationalValidator = Callable[[BindSecondaryPlan], BindSecondaryStep]


class BindSecondaryTransaction:
    def __init__(
        self,
        backup_root: Path,
        manifest_directory: Path,
        *,
        root_config: Path = Path("/etc/bind/named.conf"),
        config_validator: ConfigValidator | None = None,
        activator: Activator | None = None,
        post_validator: PostValidator | None = None,
        operational_validator: OperationalValidator | None = None,
        audit_store: AuditStore | None = None,
    ) -> None:
        self.backup_root = backup_root
        self.manifest_directory = manifest_directory
        self.root_config = root_config
        self.config_validator = config_validator or self._validate_config
        self.activator = activator or self._activate
        self.post_validator = post_validator or self._validate_applied_state
        self.operational_validator = (
            operational_validator or self._validate_operational_state
        )
        self.audit_v1 = FamilyAuditAdapter(
            audit_store
            or FamilyAuditAdapter.default_store(
                manifest_directory, system_anchor=root_config
            ),
            manifest_directory=manifest_directory,
            backup_root=backup_root,
        )

    def apply(
        self,
        plan: BindSecondaryPlan,
        *,
        commit: bool = False,
        activate: bool = False,
        reason: str | None = None,
    ) -> BindSecondaryResult:
        txid = (
            datetime.now().strftime("%Y%m%d-%H%M%S")
            + f"-secondary-{plan.name}-{uuid.uuid4().hex[:8]}"
        )
        result = BindSecondaryResult(
            txid,
            plan.name,
            "PLAN",
            roles=plan.roles,
            old_addresses=plan.old_addresses,
            new_addresses=plan.new_addresses,
            zones=plan.zones,
            operator=getpass.getuser(),
            reason=(reason or "nie podano").strip() or "nie podano",
            risk=plan.impact.risk if plan.impact is not None else "INDETERMINATE",
            state_before=self._audit_state(
                plan.original_text, plan.old_addresses, plan.source
            ),
        )
        audit_context = self.audit_v1.start(
            txid,
            "bind.secondary.apply",
            ResourceKind.SECONDARY_GROUP,
            plan.name,
            risk=risk_from_text(result.risk),
            reason=result.reason,
        )
        current = plan.source.read_text(encoding="utf-8", errors="replace")
        if current != plan.original_text:
            result.status = "CONFLICT"
            result.steps.append(
                BindSecondaryStep(
                    "preflight", False, f"Plik zmienił się: {plan.source}"
                )
            )
            return self._finish_audit(audit_context, result)
        if not plan.validation_ok:
            result.status = "BLOCKED"
            result.steps.append(
                BindSecondaryStep(
                    "candidate-validation", False, plan.validation_message
                )
            )
            return self._finish_audit(audit_context, result)
        if not commit:
            result.status = "DRY-RUN"
            result.steps.append(
                BindSecondaryStep(
                    "dry-run", True, "Nie zmieniono konfiguracji ani BIND"
                )
            )
            return self._finish_audit(audit_context, result)
        if plan.impact is not None and plan.impact.risk == "HIGH":
            result.status = "BLOCKED"
            result.steps.append(
                BindSecondaryStep(
                    "impact-gate",
                    False,
                    "Zmiana HIGH jest zablokowana przed backupem: role "
                    f"{', '.join(plan.impact.roles) or '-'}; usuwane wpisy: "
                    f"{', '.join(plan.impact.removed_entries) or '-'}. "
                    "Nie można odłączyć ostatniego aktywnego secondary.",
                )
            )
            return self._finish_audit(audit_context, result)

        self.backup_root.mkdir(parents=True, exist_ok=True, mode=0o750)
        backup = self.backup_root / f"{txid}-{plan.source.name}"
        result.backup = str(backup)
        metadata = plan.source.stat()
        activation_attempted = False
        try:
            shutil.copy2(plan.source, backup)
            result.steps.append(BindSecondaryStep("backup", True, f"Backup: {backup}"))
            self._atomic_write(
                plan.source,
                plan.candidate_text.encode("utf-8"),
                metadata.st_mode & 0o777,
                metadata.st_uid,
                metadata.st_gid,
            )
            result.steps.append(
                BindSecondaryStep(
                    "configuration", True, f"Zaktualizowano {plan.source}"
                )
            )
            check = self.config_validator(self.root_config)
            result.steps.append(check)
            if not check.ok:
                raise RuntimeError(check.message)
            if activate:
                activation_attempted = True
                reload_step = self.activator()
                result.steps.append(reload_step)
                if not reload_step.ok:
                    raise RuntimeError(reload_step.message)
                post_gate = self.post_validator(plan)
                result.steps.append(post_gate)
                if not post_gate.ok:
                    raise RuntimeError(post_gate.message)
                operational_gate = self.operational_validator(plan)
                result.steps.append(operational_gate)
                if not operational_gate.ok:
                    raise RuntimeError(operational_gate.message)
            result.committed = True
            result.status = "COMMIT"
        except Exception as exc:
            result.steps.append(BindSecondaryStep("transaction", False, str(exc)))
            rollback_ok = True
            try:
                self._atomic_write(
                    plan.source,
                    plan.original_text.encode("utf-8"),
                    metadata.st_mode & 0o777,
                    metadata.st_uid,
                    metadata.st_gid,
                )
                if activation_attempted:
                    rollback_reload = self.activator()
                    result.steps.append(
                        BindSecondaryStep(
                            "rndc-reconfig-rollback",
                            rollback_reload.ok,
                            rollback_reload.message,
                        )
                    )
                    rollback_ok = rollback_reload.ok
                rollback_state = BindSecondaryStep(
                    "post-rollback-state",
                    plan.source.read_text(encoding="utf-8", errors="replace")
                    == plan.original_text,
                    "Przywrócono stan konfiguracji sprzed transakcji",
                )
                result.steps.append(rollback_state)
                rollback_ok = rollback_ok and rollback_state.ok
            except OSError as rollback_error:
                rollback_ok = False
                result.steps.append(
                    BindSecondaryStep("rollback", False, str(rollback_error))
                )
            if rollback_ok:
                result.steps.append(
                    BindSecondaryStep(
                        "rollback", True, "Przywrócono konfigurację sprzed transakcji"
                    )
                )
            result.rolled_back = rollback_ok
            result.status = "ROLLED-BACK" if rollback_ok else "ROLLBACK-FAILED"
        after_entries = (
            plan.new_addresses if result.status == "COMMIT" else plan.old_addresses
        )
        result.state_after = self._audit_state(
            plan.source.read_text(encoding="utf-8", errors="replace"),
            after_entries,
            plan.source,
        )
        self._write_manifest(result)
        return self._finish_audit(audit_context, result)

    def _finish_audit(
        self, context: FamilyAuditContext, result: BindSecondaryResult
    ) -> BindSecondaryResult:
        self.audit_v1.finish(context, result)
        return result

    @staticmethod
    def _audit_state(
        text: str, entries: tuple[str, ...], path: Path
    ) -> dict[str, object]:
        metadata = path.stat()
        return {
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "entries": list(entries),
            "uid": metadata.st_uid,
            "gid": metadata.st_gid,
            "mode": f"{metadata.st_mode & 0o777:04o}",
        }

    def _validate_applied_state(self, plan: BindSecondaryPlan) -> BindSecondaryStep:
        if plan.kind == "zone-assignment":
            ok = (
                plan.source.read_text(encoding="utf-8", errors="replace")
                == plan.candidate_text
            )
        else:
            inventory = BindAccessInventoryReader(self.root_config).collect()
            matches = [
                item
                for item in inventory.definitions
                if item.kind == plan.kind
                and item.name.casefold() == plan.name.casefold()
            ]
            ok = len(matches) == 1 and matches[0].entries == plan.new_addresses
        detail = (
            "Aktywna konfiguracja secondary odpowiada zatwierdzonemu planowi"
            if ok
            else "Aktywna konfiguracja secondary nie odpowiada zatwierdzonemu planowi"
        )
        return BindSecondaryStep("post-config-state", ok, detail)

    @staticmethod
    def _validate_operational_state(plan: BindSecondaryPlan) -> BindSecondaryStep:
        zones = tuple(zone for zone in plan.zones if "rpz" not in zone.casefold())
        if not zones or not plan.operational_addresses:
            return BindSecondaryStep(
                "secondary-operational",
                True,
                "Brak stref lub adresów wymagających kontroli SOA",
            )
        reports = BindSecondaryHealthGate().check(zones, plan.operational_addresses)
        failed = tuple(report for report in reports if report.status == "FAIL")
        pending = tuple(report for report in reports if report.status == "PENDING")
        if failed:
            return BindSecondaryStep(
                "secondary-operational",
                False,
                "Błąd autorytatywności/SOA: "
                + ", ".join(report.zone for report in failed),
            )
        if pending:
            return BindSecondaryStep(
                "secondary-operational",
                True,
                "PENDING — transfer SOA trwa dla: "
                + ", ".join(report.zone for report in pending),
            )
        return BindSecondaryStep(
            "secondary-operational",
            True,
            "PASS — secondary zwracają autorytatywne SOA zgodne z primary",
        )

    def _write_manifest(self, result: BindSecondaryResult) -> None:
        self.manifest_directory.mkdir(parents=True, exist_ok=True, mode=0o750)
        path = self.manifest_directory / f"{result.transaction_id}.json"
        result.manifest = str(path)
        payload = safe_manifest_payload(
            result,
            (
                "transaction_id",
                "group",
                "status",
                "roles",
                "old_addresses",
                "new_addresses",
                "zones",
                "committed",
                "rolled_back",
                "backup",
                "manifest",
                "operator",
                "reason",
                "risk",
                "state_before",
                "state_after",
                "steps",
            ),
        )
        payload["saved_at"] = (
            datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        )
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _atomic_write(
        path: Path, content: bytes, mode: int, uid: int, gid: int
    ) -> None:
        fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, mode)
            chown = getattr(os, "chown", None)
            if chown is not None:
                chown(temporary, uid, gid)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _validate_config(root: Path) -> BindSecondaryStep:
        outcome = run(["named-checkconf", str(root)], 30)
        detail = (
            outcome.stdout or outcome.stderr
        ).strip() or f"kod {outcome.returncode}"
        return BindSecondaryStep("named-checkconf", outcome.returncode == 0, detail)

    @staticmethod
    def _activate() -> BindSecondaryStep:
        outcome = run(["rndc", "reconfig"], 30)
        detail = (
            outcome.stdout or outcome.stderr
        ).strip() or f"kod {outcome.returncode}"
        return BindSecondaryStep("rndc-reconfig", outcome.returncode == 0, detail)
