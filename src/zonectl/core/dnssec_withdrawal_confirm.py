"""Guarded confirmation of DNSSEC withdrawal.

This is the write-side counterpart to :mod:`dnssec_withdrawal_check`. It is
the only place in ZoneCTL allowed to run ``rndc dnssec -checkds withdrawn``,
and it refuses to do so unless:

1. the caller passed ``--commit`` (otherwise it is a pure dry-run), and
2. the caller passed the explicit ``--acknowledge-withdrawn`` flag, and
3. a *freshly run* :class:`DnssecWithdrawalChecker` reports
   ``READY_FOR_WITHDRAWN`` at the moment of the call.

Any of those failing leaves BIND, KASP, and the zone completely untouched
and returns ``BLOCKED`` with the reason. A successful run writes a manifest
recording the DS check that authorized it, so the decision is auditable
after the fact.
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from .dnssec_withdrawal_check import DnssecWithdrawalCheckResult

Checker = Callable[[str, Sequence[str]], DnssecWithdrawalCheckResult]
RndcRunner = Callable[[str], "subprocess.CompletedProcess[str]"]


@dataclass(slots=True)
class DnssecWithdrawalConfirmStep:
    name: str
    ok: bool
    message: str


@dataclass(slots=True)
class DnssecWithdrawalConfirmResult:
    transaction_id: str
    zone: str
    status: str  # "DRY-RUN" | "BLOCKED" | "WITHDRAWN" | "FAILED"
    committed: bool = False
    manifest: str | None = None
    steps: list[DnssecWithdrawalConfirmStep] = field(default_factory=list)


class DnssecWithdrawalConfirmTransaction:
    """Executes the withdrawn step only behind a freshly verified gate."""

    def __init__(
        self,
        manifest_directory: Path,
        *,
        checker: Checker,
        rndc_runner: RndcRunner | None = None,
        timeout: int = 10,
    ) -> None:
        self.manifest_directory = manifest_directory
        self._checker = checker
        self.timeout = timeout
        self._rndc_runner = rndc_runner or self._default_rndc_runner

    def _default_rndc_runner(self, zone: str) -> "subprocess.CompletedProcess[str]":
        query = zone if zone.endswith(".") else f"{zone}."
        return subprocess.run(
            ["rndc", "dnssec", "-checkds", "withdrawn", query],
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )

    @staticmethod
    def _step(name: str, ok: bool, message: str) -> DnssecWithdrawalConfirmStep:
        return DnssecWithdrawalConfirmStep(name, ok, message)

    def apply(
        self,
        zone: str,
        resolvers: Sequence[str],
        *,
        commit: bool = False,
        acknowledge_withdrawn: bool = False,
    ) -> DnssecWithdrawalConfirmResult:
        txid = (
            datetime.now().strftime("%Y%m%d-%H%M%S")
            + f"-dnssec-withdrawal-confirm-{zone}-{uuid.uuid4().hex[:8]}"
        )
        result = DnssecWithdrawalConfirmResult(txid, zone, "DRY-RUN")

        check = self._checker(zone, resolvers)
        result.steps.append(
            self._step(
                "check",
                check.status == "READY_FOR_WITHDRAWN",
                f"Kontrola DS: {check.status} — {check.next_action}",
            )
        )

        if not commit:
            result.status = "DRY-RUN"
            return result

        if not acknowledge_withdrawn:
            result.status = "BLOCKED"
            result.steps.append(
                self._step(
                    "acknowledge",
                    False,
                    "Wymagana jawna flaga --acknowledge-withdrawn",
                )
            )
            return result

        if check.status != "READY_FOR_WITHDRAWN":
            result.status = "BLOCKED"
            result.steps.append(
                self._step(
                    "gate",
                    False,
                    "Blokada: świeża kontrola DS zwróciła "
                    f"{check.status}, nie READY_FOR_WITHDRAWN",
                )
            )
            return result

        try:
            completed = self._rndc_runner(zone)
        except (OSError, subprocess.TimeoutExpired) as exc:
            result.status = "FAILED"
            result.steps.append(
                self._step("rndc", False, f"rndc nie powiodło się: {exc}")
            )
            return result

        if completed.returncode != 0:
            result.status = "FAILED"
            stderr = (completed.stderr or "").strip()
            result.steps.append(
                self._step(
                    "rndc",
                    False,
                    f"rndc zwrócił kod {completed.returncode}: {stderr}",
                )
            )
            return result

        result.steps.append(
            self._step("rndc", True, "Wykonano rndc dnssec -checkds withdrawn")
        )

        try:
            zone_root = self.manifest_directory / zone.rstrip(".")
            zone_root.mkdir(parents=True, exist_ok=True, mode=0o750)
            manifest_path = zone_root / f"{txid}.json"
            payload = {
                "transaction_id": txid,
                "zone": zone,
                "status": "WITHDRAWN",
                "created_at": datetime.now(timezone.utc)
                .astimezone()
                .isoformat(timespec="seconds"),
                "ds_check": asdict(check),
                "rndc_stdout": completed.stdout,
            }
            manifest_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.chmod(manifest_path, 0o640)
        except OSError as exc:
            # rndc already ran successfully; the withdrawal itself is not
            # rolled back, since KASP state cannot be safely un-confirmed
            # from here. The operator must record the outcome manually.
            result.status = "FAILED"
            result.steps.append(
                self._step(
                    "manifest",
                    False,
                    "rndc wykonano, ale zapis manifestu nie powiódł się: "
                    f"{exc}. Sprawdź stan KASP ręcznie.",
                )
            )
            return result

        result.status = "WITHDRAWN"
        result.committed = True
        result.manifest = str(manifest_path)
        result.steps.append(
            self._step("manifest", True, f"Zapisano manifest: {manifest_path}")
        )
        return result
