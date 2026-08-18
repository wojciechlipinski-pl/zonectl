"""Isolated dry-run for migration of an EXTERNAL RPZ integration."""

from __future__ import annotations

import hashlib
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from .rpz_external_migration_plan import RpzExternalMigrationPlan
from .runner import CommandResult, run


@dataclass(frozen=True, slots=True)
class RpzMigrationDryRunStep:
    name: str
    ok: bool
    message: str


@dataclass(slots=True)
class RpzMigrationDryRunResult:
    zone: str
    status: str
    committed: bool = False
    timer_switched: bool = False
    candidate_hashes: dict[str, str] = field(default_factory=dict)
    steps: list[RpzMigrationDryRunStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class RpzExternalMigrationDryRun:
    """Build and validate candidates only inside a temporary directory."""

    def __init__(
        self,
        *,
        root_config: Path = Path("/etc/bind/named.conf"),
        command_runner: Callable[[list[str], int], CommandResult] = run,
    ) -> None:
        self.root_config = root_config
        self.command_runner = command_runner

    def execute(self, plan: RpzExternalMigrationPlan) -> RpzMigrationDryRunResult:
        result = RpzMigrationDryRunResult(plan.zone, "PLAN")
        if plan.status != "READY":
            result.status = "BLOCKED"
            result.steps.append(
                RpzMigrationDryRunStep(
                    "preflight", False, "; ".join(plan.blockers) or plan.status
                )
            )
            return result

        paths = {item.role: item.path for item in plan.artifacts}
        required = ("zone-file", "updater", "service-unit", "timer-unit")
        missing = [role for role in required if paths.get(role) is None]
        if missing:
            result.status = "BLOCKED"
            result.steps.append(
                RpzMigrationDryRunStep(
                    "preflight", False, "Brak artefaktów: " + ", ".join(missing)
                )
            )
            return result

        before = {
            role: self._digest(paths[role])  # type: ignore[arg-type]
            for role in required
        }
        try:
            with tempfile.TemporaryDirectory(prefix="zonectl-rpz-dry-run-") as raw:
                workspace = Path(raw)
                updater = workspace / plan.managed_updater.name
                service = workspace / plan.managed_service.name
                timer = workspace / plan.managed_timer.name

                updater.write_bytes(paths["updater"].read_bytes())  # type: ignore[union-attr]
                service_text = paths["service-unit"].read_text(  # type: ignore[union-attr]
                    encoding="utf-8", errors="replace"
                )
                old_updater = str(paths["updater"])
                service.write_text(
                    service_text.replace(old_updater, str(plan.managed_updater)),
                    encoding="utf-8",
                )
                timer.write_text(
                    paths["timer-unit"].read_text(  # type: ignore[union-attr]
                        encoding="utf-8", errors="replace"
                    ),
                    encoding="utf-8",
                )
                result.steps.append(
                    RpzMigrationDryRunStep(
                        "candidates", True,
                        f"Kandydaci utworzeni wyłącznie w {workspace}",
                    )
                )

                result.candidate_hashes = {
                    "updater": self._digest(updater),
                    "service-unit": self._digest(service),
                    "timer-unit": self._digest(timer),
                }
                self._command_step(result, "updater-syntax", ["bash", "-n", str(updater)])
                self._unit_step(result, service, timer, plan.managed_updater)
                self._command_step(
                    result, "named-checkzone",
                    ["named-checkzone", plan.zone, str(paths["zone-file"])],
                )
                self._command_step(
                    result, "named-checkconf", ["named-checkconf", str(self.root_config)]
                )
        except OSError as exc:
            result.steps.append(RpzMigrationDryRunStep("workspace", False, str(exc)))

        after = {
            role: self._digest(paths[role])  # type: ignore[arg-type]
            for role in required
        }
        unchanged = before == after
        result.steps.append(
            RpzMigrationDryRunStep(
                "source-integrity", unchanged,
                "Artefakty EXTERNAL pozostały bez zmian"
                if unchanged else "Wykryto zmianę artefaktów EXTERNAL",
            )
        )
        ok = all(step.ok for step in result.steps)
        result.status = "DRY-RUN" if ok else "FAILED"
        result.steps.append(
            RpzMigrationDryRunStep(
                "no-activation", True,
                "Nie zapisano plików systemowych, nie zatrzymano timera i nie przeładowano BIND",
            )
        )
        return result

    def _command_step(
        self, result: RpzMigrationDryRunResult, name: str, command: list[str]
    ) -> None:
        outcome = self.command_runner(command, 30)
        message = (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}"
        result.steps.append(RpzMigrationDryRunStep(name, outcome.returncode == 0, message))

    @staticmethod
    def _unit_step(
        result: RpzMigrationDryRunResult,
        service: Path,
        timer: Path,
        managed_updater: Path,
    ) -> None:
        service_text = service.read_text(encoding="utf-8", errors="replace")
        timer_text = timer.read_text(encoding="utf-8", errors="replace")
        valid = (
            "[Service]" in service_text
            and f"ExecStart={managed_updater}" in service_text
            and "[Timer]" in timer_text
            and ("OnCalendar=" in timer_text or "OnUnitActiveSec=" in timer_text)
        )
        result.steps.append(
            RpzMigrationDryRunStep(
                "unit-candidates", valid,
                "Sekcje Service/Timer i docelowy ExecStart są poprawne"
                if valid else "Kandydaci unitów nie zawierają wymaganych dyrektyw",
            )
        )

    @staticmethod
    def _digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
