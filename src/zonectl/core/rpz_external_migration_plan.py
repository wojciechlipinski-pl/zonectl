"""Read-only migration plan from an external RPZ updater to ZoneCTL MANAGED."""

from __future__ import annotations

import hashlib
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .bind_environment_report import BindEnvironmentReporter, RpzEnvironment
from .runner import CommandResult, run


def _exists_or_inaccessible(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return True


@dataclass(frozen=True, slots=True)
class RpzMigrationArtifact:
    role: str
    path: Path | None
    exists: bool
    owner: int | None
    group: int | None
    mode: str | None
    sha256: str | None

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["path"] = str(self.path) if self.path else None
        return data


@dataclass(frozen=True, slots=True)
class RpzExternalMigrationPlan:
    status: str
    zone: str
    current_timer: str | None
    current_service: str | None
    current_enabled: bool
    current_active: bool
    artifacts: tuple[RpzMigrationArtifact, ...]
    managed_updater: Path
    managed_service: Path
    managed_timer: Path
    backup_root: Path
    blockers: tuple[str, ...]
    steps: tuple[str, ...]
    next_action: str

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "zone": self.zone,
            "current_timer": self.current_timer,
            "current_service": self.current_service,
            "current_enabled": self.current_enabled,
            "current_active": self.current_active,
            "artifacts": [item.to_dict() for item in self.artifacts],
            "managed_updater": str(self.managed_updater),
            "managed_service": str(self.managed_service),
            "managed_timer": str(self.managed_timer),
            "backup_root": str(self.backup_root),
            "blockers": list(self.blockers),
            "steps": list(self.steps),
            "next_action": self.next_action,
        }


class RpzExternalMigrationPlanner:
    """Inventory an existing EXTERNAL integration without exposing its content."""

    def __init__(
        self,
        root_config: Path = Path("/etc/bind/named.conf"),
        *,
        command_runner: Callable[[list[str], int], CommandResult] = run,
        managed_updater: Path = Path("/usr/lib/zonectl/update-cert-rpz"),
        managed_service: Path = Path("/etc/systemd/system/zonectl-cert-rpz.service"),
        managed_timer: Path = Path("/etc/systemd/system/zonectl-cert-rpz.timer"),
        backup_root: Path = Path("/var/backups/zonectl-rpz/migrations"),
    ) -> None:
        self.root_config = root_config
        self.command_runner = command_runner
        self.managed_updater = managed_updater
        self.managed_service = managed_service
        self.managed_timer = managed_timer
        self.backup_root = backup_root

    def plan(self) -> RpzExternalMigrationPlan:
        report = BindEnvironmentReporter(
            self.root_config, command_runner=self.command_runner
        ).collect()
        external = tuple(item for item in report.rpz if item.mode == "EXTERNAL")
        blockers: list[str] = []
        integration: RpzEnvironment | None = None
        if not external:
            blockers.append("Nie wykryto integracji RPZ w trybie EXTERNAL")
        elif len(external) > 1:
            blockers.append(
                f"Wykryto {len(external)} integracje EXTERNAL; wymagano dokładnie jednej"
            )
        else:
            integration = external[0]

        service_path = self._fragment_path(
            integration.service_unit if integration else None
        )
        timer_path = self._fragment_path(
            integration.timer_unit if integration else None
        )
        artifacts = (
            self._artifact(
                "zone-file",
                Path(integration.source_file)
                if integration and integration.source_file
                else None,
            ),
            self._artifact(
                "updater",
                Path(integration.updater_path)
                if integration and integration.updater_path
                else None,
            ),
            self._artifact("service-unit", service_path),
            self._artifact("timer-unit", timer_path),
        )
        if integration:
            for artifact in artifacts:
                if artifact.path is None:
                    blockers.append(f"Nie ustalono ścieżki: {artifact.role}")
                elif not artifact.exists:
                    blockers.append(f"Brak wymaganego pliku: {artifact.path}")
        for target in (self.managed_updater, self.managed_service, self.managed_timer):
            if _exists_or_inaccessible(target):
                blockers.append(f"Istnieje docelowy plik MANAGED: {target}")

        status = "READY" if integration and not blockers else "BLOCKED"
        return RpzExternalMigrationPlan(
            status=status,
            zone=integration.zone if integration else "-",
            current_timer=integration.timer_unit if integration else None,
            current_service=integration.service_unit if integration else None,
            current_enabled=integration.timer_enabled if integration else False,
            current_active=integration.timer_active if integration else False,
            artifacts=artifacts,
            managed_updater=self.managed_updater,
            managed_service=self.managed_service,
            managed_timer=self.managed_timer,
            backup_root=self.backup_root,
            blockers=tuple(blockers),
            steps=(
                "zapisz manifest SHA-256, właścicieli, tryby i stan unitów EXTERNAL",
                "utwórz kompletny backup skryptu, unitów i konfiguracji RPZ",
                "zbuduj równoległe artefakty MANAGED bez ich aktywowania",
                "zweryfikuj pobrany plik przez named-checkzone i konfigurację przez named-checkconf",
                "wykonaj dry-run bez zatrzymywania istniejącego timera EXTERNAL",
                "w punkcie przełączenia zatrzymaj timer EXTERNAL i uruchom MANAGED",
                "potwierdź serial, świeżość, rndc zonestatus i wynik usługi MANAGED",
                "przy błędzie wyłącz MANAGED, odtwórz pliki i stan timera EXTERNAL",
            ),
            next_action=(
                "Można przygotować transakcyjny dry-run migracji bez przełączenia timerów."
                if status == "READY"
                else "Usuń zgłoszone blokady; niczego nie przełączaj."
            ),
        )

    def _fragment_path(self, unit: str | None) -> Path | None:
        if not unit:
            return None
        result = self.command_runner(
            ["systemctl", "show", unit, "--property=FragmentPath", "--value"], 10
        )
        value = result.stdout.strip()
        return Path(value) if result.returncode == 0 and value else None

    @staticmethod
    def _artifact(role: str, path: Path | None) -> RpzMigrationArtifact:
        if path is None or not path.is_file():
            return RpzMigrationArtifact(role, path, False, None, None, None, None)
        metadata = path.stat()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return RpzMigrationArtifact(
            role=role,
            path=path,
            exists=True,
            owner=metadata.st_uid,
            group=metadata.st_gid,
            mode=stat.filemode(metadata.st_mode),
            sha256=digest,
        )
