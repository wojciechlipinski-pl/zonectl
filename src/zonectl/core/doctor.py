"""Privacy-safe, read-only host diagnostics and GitHub issue preparation."""

from __future__ import annotations

import configparser
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import urlencode


SCHEMA = "zonectl.doctor/v1"
REPORT_SCHEMA = "zonectl.doctor-report/v1"
DEFAULT_REPOSITORY = "wojciechlipinski-pl/zonectl"
PUBLIC_CONFIRMATION = "WYŚLIJ"
MIN_FREE_BYTES = 256 * 1024 * 1024
MAX_ISSUE_URL_LENGTH = 1800


@dataclass(frozen=True)
class GitHistorySettings:
    """Minimal optional-history settings readable without loading all config."""

    enabled: bool | None
    directory: Path


def read_git_history_settings(config_path: Path) -> GitHistorySettings:
    """Read only Git-history settings while keeping Doctor failure tolerant."""
    from .paths import GIT_HISTORY_DIR

    parser = configparser.ConfigParser(interpolation=None)
    try:
        loaded = parser.read(config_path, encoding="utf-8")
    except (configparser.Error, OSError, UnicodeError):
        return GitHistorySettings(None, GIT_HISTORY_DIR)
    if not loaded:
        return GitHistorySettings(False, GIT_HISTORY_DIR)
    if "toolkit" not in parser:
        return GitHistorySettings(None, GIT_HISTORY_DIR)
    section = parser["toolkit"]
    raw_enabled = section.get("git_history_enabled")
    enabled = raw_enabled is not None and raw_enabled.strip().casefold() in {
        "1",
        "yes",
        "true",
        "on",
        "tak",
    }
    raw_directory = section.get("git_history_directory", str(GIT_HISTORY_DIR)).strip()
    return GitHistorySettings(enabled, Path(raw_directory).expanduser())


class CommandResult(Protocol):
    """Minimal result returned by an injected command runner."""

    returncode: int
    stdout: str
    stderr: str


class DiskUsage(Protocol):
    """Minimal filesystem capacity result used by diagnostics."""

    @property
    def free(self) -> int:
        """Return available bytes."""
        ...


CommandRunner = Callable[[Sequence[str], int], CommandResult]


@dataclass(frozen=True)
class DoctorCheck:
    """One allowlisted diagnostic result without environment identifiers."""

    code: str
    status: str
    summary: str
    action: str | None = None

    def to_dict(self) -> dict[str, str]:
        """Return the public, versioned representation of this check."""
        result = {"code": self.code, "status": self.status, "summary": self.summary}
        if self.action:
            result["action"] = self.action
        return result


PolicyProbe = Callable[[Path], DoctorCheck]


