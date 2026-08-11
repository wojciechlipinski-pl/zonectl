"""Transakcyjne wycofanie DNSSEC — dwa etapy.

BIND nie pozwala po prostu usunąć ``dnssec-policy``: dokumentacja wymaga
przejścia przez wbudowaną politykę ``insecure``, bo w przeciwnym razie
strefa zostanie ponownie podpisana. Stąd dwa etapy:

**Etap ``insecure``** — podmienia ``dnssec-policy default`` na
``dnssec-policy insecure``, zostawiając ``inline-signing``. Bramką jest
zniknięcie DS ze wszystkich kontrolowanych resolverów, czyli dokładnie ten
sam warunek, który przepuszcza ``withdrawal-confirm``. Dopiero ta zmiana
przestawia cel KASP z ``omnipresent`` na ``hidden`` i uruchamia
uporządkowane wycofywanie kluczy.

**Etap ``finalize``** — usuwa ``dnssec-policy``, ``inline-signing`` i
``key-directory``. Bramką jest potwierdzenie z KASP, że **wszystkie** klucze
mają ``goal``, ``dnskey`` i ``ds`` w stanie ``hidden``. Ta bramka jest
osiągalna wyłącznie po etapie pierwszym.

W obu etapach brak ``--commit`` oznacza dry-run, każde niepowodzenie
walidacji powoduje pełny rollback deklaracji z backupu, a klucze i pakiet
odtworzeniowy pozostają nietknięte.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .dnssec_disable_plan import DnssecDisablePlan
from .runner import run


@dataclass(slots=True)
class DnssecDisableStep:
    name: str
    ok: bool
    message: str


@dataclass(slots=True)
class DnssecDisableResult:
    transaction_id: str
    zone: str
    status: str
    committed: bool = False
    rolled_back: bool = False
    stage: str = "insecure"
    kasp_states: tuple[str, ...] = ()
    manifest: str | None = None
    backup_directory: str | None = None
    steps: list[DnssecDisableStep] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.steps) and all(step.ok for step in self.steps)


KaspReader = Callable[[str], "KaspReading"]
DsGate = Callable[[str], bool | None]
ConfigValidator = Callable[[Path], DnssecDisableStep]
ZoneAction = Callable[[str], DnssecDisableStep]
SerialGate = Callable[[str, Path], DnssecDisableStep]


@dataclass(slots=True)
class KaspReading:
    """Odczyt stanu kluczy z ``rndc dnssec -status``.

    ``all_hidden`` jest ``None``, gdy wyjścia nie udało się zinterpretować —
    tylko wtedy dopuszczamy świadome przesłonięcie bramki.
    """

    all_hidden: bool | None
    states: tuple[str, ...]
    message: str


_KEY_STATE = re.compile(r"(?mi)^\s*-\s*(goal|dnskey|ds):\s*(\S+)\s*$")


def read_kasp_states(zone: str, timeout: int = 30) -> KaspReading:
    outcome = run(["rndc", "dnssec", "-status", zone], timeout)
    if outcome.returncode != 0:
        detail = (outcome.stderr or outcome.stdout).strip()
        return KaspReading(
            None, (), f"rndc zwrócił kod {outcome.returncode}: {detail}"
        )
    found = _KEY_STATE.findall(outcome.stdout or "")
    if not found:
        return KaspReading(
            None, (), "Nie odnaleziono stanów kluczy w wyjściu rndc dnssec -status"
        )
    states = tuple(f"{name.casefold()}={value.casefold()}" for name, value in found)
    all_hidden = all(value.casefold() == "hidden" for _name, value in found)
    return KaspReading(all_hidden, states, "Odczytano stany kluczy z KASP")


class DnssecDisableTransaction:
    """Stosuje diff wycofania DNSSEC z backupem i pełnym rollbackiem."""

    def __init__(
        self,
        backup_root: Path,
        manifest_directory: Path,
        *,
        root_config: Path = Path("/etc/bind/named.conf"),
        kasp_reader: KaspReader | None = None,
        ds_gate: DsGate | None = None,
        config_validator: ConfigValidator | None = None,
        activator: ZoneAction | None = None,
        loaded_verifier: ZoneAction | None = None,
        serial_gate: SerialGate | None = None,
    ) -> None:
        self.backup_root = backup_root
        self.manifest_directory = manifest_directory
        self.root_config = root_config
        self.kasp_reader = kasp_reader or read_kasp_states
        self.ds_gate = ds_gate
        self.config_validator = config_validator or self._validate_config
        self.activator = activator or self._activate_bind
        self.loaded_verifier = loaded_verifier or self._verify_loaded
        self.serial_gate = serial_gate or self._serial_gate

    def apply(
        self,
        plan: DnssecDisablePlan,
        *,
        stage: str = "insecure",
        commit: bool = False,
        activate: bool = False,
        acknowledge_unsigned: bool = False,
    ) -> DnssecDisableResult:
        if stage not in {"insecure", "finalize"}:
            raise ValueError(f"Nieznany etap wycofania: {stage}")
        txid = (
            datetime.now().strftime("%Y%m%d-%H%M%S")
            + f"-dnssec-disable-{stage}-{plan.zone}-{uuid.uuid4().hex[:8]}"
        )
        result = DnssecDisableResult(txid, plan.zone, "PLAN")
        result.stage = stage
        target_text = (
            plan.insecure_text if stage == "insecure" else plan.candidate_text
        )

        conflict = self._preflight(plan, target_text)
        if conflict is not None:
            return self._finish(result, "CONFLICT", conflict, write_manifest=False)

        if stage == "insecure":
            gate = self._insecure_gate(plan.zone, acknowledge_unsigned)
        else:
            reading = self.kasp_reader(plan.zone)
            result.kasp_states = reading.states
            gate = self._finalize_gate(reading, acknowledge_unsigned)
        result.steps.append(gate)
        if not gate.ok:
            return self._finish(result, "BLOCKED", write_manifest=False)

        if stage == "finalize":
            serial_gate = self.serial_gate(plan.zone, plan.zone_file)
            result.steps.append(serial_gate)
            if not serial_gate.ok:
                return self._finish(result, "BLOCKED", write_manifest=False)

        if not commit:
            return self._finish(
                result,
                "DRY-RUN",
                DnssecDisableStep("dry-run", True, "Nie zmieniono plików ani BIND"),
                write_manifest=False,
            )

        backup_directory = self.backup_root / txid
        result.backup_directory = str(backup_directory)
        declaration_stat = plan.declaration_file.stat()
        config_written = False
        activation_attempted = False
        try:
            backup_directory.mkdir(parents=True, mode=0o750)
            self._copy_backup(
                plan.declaration_file, backup_directory / "bind-declaration.conf"
            )
            result.steps.append(
                DnssecDisableStep("backup", True, f"Backup: {backup_directory}")
            )

            self._atomic_write(
                plan.declaration_file,
                target_text.encode("utf-8"),
                declaration_stat.st_mode & 0o777,
                declaration_stat.st_uid,
                declaration_stat.st_gid,
            )
            config_written = True
            result.steps.append(
                DnssecDisableStep(
                    "configuration", True, f"Zaktualizowano {plan.declaration_file}"
                )
            )

            config_step = self.config_validator(self.root_config)
            result.steps.append(config_step)
            if not config_step.ok:
                raise RuntimeError(config_step.message)

            if activate:
                activation_attempted = True
                for action in (self.activator, self.loaded_verifier):
                    step = action(plan.zone)
                    result.steps.append(step)
                    if not step.ok:
                        raise RuntimeError(step.message)

            result.committed = True
            result.steps.append(
                DnssecDisableStep(
                    "keys",
                    True,
                    "Klucze i pakiet odtworzeniowy pozostawiono nienaruszone",
                )
            )
            return self._finish(result, "COMMIT")
        except Exception as exc:
            result.steps.append(DnssecDisableStep("transaction", False, str(exc)))
            rollback_ok = True
            try:
                if config_written:
                    self._atomic_write(
                        plan.declaration_file,
                        (backup_directory / "bind-declaration.conf").read_bytes(),
                        declaration_stat.st_mode & 0o777,
                        declaration_stat.st_uid,
                        declaration_stat.st_gid,
                    )
                if activation_attempted:
                    restore = self.activator(plan.zone)
                    result.steps.append(
                        DnssecDisableStep(
                            "rndc-reconfig-rollback", restore.ok, restore.message
                        )
                    )
                    if not restore.ok:
                        rollback_ok = False
            except OSError as rollback_error:
                rollback_ok = False
                result.steps.append(
                    DnssecDisableStep("rollback", False, str(rollback_error))
                )
            else:
                result.steps.append(
                    DnssecDisableStep(
                        "rollback", rollback_ok, "Przywrócono stan sprzed transakcji"
                    )
                )
            result.rolled_back = rollback_ok
            return self._finish(
                result, "ROLLED-BACK" if rollback_ok else "ROLLBACK-FAILED"
            )

    def _insecure_gate(
        self, zone: str, acknowledge_unsigned: bool
    ) -> DnssecDisableStep:
        """Etap 1 wolno wykonać dopiero, gdy DS zniknął z resolverów."""
        if self.ds_gate is None:
            if acknowledge_unsigned:
                return DnssecDisableStep(
                    "ds-gate",
                    True,
                    "Brak kontroli DS; operator potwierdził wycofanie "
                    "flagą --acknowledge-unsigned",
                )
            return DnssecDisableStep(
                "ds-gate",
                False,
                "Blokada: nie skonfigurowano kontroli DS. Uruchom najpierw "
                "withdrawal-check albo użyj --acknowledge-unsigned.",
            )
        absent = self.ds_gate(zone)
        if absent is True:
            return DnssecDisableStep(
                "ds-gate", True, "DS nie jest widoczny na żadnym resolverze"
            )
        if absent is False:
            return DnssecDisableStep(
                "ds-gate",
                False,
                "Blokada: DS jest nadal widoczny na co najmniej jednym "
                "resolverze. Tej blokady nie wolno przesłonić.",
            )
        if acknowledge_unsigned:
            return DnssecDisableStep(
                "ds-gate",
                True,
                "Nie rozstrzygnięto kontroli DS; operator potwierdził "
                "wycofanie flagą --acknowledge-unsigned",
            )
        return DnssecDisableStep(
            "ds-gate",
            False,
            "Blokada: nie rozstrzygnięto kontroli DS. Sprawdź ręcznie i użyj "
            "--acknowledge-unsigned, jeśli DS jest wycofany.",
        )

    @staticmethod
    def _finalize_gate(
        reading: KaspReading, acknowledge_unsigned: bool
    ) -> DnssecDisableStep:
        """Etap 2 wolno wykonać dopiero, gdy KASP schował wszystkie klucze."""
        if reading.all_hidden is True:
            return DnssecDisableStep(
                "kasp-gate", True, "KASP zgłasza wszystkie stany kluczy jako hidden"
            )
        if reading.all_hidden is False:
            visible = ", ".join(
                state for state in reading.states if not state.endswith("=hidden")
            )
            withdrawing = "goal=hidden" in reading.states
            if withdrawing:
                guidance = (
                    "KASP realizuje już etap insecure. Poczekaj do następnego "
                    "zdarzenia KASP i ponów kontrolę; tej blokady nie wolno "
                    "przesłonić."
                )
            else:
                guidance = (
                    "Wykonaj najpierw etap insecure i poczekaj; tej blokady "
                    "nie wolno przesłonić."
                )
            return DnssecDisableStep(
                "kasp-gate",
                False,
                f"Blokada: KASP nie schował jeszcze kluczy ({visible}). "
                + guidance,
            )
        if acknowledge_unsigned:
            return DnssecDisableStep(
                "kasp-gate",
                True,
                f"Nie odczytano stanu KASP ({reading.message}); operator "
                "potwierdził wycofanie flagą --acknowledge-unsigned",
            )
        return DnssecDisableStep(
            "kasp-gate",
            False,
            f"Blokada: nie odczytano stanów kluczy z KASP ({reading.message}). "
            "Sprawdź ręcznie i użyj --acknowledge-unsigned, jeśli klucze są wycofane.",
        )

    @staticmethod
    def _serial_gate(zone: str, zone_file: Path) -> DnssecDisableStep:
        """Nie dopuść do cofnięcia SOA po odłączeniu inline-signing."""
        source_result = run(["named-checkzone", zone, str(zone_file)], 30)
        source_match = re.search(
            r"\bloaded serial\s+(\d+)\b",
            source_result.stdout + source_result.stderr,
            re.IGNORECASE,
        )
        status_result = run(["rndc", "zonestatus", zone], 15)
        status_text = status_result.stdout + status_result.stderr
        signed_match = re.search(
            r"^signed serial:\s*(\d+)\s*$",
            status_text,
            re.MULTILINE | re.IGNORECASE,
        )
        served_match = signed_match or re.search(
            r"^serial:\s*(\d+)\s*$",
            status_text,
            re.MULTILINE | re.IGNORECASE,
        )
        if (
            source_result.returncode != 0
            or status_result.returncode != 0
            or source_match is None
            or served_match is None
        ):
            return DnssecDisableStep(
                "serial-gate",
                False,
                "Blokada: nie udało się jednoznacznie porównać serialu "
                "źródłowego z obecnie serwowanym serialem.",
            )
        source = int(source_match.group(1))
        served = int(served_match.group(1))
        difference = (source - served) % (2**32)
        newer = 0 < difference < 2**31
        if not newer:
            return DnssecDisableStep(
                "serial-gate",
                False,
                f"Blokada: serial źródłowy {source} nie jest wyższy od "
                f"serwowanego serialu {served}. Podbij serial źródłowy przed "
                "finalizacją, aby secondary pobrały strefę bez DNSSEC.",
            )
        return DnssecDisableStep(
            "serial-gate",
            True,
            f"Serial źródłowy {source} jest wyższy od serwowanego {served}",
        )

    @staticmethod
    def _preflight(
        plan: DnssecDisablePlan, target_text: str
    ) -> DnssecDisableStep | None:
        if not plan.declaration_file.is_file():
            return DnssecDisableStep(
                "preflight", False, f"Brak deklaracji: {plan.declaration_file}"
            )
        if plan.declaration_file.read_text(encoding="utf-8") != plan.original_text:
            return DnssecDisableStep(
                "preflight", False, "Konfiguracja zmieniła się od utworzenia planu"
            )
        if not target_text or target_text == plan.original_text:
            return DnssecDisableStep(
                "preflight", False, "Plan nie wprowadza żadnej zmiany"
            )
        return None

    def _finish(
        self,
        result: DnssecDisableResult,
        status: str,
        step: DnssecDisableStep | None = None,
        *,
        write_manifest: bool = True,
    ) -> DnssecDisableResult:
        result.status = status
        if step is not None:
            result.steps.append(step)
        if write_manifest:
            self.manifest_directory.mkdir(parents=True, exist_ok=True, mode=0o750)
            path = self.manifest_directory / f"{result.transaction_id}.json"
            result.manifest = str(path)
            payload = asdict(result)
            payload["saved_at"] = (
                datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
            )
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return result

    @staticmethod
    def _copy_backup(source: Path, target: Path) -> None:
        shutil.copy2(source, target)
        if hasattr(os, "chown"):
            owner = source.stat()
            os.chown(target, owner.st_uid, owner.st_gid)

    @staticmethod
    def _atomic_write(
        path: Path, content: bytes, mode: int, uid: int, gid: int
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "wb") as handle:
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
    def _validate_config(path: Path) -> DnssecDisableStep:
        outcome = run(["named-checkconf", str(path)], 30)
        return DnssecDisableStep(
            "named-checkconf",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}",
        )

    @staticmethod
    def _activate_bind(_zone: str) -> DnssecDisableStep:
        outcome = run(["rndc", "reconfig"], 30)
        return DnssecDisableStep(
            "rndc-reconfig",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}",
        )

    @staticmethod
    def _verify_loaded(zone: str) -> DnssecDisableStep:
        outcome = run(["rndc", "zonestatus", zone], 30)
        return DnssecDisableStep(
            "rndc-zonestatus",
            outcome.returncode == 0,
            (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}",
        )
