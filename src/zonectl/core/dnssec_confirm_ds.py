"""Controlled acknowledgement of a published DS record in BIND KASP."""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .dnssec_ds_check import DnssecDsCheck
from .runner import CommandResult, run


@dataclass(slots=True)
class DnssecConfirmStep:
    name: str
    ok: bool
    message: str


@dataclass(slots=True)
class DnssecConfirmResult:
    transaction_id: str
    zone: str
    status: str
    committed: bool = False
    manifest: str | None = None
    steps: list[DnssecConfirmStep] = field(default_factory=list)


DsChecker = Callable[[str, tuple[str, ...]], DnssecDsCheck]
ZoneAction = Callable[[str], DnssecConfirmStep]


class DnssecConfirmDsTransaction:
    """Acknowledge DS only after an independent check returned PASS."""

    def __init__(
        self,
        manifest_directory: Path,
        *,
        checker: DsChecker,
        confirmer: ZoneAction | None = None,
        verifier: ZoneAction | None = None,
    ) -> None:
        self.manifest_directory = manifest_directory
        self.checker = checker
        self.confirmer = confirmer or self._confirm
        self.verifier = verifier or self._verify

    def apply(
        self,
        zone: str,
        resolvers: tuple[str, ...],
        *,
        commit: bool = False,
        acknowledge_published: bool = False,
    ) -> DnssecConfirmResult:
        txid = (
            datetime.now().strftime("%Y%m%d-%H%M%S")
            + f"-dnssec-confirm-ds-{zone}-{uuid.uuid4().hex[:8]}"
        )
        result = DnssecConfirmResult(txid, zone, "PLAN")

        check = self.checker(zone, resolvers)
        check_ok = check.status == "PASS"
        result.steps.append(
            DnssecConfirmStep(
                "check-ds",
                check_ok,
                f"Status kontroli DS: {check.status}",
            )
        )
        if not check_ok:
            return self._finish(result, "BLOCKED", write_manifest=False)

        if commit != acknowledge_published:
            result.steps.append(
                DnssecConfirmStep(
                    "confirmation",
                    False,
                    "Wymagane są jednocześnie commit i potwierdzenie publikacji DS",
                )
            )
            return self._finish(result, "CONFIRMATION-REQUIRED", write_manifest=False)

        if not commit:
            result.steps.append(
                DnssecConfirmStep(
                    "dry-run",
                    True,
                    "DS jest zweryfikowany; nie zmieniono stanu KASP",
                )
            )
            return self._finish(result, "DRY-RUN", write_manifest=False)

        confirm = self.confirmer(zone)
        result.steps.append(confirm)
        if not confirm.ok:
            return self._finish(result, "FAILED")

        result.committed = True
        verify = self.verifier(zone)
        result.steps.append(verify)
        if not verify.ok:
            result.steps.append(
                DnssecConfirmStep(
                    "operator-action",
                    False,
                    "Nie wycofuj DS automatycznie; sprawdź stan KASP i delegację.",
                )
            )
            return self._finish(result, "VERIFY-FAILED")
        return self._finish(result, "CONFIRMED")

    def _finish(
        self,
        result: DnssecConfirmResult,
        status: str,
        *,
        write_manifest: bool = True,
    ) -> DnssecConfirmResult:
        result.status = status
        if write_manifest:
            self.manifest_directory.mkdir(parents=True, exist_ok=True, mode=0o750)
            path = self.manifest_directory / f"{result.transaction_id}.json"
            result.manifest = str(path)
            payload = asdict(result)
            payload["saved_at"] = datetime.now(timezone.utc).astimezone().isoformat(
                timespec="seconds"
            )
            self._atomic_json(path, payload)
        return result

    @staticmethod
    def _atomic_json(path: Path, payload: dict[str, object]) -> None:
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o640)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _confirm(zone: str) -> DnssecConfirmStep:
        outcome = run(["rndc", "dnssec", "-checkds", "published", zone], timeout=15)
        message = (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}"
        return DnssecConfirmStep("rndc-checkds-published", outcome.returncode == 0, message)

    @staticmethod
    def _verify(zone: str) -> DnssecConfirmStep:
        outcome: CommandResult = run(["rndc", "dnssec", "-status", zone], timeout=15)
        text = (outcome.stdout + outcome.stderr).strip()
        state = re.search(r"^\s*-\s*ds:\s*([a-z-]+)\s*$", text, re.MULTILINE | re.IGNORECASE)
        ok = outcome.returncode == 0 and state is not None and state.group(1).casefold() != "hidden"
        return DnssecConfirmStep("kasp-ds-state", ok, text or f"kod {outcome.returncode}")
