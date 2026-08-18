"""Read-only plan for an optional ZoneCTL-managed CERT Polska RPZ."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re

from .bind_environment_report import BindEnvironmentReporter


def _exists_or_inaccessible(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return True


CERT_POLSKA_RPZ_URL = "https://hole.cert.pl/domains/v2/domains_rpz.db"


@dataclass(frozen=True, slots=True)
class RpzManagedPlan:
    """A proposed installation; creating it never writes to the system."""

    status: str
    zone: str
    source_url: str
    root_config: Path
    zone_file: Path
    declaration_file: Path
    updater_file: Path
    service_file: Path
    timer_file: Path
    backup_root: Path
    conflicts: tuple[str, ...]
    steps: tuple[str, ...]
    next_action: str
    options_file: Path | None = None

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        for key in (
            "root_config",
            "zone_file",
            "declaration_file",
            "updater_file",
            "service_file",
            "timer_file",
            "backup_root",
            "options_file",
        ):
            data[key] = str(data[key]) if data[key] is not None else None
        data["conflicts"] = list(self.conflicts)
        data["steps"] = list(self.steps)
        return data


class RpzManagedPlanner:
    """Detect conflicts and describe a future guarded MANAGED transaction."""

    def __init__(
        self,
        root_config: Path = Path("/etc/bind/named.conf"),
        *,
        zone: str = "cert-rpz.local",
        source_url: str = CERT_POLSKA_RPZ_URL,
        zone_file: Path = Path("/var/lib/zonectl/rpz/domains_rpz.db"),
        declaration_file: Path = Path("/etc/bind/zonectl-rpz.conf"),
        updater_file: Path = Path("/usr/lib/zonectl/update-cert-rpz"),
        service_file: Path = Path("/etc/systemd/system/zonectl-cert-rpz.service"),
        timer_file: Path = Path("/etc/systemd/system/zonectl-cert-rpz.timer"),
        backup_root: Path = Path("/var/backups/zonectl-rpz"),
    ) -> None:
        self.root_config = root_config
        self.zone = zone.rstrip(".")
        self.source_url = source_url
        self.zone_file = zone_file
        self.declaration_file = declaration_file
        self.updater_file = updater_file
        self.service_file = service_file
        self.timer_file = timer_file
        self.backup_root = backup_root

    def plan(self) -> RpzManagedPlan:
        report = BindEnvironmentReporter(self.root_config).collect()
        conflicts: list[str] = []
        options_file = self._options_file(report.config_files)
        for integration in report.rpz:
            if integration.mode == "EXTERNAL":
                conflicts.append(
                    f"EXTERNAL: {integration.zone} korzysta z "
                    f"{integration.updater_path or integration.timer_unit}"
                )
            elif integration.mode != "OFF":
                conflicts.append(
                    f"{integration.mode}: istnieje integracja {integration.zone}"
                )

        for target in (
            self.zone_file,
            self.declaration_file,
            self.updater_file,
            self.service_file,
            self.timer_file,
        ):
            if _exists_or_inaccessible(target):
                conflicts.append(f"Istnieje plik docelowy: {target}")

        if report.config_files and options_file is None:
            conflicts.append(
                "Nie można jednoznacznie wskazać jednego bloku options bez response-policy"
            )

        status = "BLOCKED_EXTERNAL" if any(
            item.startswith("EXTERNAL:") for item in conflicts
        ) else "BLOCKED_CONFLICT" if conflicts else "READY"
        next_action = (
            "Utwórz osobny plan migracji istniejącej integracji EXTERNAL; "
            "nie przejmuj jej automatycznie."
            if status == "BLOCKED_EXTERNAL"
            else "Usuń lub wyjaśnij konflikty przed przygotowaniem transakcji."
            if status == "BLOCKED_CONFLICT"
            else "Można przygotować osobny dry-run transakcji MANAGED."
        )
        return RpzManagedPlan(
            status=status,
            zone=self.zone,
            source_url=self.source_url,
            root_config=self.root_config,
            zone_file=self.zone_file,
            declaration_file=self.declaration_file,
            updater_file=self.updater_file,
            service_file=self.service_file,
            timer_file=self.timer_file,
            backup_root=self.backup_root,
            conflicts=tuple(conflicts),
            steps=(
                "pobierz RPZ przez HTTPS do pliku tymczasowego",
                f"zweryfikuj kandydat przez named-checkzone {self.zone}",
                "utwórz backup i manifest wszystkich zastępowanych plików",
                "zapisz aktualizator, deklarację i unity atomowo",
                "wykonaj named-checkconf przed aktywacją",
                "wykonaj systemctl daemon-reload i włącz timer co 5 minut",
                "wykonaj kontrolowany rndc reconfig i rndc zonestatus",
                "po każdym błędzie przywróć pliki i stan unitów z backupu",
            ),
            next_action=next_action,
            options_file=options_file,
        )

    @staticmethod
    def _options_file(config_files: tuple[str, ...]) -> Path | None:
        """Return the sole file containing the active top-level options block."""
        candidates: list[Path] = []
        pattern = re.compile(r"\boptions\s*\{", re.IGNORECASE)
        for raw in config_files:
            path = Path(raw)
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if pattern.search(text):
                candidates.append(path)
        return candidates[0] if len(candidates) == 1 else None