@dataclass(frozen=True)
class DoctorReport:
    """Bounded diagnostic report safe to render or export."""

    generated_at: str
    status: str
    zonectl_version: str
    bind_version: str | None
    package_version: str | None
    checks: tuple[DoctorCheck, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible allowlisted payload."""
        return {
            "schema": SCHEMA,
            "generated_at": self.generated_at,
            "status": self.status,
            "versions": {
                "zonectl": self.zonectl_version,
                "bind": self.bind_version,
                "package": self.package_version,
            },
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass(frozen=True)
class PreparedIssue:
    """A reviewed public issue payload and a browser-copyable URL."""

    title: str
    body: str
    url: str
    report_path: Path | None = None
    body_in_url: bool = True


def _run(command: Sequence[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _disk_usage(path: Path) -> DiskUsage:
    return shutil.disk_usage(path)


def _version(text: str) -> str | None:
    match = re.search(r"\b(\d+\.\d+(?:\.\d+)?(?:[-+~][A-Za-z0-9.]+)?)\b", text)
    return match.group(1) if match else None


def _status(checks: Sequence[DoctorCheck]) -> str:
    if any(item.status == "BLOCKED" for item in checks):
        return "BLOCKED"
    if any(item.status == "WARN" for item in checks):
        return "WARN"
    return "PASS"


def _policy_check(root_config: Path) -> DoctorCheck:
    """Summarize DNSSEC/KASP safety without exposing policy or zone names."""
    from .bind_capabilities import BindCapabilityDetector
    from .discovery import BindDiscoveryError
    from .dnssec_policy_inventory import DnssecPolicyInventoryReader

    try:
        capabilities = BindCapabilityDetector().detect()
        inventory = DnssecPolicyInventoryReader(root_config, capabilities).read()
    except (BindDiscoveryError, OSError, ValueError):
        return DoctorCheck(
            "dnssec.policies",
            "WARN",
            "nie można ocenić polityk DNSSEC/KASP",
            "uruchom odczytowy raport polityk DNSSEC",
        )
    if inventory.undefined_references or any(
        policy.status == "BLOCKED" or policy.bind_compatibility == "BLOCKED"
        for policy in inventory.policies
    ):
        return DoctorCheck(
            "dnssec.policies",
            "BLOCKED",
            "wykryto zablokowaną lub niespójną politykę DNSSEC/KASP",
            "przejrzyj raport polityk przed zmianą DNSSEC",
        )
    if any(
        policy.status == "REVIEW" or policy.bind_compatibility in {"REVIEW", "UNKNOWN"}
        for policy in inventory.policies
    ):
        return DoctorCheck(
            "dnssec.policies",
            "WARN",
            "co najmniej jedna polityka DNSSEC/KASP wymaga oceny",
            "przejrzyj raport zgodności polityk",
        )
    return DoctorCheck(
        "dnssec.policies",
        "PASS",
        "polityki DNSSEC/KASP nie mają znanych blokad",
    )


class Doctor:
    """Run bounded read-only checks without collecting production identifiers."""

    def __init__(
        self,
        *,
        zonectl_version: str,
        root_config: Path = Path("/etc/bind/named.conf"),
        directories: Sequence[tuple[str, Path]] = (),
        git_history: GitHistorySettings | None = None,
        command_runner: CommandRunner = _run,
        which: Callable[[str], str | None] = shutil.which,
        disk_usage: Callable[[Path], DiskUsage] = _disk_usage,
        policy_probe: PolicyProbe = _policy_check,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.zonectl_version = zonectl_version
        self.root_config = root_config
        self.directories = tuple(directories)
        self.git_history = git_history or GitHistorySettings(False, Path("."))
        self.command_runner = command_runner
        self.which = which
        self.disk_usage = disk_usage
        self.policy_probe = policy_probe
        self.now = now

    def collect(self) -> DoctorReport:
        """Collect host health without mutating services, files or configuration."""
        checks: list[DoctorCheck] = []
        required = ("named-checkconf", "rndc", "systemctl")
        available = {name: self.which(name) is not None for name in required}
        for name in required:
            checks.append(
                DoctorCheck(
                    f"tool.{name}",
                    "PASS" if available[name] else "BLOCKED",
                    "narzędzie dostępne" if available[name] else "brak narzędzia",
                    None
                    if available[name]
                    else f"zainstaluj wymagane narzędzie {name}",
                )
            )

        bind_version: str | None = None
        if available["named-checkconf"]:
            version_result = self.command_runner(["named-checkconf", "-v"], 10)
            bind_version = _version(version_result.stdout + " " + version_result.stderr)
            checks.append(
                DoctorCheck(
                    "bind.version",
                    "PASS" if bind_version else "WARN",
                    "wersja BIND rozpoznana"
                    if bind_version
                    else "nie rozpoznano wersji BIND",
                    None if bind_version else "sprawdź instalację pakietów BIND",
                )
            )
            config_result = self.command_runner(
                ["named-checkconf", str(self.root_config)], 30
            )
            checks.append(
                DoctorCheck(
                    "bind.configuration",
                    "PASS" if config_result.returncode == 0 else "BLOCKED",
                    "konfiguracja BIND poprawna"
                    if config_result.returncode == 0
                    else "walidacja konfiguracji BIND nie powiodła się",
                    None
                    if config_result.returncode == 0
                    else "uruchom named-checkconf lokalnie i popraw konfigurację",
                )
            )

        if available["systemctl"]:
            active = self.command_runner(["systemctl", "is-active", "bind9"], 10)
            checks.append(
                DoctorCheck(
                    "bind.service",
                    "PASS" if active.returncode == 0 else "BLOCKED",
                    "usługa BIND aktywna"
                    if active.returncode == 0
                    else "usługa BIND nieaktywna",
                    None
                    if active.returncode == 0
                    else "sprawdź stan i dziennik usługi bind9",
                )
            )
            timer = self.command_runner(
                ["systemctl", "is-enabled", "zonectl-cert-rpz.timer"], 10
            )
            if timer.returncode == 0:
                timer_active = self.command_runner(
                    ["systemctl", "is-active", "zonectl-cert-rpz.timer"], 10
                )
                checks.append(
                    DoctorCheck(
                        "rpz.timer",
                        "PASS" if timer_active.returncode == 0 else "WARN",
                        "timer RPZ aktywny"
                        if timer_active.returncode == 0
                        else "włączony timer RPZ nie jest aktywny",
                        None
                        if timer_active.returncode == 0
                        else "sprawdź timer zarządzanej integracji RPZ",
                    )
                )
                service = self.command_runner(
                    [
                        "systemctl",
                        "show",
                        "zonectl-cert-rpz.service",
                        "--property=Result",
                        "--value",
                    ],
                    10,
                )
                result_ok = service.returncode == 0 and service.stdout.strip() in {
                    "success",
                    "",
                }
                checks.append(
                    DoctorCheck(
                        "rpz.service",
                        "PASS" if result_ok else "WARN",
                        "ostatni wynik integracji RPZ poprawny"
                        if result_ok
                        else "ostatni wynik integracji RPZ wymaga kontroli",
                        None
                        if result_ok
                        else "sprawdź usługę zarządzanej integracji RPZ",
                    )
                )

        if available["rndc"]:
            control = self.command_runner(["rndc", "status"], 15)
            checks.append(
                DoctorCheck(
                    "bind.control",
                    "PASS" if control.returncode == 0 else "WARN",
                    "kanał sterowania BIND odpowiada"
                    if control.returncode == 0
                    else "kanał sterowania BIND jest niedostępny",
                    None
                    if control.returncode == 0
                    else "sprawdź konfigurację i uprawnienia rndc",
                )
            )

        package_version: str | None = None
        if self.which("dpkg-query"):
            package = self.command_runner(
                ["dpkg-query", "-W", "-f=${Version}", "zonectl"], 10
            )
            if package.returncode == 0:
                package_version = _version(package.stdout)
        checks.append(
            DoctorCheck(
                "package.version",
                "PASS" if package_version else "WARN",
                "pakiet systemowy rozpoznany"
                if package_version
                else "nie rozpoznano pakietu systemowego",
                None if package_version else "sprawdź sposób instalacji ZoneCTL",
            )
        )

        for label, path in self.directories:
            checks.extend(self._directory_checks(label, path))

        checks.extend(self._git_history_checks())

        checks.append(self.policy_probe(self.root_config))

        backup_ready = any(
            check.code == "directory.backup" and check.status == "PASS"
            for check in checks
        )
        checks.append(
            DoctorCheck(
                "rollback.readiness",
                "PASS" if backup_ready else "BLOCKED",
                "miejsce backupu i rollbacku gotowe"
                if backup_ready
                else "miejsce backupu i rollbacku nie jest gotowe",
                None
                if backup_ready
                else "przywróć prywatny, zapisywalny katalog backupu",
            )
        )

        return DoctorReport(
            generated_at=self.now().isoformat(),
            status=_status(checks),
            zonectl_version=self.zonectl_version,
            bind_version=bind_version,
            package_version=package_version,
            checks=tuple(checks),
        )

    def _git_history_checks(self) -> tuple[DoctorCheck, ...]:
        """Classify disabled, uninitialized, ready and unsafe local history."""
        settings = self.git_history
        if settings.enabled is None:
            return (
                DoctorCheck(
                    "directory.historia-git",
                    "WARN",
                    "nie można odczytać konfiguracji historii Git",
                    "sprawdź sekcję toolkit w konfiguracji ZoneCTL",
                ),
            )
        if not settings.enabled:
            return (
                DoctorCheck(
                    "directory.historia-git",
                    "PASS",
                    "opcjonalna historia Git wyłączona zgodnie z konfiguracją",
                ),
            )

        path = settings.directory
        if self.which("git") is None:
            return (
                DoctorCheck(
                    "tool.git",
                    "BLOCKED",
                    "historia Git jest włączona, lecz brak narzędzia Git",
                    "zainstaluj Git albo wyłącz opcjonalną historię",
                ),
            )
        if not path.exists():
            return (
                DoctorCheck(
                    "directory.historia-git",
                    "WARN",
                    "historia Git jest włączona, lecz niezainicjalizowana",
                    "uruchom plan, a następnie potwierdzoną inicjalizację historii Git",
                ),
            )
        if path.is_symlink() or not path.is_dir():
            return (
                DoctorCheck(
                    "directory.historia-git",
                    "BLOCKED",
                    "ścieżka historii Git ma niebezpieczny typ",
                    "usuń dowiązanie lub plik i użyj prywatnego katalogu",
                ),
            )
        try:
            mode = stat.S_IMODE(path.stat().st_mode)
        except OSError:
            mode = 0o777
        if mode & 0o027:
            return (
                DoctorCheck(
                    "directory.historia-git",
                    "BLOCKED",
                    "katalog historii Git ma zbyt szerokie uprawnienia",
                    "usuń zapis grupowy i wszystkie uprawnienia innych użytkowników",
                ),
            )
        if not (path / ".git").is_dir():
            return (
                DoctorCheck(
                    "directory.historia-git",
                    "WARN",
                    "historia Git jest włączona, lecz niezainicjalizowana",
                    "uruchom plan, a następnie potwierdzoną inicjalizację historii Git",
                ),
            )
        remote = self.command_runner(["git", "-C", str(path), "remote"], 10)
        if remote.returncode != 0:
            return (
                DoctorCheck(
                    "directory.historia-git",
                    "BLOCKED",
                    "lokalna historia Git jest uszkodzona lub niedostępna",
                    "sprawdź prywatne repozytorium historii Git",
                ),
            )
        if remote.stdout.strip():
            return (
                DoctorCheck(
                    "directory.historia-git",
                    "BLOCKED",
                    "lokalna historia Git ma niedozwolony remote",
                    "usuń remote; historia stref musi pozostać wyłącznie lokalna",
                ),
            )
        return self._directory_checks("historia Git", path)

    def _directory_checks(self, label: str, path: Path) -> tuple[DoctorCheck, ...]:
        code = re.sub(r"[^a-z0-9]+", "-", label.casefold()).strip("-") or "state"
        if not path.is_dir():
            return (
                DoctorCheck(
                    f"directory.{code}",
                    "WARN",
                    f"katalog {label} niedostępny",
                    f"sprawdź instalację i uprawnienia katalogu {label}",
                ),
            )
        writable = os.access(path, os.R_OK | os.W_OK | os.X_OK)
        checks = [
            DoctorCheck(
                f"directory.{code}",
                "PASS" if writable else "BLOCKED",
                f"katalog {label} dostępny"
                if writable
                else f"katalog {label} ma nieprawidłowe uprawnienia",
                None if writable else f"napraw uprawnienia katalogu {label}",
            )
        ]
        try:
            free = self.disk_usage(path).free
        except OSError:
            free = 0
        checks.append(
            DoctorCheck(
                f"storage.{code}",
                "PASS" if free >= MIN_FREE_BYTES else "WARN",
                "dostępne miejsce wystarczające"
                if free >= MIN_FREE_BYTES
                else "mało dostępnego miejsca",
                None
                if free >= MIN_FREE_BYTES
                else "zwolnij miejsce przed operacją zapisu",
            )
        )
        return tuple(checks)


_IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
_IPV6 = re.compile(r"(?<![\w:])(?:[0-9A-Fa-f]{0,4}:){2,}[0-9A-Fa-f:]{0,4}(?![\w:])")
_EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_ABS_PATH = re.compile(r"(?<!\w)/(?:etc|home|root|opt|srv|tmp|usr|var)/[^\s`]+")
_LONG_HEX = re.compile(r"\b[0-9A-Fa-f]{32,}\b")


def privacy_findings(text: str) -> tuple[str, ...]:
    """Return categories of data forbidden in a public diagnostic report."""
    patterns = {
        "ipv4": _IPV4,
        "ipv6": _IPV6,
        "email": _EMAIL,
        "absolute-path": _ABS_PATH,
        "key-or-digest": _LONG_HEX,
    }
    return tuple(name for name, pattern in patterns.items() if pattern.search(text))


def render_text(report: DoctorReport) -> str:
    """Render a bounded operator-facing diagnostic summary."""
    lines = [
        "RAPORT DIAGNOSTYCZNY ZONECTL — TYLKO ODCZYT",
        f"Status: {report.status}",
        f"ZoneCTL: {report.zonectl_version}",
        f"BIND: {report.bind_version or '-'}",
        f"Pakiet: {report.package_version or '-'}",
        "",
    ]
    for check in report.checks:
        lines.append(f"[{check.status}] {check.code}: {check.summary}")
        if check.action:
            lines.append(f"  Następny krok: {check.action}")
    lines.append("")
    lines.append("Wynik: diagnostyka nie wprowadziła żadnych zmian.")
    return "\n".join(lines)


def issue_body(report: DoctorReport) -> str:
    """Build a public Markdown body exclusively from allowlisted fields."""
    failing = [check for check in report.checks if check.status != "PASS"]
    lines = [
        "## ZoneCTL doctor report",
        "",
        f"- Schema: `{REPORT_SCHEMA}`",
        f"- Overall status: `{report.status}`",
        f"- ZoneCTL: `{report.zonectl_version}`",
        f"- BIND: `{report.bind_version or 'unknown'}`",
        f"- Package: `{report.package_version or 'unknown'}`",
        "",
        "## Findings",
        "",
    ]
    if not failing:
        lines.append("- No WARN or BLOCKED findings.")
    for check in failing:
        lines.append(f"- **{check.status}** `{check.code}` — {check.summary}")
        if check.action:
            lines.append(f"  - Suggested action: {check.action}")
    lines.extend(
        [
            "",
            "## Privacy",
            "",
            "Generated from an allowlist. Zone names, addresses, host names, "
            "environment paths, contact data, keys and DS digests were not collected.",
            "",
            "The operator reviewed this content before publication.",
        ]
    )
    body = "\n".join(lines)
    findings = privacy_findings(body)
    if findings:
        raise ValueError(
            "raport publiczny zawiera niedozwolone dane: " + ", ".join(findings)
        )
    return body


def prepare_issue(
    report: DoctorReport,
    *,
    repository: str = DEFAULT_REPOSITORY,
    report_path: Path | None = None,
) -> PreparedIssue:
    """Create a browser-copyable Issue URL without sending anything."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("nieprawidłowy identyfikator repozytorium GitHub")
    title = f"[doctor] ZoneCTL {report.zonectl_version}: {report.status}"
    body = issue_body(report)
    base = f"https://github.com/{repository}/issues/new"
    query = urlencode({"title": title, "body": body})
    url = f"{base}?{query}"
    body_in_url = len(url) <= MAX_ISSUE_URL_LENGTH
    if not body_in_url:
        url = f"{base}?{urlencode({'template': 'doctor.yml', 'title': title})}"
    return PreparedIssue(
        title=title,
        body=body,
        url=url,
        report_path=report_path,
        body_in_url=body_in_url,
    )


def write_public_report(report: DoctorReport, directory: Path) -> Path:
    """Atomically write a mode-0600 report after a second privacy scan."""
    body = issue_body(report)
    if directory.is_symlink():
        raise OSError("katalog raportów nie może być dowiązaniem symbolicznym")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not directory.is_dir() or directory.is_symlink():
        raise OSError("nieprawidłowy katalog raportów")
    os.chmod(directory, 0o700)
    timestamp = report.generated_at.replace(":", "").replace("+", "-")
    target = directory / f"zonectl-doctor-{timestamp}.md"
    fd, temporary = tempfile.mkstemp(prefix=".doctor-", dir=directory, text=True)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        os.chmod(target, 0o600)
        directory_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return target


def submit_issue(
    prepared: PreparedIssue,
    *,
    repository: str = DEFAULT_REPOSITORY,
    confirmation: str,
    command_runner: CommandRunner = _run,
    which: Callable[[str], str | None] = shutil.which,
) -> str:
    """Create a public Issue through an existing authenticated ``gh`` session."""
    if confirmation != PUBLIC_CONFIRMATION:
        raise ValueError(
            f"publiczna wysyłka wymaga potwierdzenia {PUBLIC_CONFIRMATION}"
        )
    if which("gh") is None:
        raise RuntimeError("brak klienta gh; użyj przygotowanego linku")
    auth = command_runner(["gh", "auth", "status", "--hostname", "github.com"], 15)
    if auth.returncode != 0:
        raise RuntimeError("klient gh nie jest uwierzytelniony")
    if privacy_findings(prepared.title + "\n" + prepared.body):
        raise ValueError("ponowny skan prywatności zablokował wysyłkę")
    result = command_runner(
        [
            "gh",
            "issue",
            "create",
            "--repo",
            repository,
            "--title",
            prepared.title,
            "--body",
            prepared.body,
        ],
        30,
    )
    if result.returncode != 0:
        raise RuntimeError("GitHub odrzucił utworzenie zgłoszenia")
    url = result.stdout.strip()
    if not url.startswith("https://github.com/"):
        raise RuntimeError("GitHub nie zwrócił adresu zgłoszenia")
    return url


def json_text(report: DoctorReport) -> str:
    """Serialize the allowlisted diagnostic contract."""
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
