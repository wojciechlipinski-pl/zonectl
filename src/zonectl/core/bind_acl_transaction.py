"""Transactional application of a validated BIND ACL plan."""

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
from .bind_acl_plan import BindAclPlan
from .runner import run


@dataclass(slots=True)
class BindAclStep:
    name: str
    ok: bool
    message: str


@dataclass(slots=True)
class BindAclResult:
    transaction_id: str
    acl: str
    status: str
    committed: bool = False
    rolled_back: bool = False
    backup: str | None = None
    manifest: str | None = None
    operator: str = ""
    reason: str = ""
    risk: str = "NONE"
    roles: tuple[str, ...] = ()
    zones: tuple[str, ...] = ()
    state_before: dict[str, object] = field(default_factory=dict)
    state_after: dict[str, object] = field(default_factory=dict)
    steps: list[BindAclStep] = field(default_factory=list)


ConfigValidator = Callable[[Path], BindAclStep]
Activator = Callable[[], BindAclStep]
PostValidator = Callable[[BindAclPlan], BindAclStep]


class BindAclTransaction:
    def __init__(
        self,
        backup_root: Path,
        manifest_directory: Path,
        *,
        root_config: Path = Path("/etc/bind/named.conf"),
        config_validator: ConfigValidator | None = None,
        activator: Activator | None = None,
        post_validator: PostValidator | None = None,
    ) -> None:
        self.backup_root = backup_root
        self.manifest_directory = manifest_directory
        self.root_config = root_config
        self.config_validator = config_validator or self._validate_config
        self.activator = activator or self._activate
        self.post_validator = post_validator or self._validate_applied_state

    def apply(
        self, plan: BindAclPlan, *, commit: bool = False, activate: bool = False,
        reason: str | None = None,
    ) -> BindAclResult:
        txid = (
            datetime.now().strftime("%Y%m%d-%H%M%S")
            + f"-acl-{plan.name}-{uuid.uuid4().hex[:8]}"
        )
        risk = plan.impact.risk if plan.impact is not None else "INDETERMINATE"
        before_entries = plan.impact.current_entries if plan.impact else ()
        result = BindAclResult(
            txid, plan.name, "PLAN", operator=getpass.getuser(),
            reason=(reason or "nie podano").strip() or "nie podano",
            risk=risk,
            roles=plan.impact.roles if plan.impact else (),
            zones=plan.impact.zones if plan.impact else (),
            state_before=self._audit_state(plan.original_text, before_entries),
        )
        if plan.source.read_text(encoding="utf-8", errors="replace") != plan.original_text:
            result.status = "CONFLICT"
            result.steps.append(BindAclStep(
                "preflight", False, f"Plik zmienił się od utworzenia planu: {plan.source}"
            ))
            return result
        if not plan.validation_ok:
            result.status = "BLOCKED"
            result.steps.append(BindAclStep(
                "candidate-validation", False, plan.validation_message
            ))
            return result
        if not commit:
            result.status = "DRY-RUN"
            result.steps.append(BindAclStep(
                "dry-run", True, "Nie zmieniono konfiguracji ani BIND"
            ))
            return result
        if plan.impact is not None and plan.impact.risk == "HIGH":
            result.status = "BLOCKED"
            result.steps.append(BindAclStep(
                "impact-gate",
                False,
                "Zmiana HIGH jest zablokowana przed backupem: role "
                f"{', '.join(plan.impact.roles) or '-'}; usuwane wpisy: "
                f"{', '.join(plan.impact.removed_entries) or '-'}. "
                "Nie można usunąć ostatniego dostępu administracyjnego, "
                "transferowego ani notify.",
            ))
            return result

        self.backup_root.mkdir(parents=True, exist_ok=True, mode=0o750)
        backup = self.backup_root / f"{txid}-{plan.source.name}"
        result.backup = str(backup)
        metadata = plan.source.stat()
        activation_attempted = False
        try:
            shutil.copy2(plan.source, backup)
            result.steps.append(BindAclStep("backup", True, f"Backup: {backup}"))
            self._atomic_write(
                plan.source,
                plan.candidate_text.encode("utf-8"),
                metadata.st_mode & 0o777,
                metadata.st_uid,
                metadata.st_gid,
            )
            result.steps.append(BindAclStep(
                "configuration", True, f"Zaktualizowano {plan.source}"
            ))
            check = self.config_validator(self.root_config)
            result.steps.append(check)
            if not check.ok:
                raise RuntimeError(check.message)
            if activate:
                activation_attempted = True
                activation = self.activator()
                result.steps.append(activation)
                if not activation.ok:
                    raise RuntimeError(activation.message)
                post_gate = self.post_validator(plan)
                result.steps.append(post_gate)
                if not post_gate.ok:
                    raise RuntimeError(post_gate.message)
            result.status = "COMMIT"
            result.committed = True
        except Exception as exc:
            result.steps.append(BindAclStep("transaction", False, str(exc)))
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
                    reload_step = self.activator()
                    result.steps.append(BindAclStep(
                        "rndc-reconfig-rollback", reload_step.ok, reload_step.message
                    ))
                    rollback_ok = reload_step.ok
                rollback_state = BindAclStep(
                    "post-rollback-state",
                    plan.source.read_text(encoding="utf-8", errors="replace")
                    == plan.original_text,
                    "Przywrócono stan konfiguracji sprzed transakcji",
                )
                result.steps.append(rollback_state)
                rollback_ok = rollback_ok and rollback_state.ok
            except OSError as rollback_error:
                rollback_ok = False
                result.steps.append(BindAclStep("rollback", False, str(rollback_error)))
            if rollback_ok:
                result.steps.append(BindAclStep(
                    "rollback", True, "Przywrócono konfigurację sprzed transakcji"
                ))
            result.rolled_back = rollback_ok
            result.status = "ROLLED-BACK" if rollback_ok else "ROLLBACK-FAILED"
        after_entries = (
            plan.impact.candidate_entries
            if result.status == "COMMIT" and plan.impact is not None
            else before_entries
        )
        result.state_after = self._audit_state(
            plan.source.read_text(encoding="utf-8", errors="replace"),
            after_entries,
        )
        self._write_manifest(result)
        return result

    @staticmethod
    def _audit_state(text: str, entries: tuple[str, ...]) -> dict[str, object]:
        return {
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "entries": list(entries),
        }

    def _validate_applied_state(self, plan: BindAclPlan) -> BindAclStep:
        inventory = BindAccessInventoryReader(self.root_config).collect()
        matches = [
            item for item in inventory.definitions
            if item.kind == "acl" and item.name.casefold() == plan.name.casefold()
        ]
        expected = plan.impact.candidate_entries if plan.impact else ()
        ok = len(matches) == 1 and matches[0].entries == expected
        detail = (
            "Aktywna konfiguracja ACL odpowiada zatwierdzonemu planowi"
            if ok else
            "Aktywna konfiguracja ACL nie odpowiada zatwierdzonemu planowi"
        )
        return BindAclStep("post-config-state", ok, detail)

    def _write_manifest(self, result: BindAclResult) -> None:
        self.manifest_directory.mkdir(parents=True, exist_ok=True, mode=0o750)
        path = self.manifest_directory / f"{result.transaction_id}.json"
        result.manifest = str(path)
        payload = safe_manifest_payload(result, (
            "transaction_id", "acl", "status", "committed", "rolled_back",
            "backup", "manifest", "operator", "reason", "risk", "roles",
            "zones", "state_before", "state_after", "steps",
        ))
        payload["saved_at"] = datetime.now(timezone.utc).astimezone().isoformat(
            timespec="seconds"
        )
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _atomic_write(path: Path, content: bytes, mode: int, uid: int, gid: int) -> None:
        fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, mode)
            os.chown(temporary, uid, gid)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _validate_config(root: Path) -> BindAclStep:
        outcome = run(["named-checkconf", str(root)], 30)
        detail = (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}"
        return BindAclStep("named-checkconf", outcome.returncode == 0, detail)

    @staticmethod
    def _activate() -> BindAclStep:
        outcome = run(["rndc", "reconfig"], 30)
        detail = (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}"
        return BindAclStep("rndc-reconfig", outcome.returncode == 0, detail)
