"""Isolated dry-run for a fresh optional CERT Polska RPZ installation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.request import urlopen

from .bind_config import BindConfigDiscovery
from .rpz_managed_plan import RpzManagedPlan
from .runner import CommandResult, run


@dataclass(frozen=True, slots=True)
class RpzManagedInstallStep:
    name: str
    ok: bool
    message: str


@dataclass(slots=True)
class RpzManagedInstallResult:
    zone: str
    status: str
    committed: bool = False
    activated: bool = False
    rolled_back: bool = False
    transaction_id: str | None = None
    backup: str | None = None
    manifest: str | None = None
    candidate_hashes: dict[str, str] = field(default_factory=dict)
    steps: list[RpzManagedInstallStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


Fetcher = Callable[[str], bytes]
CERT_RPZ_ORIGIN = "hole.cert.pl."


def normalize_cert_rpz_payload(payload: bytes, zone: str) -> bytes:
    """Rebase the published CERT Polska RPZ tree under the local zone name."""
    text = payload.decode("utf-8")
    origin_pattern = re.compile(
        rf"(?im)^(?P<prefix>\s*\$ORIGIN\s+){re.escape(CERT_RPZ_ORIGIN)}\s*$"
    )
    if not origin_pattern.search(text):
        raise ValueError(
            f"Pobrany plik nie zawiera oczekiwanego originu {CERT_RPZ_ORIGIN}"
        )
    target = f"{zone.rstrip('.')}."
    normalized = origin_pattern.sub(rf"\g<prefix>{target}", text, count=1)
    if not normalized.endswith("\n"):
        normalized += "\n"
    return normalized.encode("utf-8")


def _short_command_message(outcome: CommandResult, *, limit: int = 2000) -> str:
    message = (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}"
    if len(message) <= limit:
        return message
    omitted = len(message) - limit
    return f"{message[:limit].rstrip()}\n... pominięto {omitted} znaków diagnostyki"


class RpzManagedInstallDryRun:
    """Download and validate every candidate without writing system paths."""

    def __init__(
        self,
        *,
        command_runner: Callable[[list[str], int], CommandResult] = run,
        fetcher: Fetcher | None = None,
    ) -> None:
        self.command_runner = command_runner
        self.fetcher = fetcher or self._fetch

    def execute(
        self, plan: RpzManagedPlan, *, payload: bytes | None = None
    ) -> RpzManagedInstallResult:
        result = RpzManagedInstallResult(plan.zone, "PLAN")
        if plan.status != "READY":
            return self._blocked(result, "; ".join(plan.conflicts) or plan.status)
        if plan.options_file is None:
            return self._blocked(result, "Nie wskazano pliku zawierającego blok options")
        if not plan.source_url.casefold().startswith("https://"):
            return self._blocked(result, "Źródło RPZ musi używać HTTPS")

        try:
            payload = payload if payload is not None else self.fetcher(plan.source_url)
            if not payload.strip():
                return self._blocked(result, "Pobrany kandydat RPZ jest pusty")
            with tempfile.TemporaryDirectory(prefix="zonectl-rpz-install-") as raw:
                workspace = Path(raw)
                candidates = self._build_candidates(plan, payload, workspace)
                result.steps.append(
                    RpzManagedInstallStep(
                        "candidates", True,
                        f"Kandydaci utworzeni wyłącznie w {workspace}",
                    )
                )
                result.candidate_hashes = {
                    name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for name, path in candidates.items()
                }
                self._command(result, "updater-syntax", ["bash", "-n", str(candidates["updater"])])
                self._command(
                    result, "named-checkzone",
                    ["named-checkzone", plan.zone, str(candidates["zone-file"])],
                )
                self._command(
                    result, "named-checkconf",
                    ["named-checkconf", str(candidates["root-config"])],
                )
                self._validate_units(result, candidates["service"], candidates["timer"], plan)
        except (OSError, ValueError) as exc:
            result.steps.append(RpzManagedInstallStep("dry-run", False, str(exc)))

        result.steps.append(
            RpzManagedInstallStep(
                "no-system-write", True,
                "Nie zapisano /etc, /usr ani /var i nie uruchomiono systemctl lub rndc",
            )
        )
        result.status = "DRY-RUN" if all(step.ok for step in result.steps) else "FAILED"
        return result

    def _build_candidates(
        self, plan: RpzManagedPlan, payload: bytes, workspace: Path
    ) -> dict[str, Path]:
        options_original = plan.options_file.read_text(encoding="utf-8", errors="replace")
        options_candidate = self._inject_response_policy(options_original, plan.zone)
        declaration = (
            f'zone "{plan.zone}" {{\n'
            "    type primary;\n"
            f'    file "{plan.zone_file}";\n'
            "    notify no;\n"
            "    allow-query { localhost; };\n"
            "    allow-transfer { none; };\n"
            "};\n"
        )
        updater = self._updater(plan)
        service = self._service(plan)
        timer = self._timer(plan)

        paths = {
            "zone-file": workspace / "domains_rpz.db",
            "declaration": workspace / "zonectl-rpz.conf",
            "options": workspace / "named.conf.options",
            "updater": workspace / "update-cert-rpz",
            "service": workspace / "zonectl-cert-rpz.service",
            "timer": workspace / "zonectl-cert-rpz.timer",
            "root-config": workspace / "named.conf",
        }
        paths["zone-file"].write_bytes(normalize_cert_rpz_payload(payload, plan.zone))
        paths["declaration"].write_text(declaration, encoding="utf-8")
        paths["options"].write_text(options_candidate, encoding="utf-8")
        paths["updater"].write_text(updater, encoding="utf-8")
        paths["service"].write_text(service, encoding="utf-8")
        paths["timer"].write_text(timer, encoding="utf-8")

        root_text = plan.root_config.read_text(encoding="utf-8", errors="replace")
        root_text = self._redirect_direct_include(
            root_text, plan.root_config, plan.options_file, paths["options"]
        )
        root_text += f'\ninclude "{paths["declaration"]}";\n'
        paths["root-config"].write_text(root_text, encoding="utf-8")
        return paths

    @staticmethod
    def _inject_response_policy(text: str, zone: str) -> str:
        stripped = BindConfigDiscovery._strip_comments(text)
        if re.search(r"\bresponse-policy\b", stripped, re.IGNORECASE):
            raise ValueError("Blok options zawiera już response-policy")
        match = re.search(r"\boptions\s*\{", stripped, re.IGNORECASE)
        if not match:
            raise ValueError("Nie znaleziono bloku options")
        opening = stripped.find("{", match.start(), match.end())
        closing = BindConfigDiscovery._matching_brace(stripped, opening)
        if closing is None:
            raise ValueError("Blok options jest niedomknięty")
        statement = f'\n    response-policy {{ zone "{zone}"; }};\n'
        return text[:closing] + statement + text[closing:]

    @staticmethod
    def _redirect_direct_include(
        root_text: str, root_path: Path, options_path: Path, candidate: Path
    ) -> str:
        include_re = re.compile(r'include\s+"(?P<path>[^"]+)"\s*;', re.IGNORECASE)
        for match in include_re.finditer(root_text):
            raw = Path(match.group("path"))
            resolved = raw if raw.is_absolute() else root_path.parent / raw
            if resolved.resolve() == options_path.resolve():
                return root_text[: match.start()] + f'include "{candidate}";' + root_text[match.end() :]
        if root_path.resolve() == options_path.resolve():
            return root_text.replace(root_text, candidate.read_text(encoding="utf-8"))
        raise ValueError("Plik options nie jest bezpośrednio dołączony przez konfigurację główną")

    @staticmethod
    def _updater(plan: RpzManagedPlan) -> str:
        return f'''#!/bin/sh
set -eu
umask 027
tmp=$(mktemp /var/tmp/zonectl-rpz.XXXXXX)
normalized=$(mktemp /var/tmp/zonectl-rpz-normalized.XXXXXX)
checked=$(mktemp /var/tmp/zonectl-rpz-checked.XXXXXX)
current_normalized=
trap 'rm -f "$tmp" "$normalized" "$checked" ${{current_normalized:-}}' EXIT
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \\
  --output "$tmp" '{plan.source_url}'
grep -Eqi '^[[:space:]]*\\$ORIGIN[[:space:]]+hole\\.cert\\.pl\\.[[:space:]]*$' "$tmp"
sed -E 's|^([[:space:]]*\\$ORIGIN[[:space:]]+)hole\\.cert\\.pl\\.[[:space:]]*$|\\1{plan.zone}.|I' \\
  "$tmp" >"$normalized"
named-checkzone -D '{plan.zone}' "$normalized" >"$checked"
new_serial=$(awk '$4 == "SOA" {{ print $7; exit }}' "$checked")
test -n "$new_serial"
if test -f '{plan.zone_file}'; then
  current_normalized=$(mktemp /var/tmp/zonectl-rpz-current.XXXXXX)
  named-checkzone -D '{plan.zone}' '{plan.zone_file}' >"$current_normalized"
  current_serial=$(awk '$4 == "SOA" {{ print $7; exit }}' "$current_normalized")
  rm -f "$current_normalized"
  test -n "$current_serial"
  test "$new_serial" -ge "$current_serial"
  mkdir -p '{plan.backup_root}/zones'
  cp -p '{plan.zone_file}' '{plan.backup_root}/zones/domains_rpz.db.'"$current_serial"
fi
install -o root -g bind -m 0644 "$checked" '{plan.zone_file}.candidate'
mv -f '{plan.zone_file}.candidate' '{plan.zone_file}'
rndc reload '{plan.zone}'
rm -f "$normalized"
'''

    @staticmethod
    def _service(plan: RpzManagedPlan) -> str:
        return f'''[Unit]
Description=Update CERT Polska RPZ managed by ZoneCTL
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
ExecStart={plan.updater_file}
User=root
Group=root
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
ProtectHome=yes
ReadWritePaths={plan.zone_file.parent} {plan.backup_root} /var/tmp
'''

    @staticmethod
    def _timer(plan: RpzManagedPlan) -> str:
        return f'''[Unit]
Description=Update CERT Polska RPZ every 5 minutes

[Timer]
OnCalendar=*:0/5
RandomizedDelaySec=30s
Persistent=true
AccuracySec=10s
Unit={plan.service_file.name}

[Install]
WantedBy=timers.target
'''

    def _command(
        self, result: RpzManagedInstallResult, name: str, command: list[str]
    ) -> None:
        outcome = self.command_runner(command, 30)
        message = _short_command_message(outcome)
        result.steps.append(RpzManagedInstallStep(name, outcome.returncode == 0, message))

    @staticmethod
    def _validate_units(
        result: RpzManagedInstallResult, service: Path, timer: Path, plan: RpzManagedPlan
    ) -> None:
        service_text = service.read_text(encoding="utf-8")
        timer_text = timer.read_text(encoding="utf-8")
        valid = (
            f"ExecStart={plan.updater_file}" in service_text
            and "OnCalendar=*:0/5" in timer_text
            and f"Unit={plan.service_file.name}" in timer_text
        )
        result.steps.append(
            RpzManagedInstallStep(
                "unit-candidates", valid,
                "Timer co 5 minut i usługa MANAGED są spójne"
                if valid else "Niespójne unity MANAGED",
            )
        )

    @staticmethod
    def _blocked(
        result: RpzManagedInstallResult, message: str
    ) -> RpzManagedInstallResult:
        result.status = "BLOCKED"
        result.steps.append(RpzManagedInstallStep("preflight", False, message))
        return result

    @staticmethod
    def _fetch(url: str) -> bytes:
        with urlopen(url, timeout=30) as response:  # noqa: S310 - HTTPS checked above
            return response.read()


class RpzManagedInstallTransaction:
    """Install fresh MANAGED RPZ artifacts atomically and roll back on failure."""

    def __init__(
        self,
        *,
        command_runner: Callable[[list[str], int], CommandResult] = run,
        fetcher: Fetcher | None = None,
        manifest_directory: Path = Path("/var/backups/zonectl-rpz/manifests"),
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] = time.sleep,
        max_zone_age: int = 600,
    ) -> None:
        self.command_runner = command_runner
        self.fetcher = fetcher or RpzManagedInstallDryRun._fetch
        self.manifest_directory = manifest_directory
        self.clock = clock
        self.sleeper = sleeper
        self.max_zone_age = max_zone_age

    def apply(
        self,
        plan: RpzManagedPlan,
        *,
        commit: bool = False,
        activate: bool = False,
        confirm: str | None = None,
    ) -> RpzManagedInstallResult:
        txid = datetime.now().strftime("%Y%m%d-%H%M%S") + f"-rpz-install-{uuid.uuid4().hex[:8]}"
        result = RpzManagedInstallResult(plan.zone, "PLAN", transaction_id=txid)
        if plan.status != "READY":
            return self._blocked(result, "; ".join(plan.conflicts) or plan.status)
        if commit != activate:
            return self._rejected(
                result, "Instalacja wymaga jednocześnie --commit i --activate"
            )
        if commit and confirm != plan.zone:
            return self._rejected(
                result, f"Potwierdzenie musi mieć dokładną wartość: {plan.zone}"
            )
        if plan.options_file is None:
            return self._blocked(result, "Nie wskazano pliku options")

        options_original = plan.options_file.read_bytes()
        root_original = plan.root_config.read_bytes()
        try:
            payload = self.fetcher(plan.source_url)
        except OSError as exc:
            return self._blocked(result, f"Nie pobrano RPZ: {exc}")
        dry_run = RpzManagedInstallDryRun(
            command_runner=self.command_runner, fetcher=self.fetcher
        ).execute(plan, payload=payload)
        result.candidate_hashes = dry_run.candidate_hashes
        result.steps.extend(
            RpzManagedInstallStep(f"dry-run:{step.name}", step.ok, step.message)
            for step in dry_run.steps
        )
        if dry_run.status != "DRY-RUN":
            result.status = "BLOCKED"
            return result
        if not commit:
            result.status = "DRY-RUN"
            return result
        if plan.options_file.read_bytes() != options_original or plan.root_config.read_bytes() != root_original:
            return self._blocked(result, "Konfiguracja BIND zmieniła się po dry-runie")
        for target in self._targets(plan):
            if target.exists():
                return self._blocked(result, f"Plik docelowy pojawił się po dry-runie: {target}")

        backup = plan.backup_root / "installs" / txid
        result.backup = str(backup)
        installed: list[Path] = []
        created_directories: list[Path] = []
        activation_started = False
        try:
            backup.mkdir(parents=True, mode=0o750)
            shutil.copy2(plan.options_file, backup / plan.options_file.name)
            shutil.copy2(plan.root_config, backup / plan.root_config.name)
            result.steps.append(RpzManagedInstallStep("backup", True, f"Backup: {backup}"))

            with tempfile.TemporaryDirectory(prefix="zonectl-rpz-install-commit-") as raw:
                candidates = RpzManagedInstallDryRun(
                    command_runner=self.command_runner, fetcher=self.fetcher
                )._build_candidates(plan, payload, Path(raw))
                options_stat = plan.options_file.stat()
                root_stat = plan.root_config.stat()
                created_directories = self._prepare_zone_directory(
                    plan.zone_file.parent, options_stat.st_uid, options_stat.st_gid
                )
                writes = (
                    (plan.zone_file, candidates["zone-file"].read_bytes(), 0o644, options_stat.st_uid, options_stat.st_gid),
                    (plan.declaration_file, candidates["declaration"].read_bytes(), 0o640, options_stat.st_uid, options_stat.st_gid),
                    (plan.updater_file, candidates["updater"].read_bytes(), 0o750, 0, 0),
                    (plan.service_file, candidates["service"].read_bytes(), 0o644, 0, 0),
                    (plan.timer_file, candidates["timer"].read_bytes(), 0o644, 0, 0),
                    (plan.options_file, candidates["options"].read_bytes(), options_stat.st_mode & 0o777, options_stat.st_uid, options_stat.st_gid),
                )
                for target, content, mode, uid, gid in writes:
                    self._atomic_write(target, content, mode, uid, gid)
                    if target not in {plan.options_file, plan.root_config}:
                        installed.append(target)
                root_active = root_original.decode("utf-8", errors="replace")
                root_active += f'\ninclude "{plan.declaration_file}";\n'
                self._atomic_write(
                    plan.root_config, root_active.encode("utf-8"),
                    root_stat.st_mode & 0o777, root_stat.st_uid, root_stat.st_gid,
                )
            result.steps.append(
                RpzManagedInstallStep("configuration", True, "Zapisano artefakty MANAGED atomowo")
            )
            self._must_run(["named-checkconf", str(plan.root_config)], "named-checkconf", result)
            activation_started = True
            self._must_run(["systemctl", "daemon-reload"], "daemon-reload", result)
            self._must_run(["rndc", "reconfig"], "rndc-reconfig", result)
            self._must_run_retry(
                ["rndc", "zonestatus", plan.zone],
                "rndc-zonestatus",
                result,
                attempts=30,
                interval=1.0,
            )
            self._must_run(
                ["systemctl", "enable", "--now", plan.timer_file.name],
                "timer-enable", result,
            )
            self._must_run(
                ["systemctl", "start", plan.service_file.name],
                "first-update", result,
            )
            self._post_gate(plan, result)
            result.status = "COMMIT"
            result.committed = True
            result.activated = True
            self._write_manifest(result)
        except (OSError, RuntimeError) as exc:
            result.steps.append(RpzManagedInstallStep("transaction", False, str(exc)))
            result.rolled_back = self._rollback(
                plan, options_original, root_original, installed,
                created_directories, activation_started, result
            )
            result.status = "ROLLED-BACK" if result.rolled_back else "ROLLBACK-FAILED"
            try:
                self._write_manifest(result)
            except OSError as manifest_error:
                result.steps.append(RpzManagedInstallStep("manifest", False, str(manifest_error)))
        return result

    @staticmethod
    def _targets(plan: RpzManagedPlan) -> tuple[Path, ...]:
        return (
            plan.zone_file, plan.declaration_file, plan.updater_file,
            plan.service_file, plan.timer_file,
        )

    def _must_run(
        self, command: list[str], name: str, result: RpzManagedInstallResult
    ) -> CommandResult:
        outcome = self.command_runner(command, 30)
        message = _short_command_message(outcome)
        result.steps.append(RpzManagedInstallStep(name, outcome.returncode == 0, message))
        if outcome.returncode != 0:
            raise RuntimeError(f"{name}: {message}")
        return outcome

    def _must_run_retry(
        self,
        command: list[str],
        name: str,
        result: RpzManagedInstallResult,
        *,
        attempts: int,
        interval: float,
    ) -> CommandResult:
        outcome = CommandResult(1, "", "nie wykonano")
        for attempt in range(1, attempts + 1):
            outcome = self.command_runner(command, 30)
            if outcome.returncode == 0:
                message = _short_command_message(outcome)
                result.steps.append(
                    RpzManagedInstallStep(
                        name, True, f"{message} (próba {attempt}/{attempts})"
                    )
                )
                return outcome
            if attempt < attempts:
                self.sleeper(interval)
        message = _short_command_message(outcome)
        result.steps.append(RpzManagedInstallStep(name, False, message))
        raise RuntimeError(f"{name}: {message}")

    def _post_gate(self, plan: RpzManagedPlan, result: RpzManagedInstallResult) -> None:
        self._must_run(["systemctl", "is-enabled", plan.timer_file.name], "timer-enabled", result)
        self._must_run(["systemctl", "is-active", plan.timer_file.name], "timer-active", result)
        self._must_run(["systemctl", "is-active", "bind9"], "bind-active", result)
        service = self._must_run(
            ["systemctl", "show", plan.service_file.name, "--property=Result", "--value"],
            "service-result", result,
        )
        if service.stdout.strip() != "success":
            raise RuntimeError("Usługa aktualizująca nie zakończyła się wynikiem success")
        age = max(0, int(self.clock() - plan.zone_file.stat().st_mtime))
        fresh = age <= self.max_zone_age
        result.steps.append(RpzManagedInstallStep("freshness", fresh, f"wiek {age} s"))
        if not fresh:
            raise RuntimeError("Plik RPZ nie jest świeży")

    def _rollback(
        self,
        plan: RpzManagedPlan,
        options_original: bytes,
        root_original: bytes,
        installed: list[Path],
        created_directories: list[Path],
        activation_started: bool,
        result: RpzManagedInstallResult,
    ) -> bool:
        ok = True
        if activation_started:
            if self.command_runner(
                ["systemctl", "disable", "--now", plan.timer_file.name], 30
            ).returncode != 0:
                ok = False
        try:
            options_stat = plan.options_file.stat()  # type: ignore[union-attr]
            root_stat = plan.root_config.stat()
            self._atomic_write(
                plan.options_file, options_original, options_stat.st_mode & 0o777,
                options_stat.st_uid, options_stat.st_gid,
            )
            self._atomic_write(
                plan.root_config, root_original, root_stat.st_mode & 0o777,
                root_stat.st_uid, root_stat.st_gid,
            )
            for path in reversed(installed):
                path.unlink(missing_ok=True)
            for directory in created_directories:
                try:
                    directory.rmdir()
                except OSError:
                    pass
        except OSError:
            ok = False
        if activation_started:
            if self.command_runner(["systemctl", "daemon-reload"], 30).returncode != 0:
                ok = False
            if self.command_runner(["rndc", "reconfig"], 30).returncode != 0:
                ok = False
        result.steps.append(
            RpzManagedInstallStep(
                "rollback", ok,
                "Usunięto MANAGED i przywrócono konfigurację BIND"
                if ok else "Nie udało się w pełni przywrócić konfiguracji",
            )
        )
        return ok

    @staticmethod
    def _prepare_zone_directory(path: Path, uid: int, gid: int) -> list[Path]:
        missing: list[Path] = []
        cursor = path
        while not cursor.exists():
            missing.append(cursor)
            cursor = cursor.parent
        path.mkdir(parents=True, exist_ok=True, mode=0o750)
        os.chown(path, uid, gid)
        os.chmod(path, 0o750)
        return missing

    @staticmethod
    def _atomic_write(path: Path, content: bytes, mode: int, uid: int, gid: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(raw)
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

    def _write_manifest(self, result: RpzManagedInstallResult) -> None:
        self.manifest_directory.mkdir(parents=True, exist_ok=True, mode=0o750)
        path = self.manifest_directory / f"{result.transaction_id}.json"
        result.manifest = str(path)
        payload = result.to_dict()
        payload["saved_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _blocked(
        result: RpzManagedInstallResult, message: str
    ) -> RpzManagedInstallResult:
        result.status = "BLOCKED"
        result.steps.append(RpzManagedInstallStep("preflight", False, message))
        return result

    @staticmethod
    def _rejected(
        result: RpzManagedInstallResult, message: str
    ) -> RpzManagedInstallResult:
        result.status = "REJECTED"
        result.steps.append(RpzManagedInstallStep("guard", False, message))
        return result
