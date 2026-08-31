"""Safe SOA preparation before DNSSEC withdrawal finalization."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from .runner import run
from .soa_serial import bump_document_soa_serial
from .zone_file_parser import ZoneFileParser
from .zone_writer import ZoneWriter


@dataclass(slots=True)
class DnssecFinalizeSerialStep:
    name: str
    ok: bool
    message: str


@dataclass(slots=True)
class DnssecFinalizeSerialResult:
    transaction_id: str
    zone: str
    status: str
    previous_serial: int | None = None
    served_serial: int | None = None
    new_serial: int | None = None
    committed: bool = False
    backup: str | None = None
    steps: list[DnssecFinalizeSerialStep] = field(default_factory=list)


ServedSerialReader = Callable[[str], int | None]
ZoneValidator = Callable[[str, Path], DnssecFinalizeSerialStep]


class DnssecFinalizeSerialTransaction:
    """Raise the source SOA above the currently served signed serial."""

    def __init__(
        self,
        backup_root: Path,
        *,
        served_serial_reader: ServedSerialReader | None = None,
        validator: ZoneValidator | None = None,
        today_provider: Callable[[], date] = date.today,
    ) -> None:
        self.backup_root = backup_root
        self.served_serial_reader = served_serial_reader or self._served_serial
        self.validator = validator or self._validate_zone
        self.today_provider = today_provider

    def apply(
        self,
        zone: str,
        zone_file: Path,
        *,
        commit: bool = False,
    ) -> DnssecFinalizeSerialResult:
        txid = (
            datetime.now().strftime("%Y%m%d-%H%M%S")
            + f"-dnssec-finalize-serial-{zone}-{uuid.uuid4().hex[:8]}"
        )
        result = DnssecFinalizeSerialResult(txid, zone, "PLAN")
        if not zone_file.is_file():
            return self._blocked(result, f"Brak pliku strefy: {zone_file}")
        served = self.served_serial_reader(zone)
        result.served_serial = served
        if served is None:
            return self._blocked(
                result, "Nie udało się odczytać obecnie serwowanego serialu"
            )
        try:
            document = ZoneFileParser.parse_file(zone_file)
            change = bump_document_soa_serial(
                document,
                today=self.today_provider(),
                minimum_current=served,
            )
            candidate = ZoneWriter().render_document(document)
        except (OSError, RuntimeError, ValueError) as exc:
            return self._blocked(result, str(exc))
        result.previous_serial = change.previous
        result.new_serial = change.current
        result.steps.append(
            DnssecFinalizeSerialStep(
                "serial-plan",
                True,
                f"{change.previous} -> {change.current}; serwowany={served}",
            )
        )

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{zone_file.name}.serial-", dir=zone_file.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(candidate)
                handle.flush()
                os.fsync(handle.fileno())
            validation = self.validator(zone, temporary)
            result.steps.append(validation)
            if not validation.ok:
                result.status = "BLOCKED"
                return result
            if not commit:
                result.status = "DRY-RUN"
                result.steps.append(
                    DnssecFinalizeSerialStep(
                        "dry-run", True, "Nie zmieniono pliku strefy ani BIND"
                    )
                )
                return result

            source_stat = zone_file.stat()
            self.backup_root.mkdir(parents=True, exist_ok=True, mode=0o750)
            backup = self.backup_root / f"{txid}-{zone_file.name}"
            shutil.copy2(zone_file, backup)
            result.backup = str(backup)
            result.steps.append(
                DnssecFinalizeSerialStep("backup", True, f"Backup: {backup}")
            )
            os.chmod(temporary, source_stat.st_mode & 0o7777)
            if hasattr(os, "chown"):
                os.chown(temporary, source_stat.st_uid, source_stat.st_gid)
            os.replace(temporary, zone_file)
            result.committed = True
            result.status = "COMMIT"
            result.steps.append(
                DnssecFinalizeSerialStep(
                    "zone-file",
                    True,
                    f"Zapisano serial {change.current}; nie wykonano rndc",
                )
            )
            return result
        finally:
            if temporary.exists():
                temporary.unlink()

    @staticmethod
    def _blocked(
        result: DnssecFinalizeSerialResult, message: str
    ) -> DnssecFinalizeSerialResult:
        result.status = "BLOCKED"
        result.steps.append(DnssecFinalizeSerialStep("preflight", False, message))
        return result

    @staticmethod
    def _served_serial(zone: str) -> int | None:
        outcome = run(["rndc", "zonestatus", zone], 15)
        if outcome.returncode != 0:
            return None
        text = outcome.stdout + outcome.stderr
        match = re.search(
            r"^signed serial:\s*(\d+)\s*$",
            text,
            re.MULTILINE | re.IGNORECASE,
        ) or re.search(r"^serial:\s*(\d+)\s*$", text, re.MULTILINE | re.IGNORECASE)
        return int(match.group(1)) if match else None

    @staticmethod
    def _validate_zone(zone: str, candidate: Path) -> DnssecFinalizeSerialStep:
        outcome = run(["named-checkzone", zone, str(candidate)], 30)
        message = (
            outcome.stdout or outcome.stderr
        ).strip() or f"kod {outcome.returncode}"
        return DnssecFinalizeSerialStep(
            "named-checkzone", outcome.returncode == 0, message
        )
