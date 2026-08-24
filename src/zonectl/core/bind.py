from __future__ import annotations

import time

from .config import ToolkitConfig
from .models import Health, Zone, ZoneStatus
from .runner import run
from .zone_parser import DNSRecord, ZoneRecordParser


class BindService:
    """Read-only BIND status service used by the Sprint 1 dashboard."""

    def __init__(self, config: ToolkitConfig):
        self.config = config
        t = config.toolkit
        self.local_server = t.get("local_server", "127.0.0.1")
        self.dns2_server = t.get("dns2_server", "192.0.2.53")
        self.he_server = t.get("he_server", "192.0.2.54")
        self.timeout = int(t.get("dig_timeout", "3"))
        self.secondary_propagation_grace = max(
            0,
            int(t.get("secondary_propagation_grace_seconds", "600")),
        )

    @staticmethod
    def _serial_relation(primary: str, secondary: str) -> str:
        """Porównaj seriale zgodnie z arytmetyką szeregową DNS (RFC 1982)."""
        try:
            primary_value = int(primary)
            secondary_value = int(secondary)
        except ValueError:
            return "different"

        modulo = 2**32
        delta = (primary_value - secondary_value) % modulo
        if delta == 0:
            return "equal"
        if delta < modulo // 2:
            return "behind"
        return "ahead"

    def _secondary_serial_state(
        self,
        label: str,
        primary: str,
        secondary: str,
        file_age_seconds: int | None,
    ) -> tuple[str | None, str | None]:
        relation = self._serial_relation(primary, secondary)
        if relation == "equal":
            return None, None
        if (
            relation == "behind"
            and file_age_seconds is not None
            and file_age_seconds <= self.secondary_propagation_grace
        ):
            return (
                None,
                f"propagacja {label}: serial {secondary} → {primary} "
                f"({file_age_seconds}/{self.secondary_propagation_grace}s)",
            )
        if relation == "behind":
            return f"nieaktualny serial {label}", None
        if relation == "ahead":
            return f"serial {label} wyższy od primary", None
        return f"inny serial {label}", None

    def serial(self, server: str, zone: str) -> str | None:
        result = run(
            ["dig", f"@{server}", zone, "SOA", "+short", f"+time={self.timeout}", "+tries=1"],
            self.timeout + 3,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        fields = result.stdout.splitlines()[0].split()
        return fields[2] if len(fields) >= 3 else None

    def dnssec_enabled(self, zone: str) -> bool | None:
        result = run(["rndc", "dnssec", "-status", zone], 8)
        if result.returncode != 0:
            return None
        text = (result.stdout + result.stderr).lower()
        return "zone signing:" in text and "yes" in text

    def rpz_status(self, zone: Zone) -> ZoneStatus:
        status = ZoneStatus(zone=zone)
        status.file_exists = bool(
            zone.file and zone.file.exists()
        )
        problems: list[str] = []

        if not status.file_exists or zone.file is None:
            problems.append("brak pliku RPZ")
        else:
            status.file_age_seconds = max(
                0,
                int(time.time() - zone.file.stat().st_mtime),
            )
            syntax = run(
                [
                    "named-checkzone",
                    zone.name,
                    str(zone.file),
                ],
                self.timeout + 3,
            )
            if syntax.returncode != 0:
                problems.append("błędna składnia RPZ")

        loaded = run(
            ["rndc", "zonestatus", zone.name],
            self.timeout + 3,
        )
        if loaded.returncode != 0:
            problems.append("RPZ niezaładowana")

        if (
            status.file_age_seconds is not None
            and status.file_age_seconds > zone.rpz_max_age
        ):
            problems.append(
                f"RPZ nieaktualna ({status.file_age_seconds}s)"
            )

        if problems:
            status.health = Health.FAIL
            status.message = "; ".join(problems)
        else:
            status.health = Health.PASS
            status.message = (
                f"RPZ aktualna ({status.file_age_seconds}s)"
            )

        return status


    def zone_records(self, zone: Zone) -> tuple[list[str], str | None]:
        """Zwraca kanoniczną listę rekordów z aktywnego pliku strefy."""
        if zone.file is None:
            return [], "Brak ścieżki do pliku strefy"

        if not zone.file.exists():
            return [], f"Plik strefy nie istnieje: {zone.file}"

        result = run(
            [
                "named-checkzone",
                "-D",
                zone.name,
                str(zone.file),
            ],
            15,
        )

        if result.returncode != 0:
            message = (result.stdout + result.stderr).strip()
            return [], message or "named-checkzone zakończył się błędem"

        records: list[str] = []

        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()

            if not line:
                continue

            lowered = line.casefold()

            if lowered.startswith("zone "):
                continue

            if lowered.startswith("loaded serial"):
                continue

            if lowered == "ok":
                continue

            records.append(line)

        return records, None


    def parsed_zone_records(
        self,
        zone: Zone,
    ) -> tuple[list[DNSRecord], str | None]:
        """Zwraca rekordy strefy przekształcone do modelu DNSRecord."""
        if zone.file is None:
            return [], "Brak ścieżki do pliku strefy"

        if not zone.file.exists():
            return [], f"Plik strefy nie istnieje: {zone.file}"

        result = run(
            [
                "named-checkzone",
                "-D",
                zone.name,
                str(zone.file),
            ],
            15,
        )

        if result.returncode != 0:
            message = (result.stdout + result.stderr).strip()
            return [], message or "named-checkzone zakończył się błędem"

        records = ZoneRecordParser.parse_output(result.stdout)
        return records, None

    def quick_status(self, zone: Zone) -> ZoneStatus:
        if zone.health_profile == "rpz":
            return self.rpz_status(zone)

        status = ZoneStatus(zone=zone)
        status.file_exists = bool(zone.file and zone.file.exists())
        if status.file_exists and zone.file is not None:
            status.file_age_seconds = max(
                0,
                int(time.time() - zone.file.stat().st_mtime),
            )
        status.local_serial = self.serial(self.local_server, zone.name)
        status.dns2_serial = self.serial(self.dns2_server, zone.name) if zone.dns2 else None
        status.he_serial = self.serial(self.he_server, zone.name) if zone.he else None
        status.dnssec = self.dnssec_enabled(zone.name)

        problems: list[str] = []
        warnings: list[str] = []
        if not status.file_exists:
            problems.append("brak pliku strefy")
        if status.local_serial is None:
            problems.append("brak SOA lokalnie")
        if zone.dns2:
            if status.dns2_serial is None:
                problems.append("brak SOA DNS2")
            elif status.local_serial and status.dns2_serial != status.local_serial:
                problem, warning = self._secondary_serial_state(
                    "DNS2", status.local_serial, status.dns2_serial,
                    status.file_age_seconds,
                )
                if problem:
                    problems.append(problem)
                if warning:
                    warnings.append(warning)
        if zone.he:
            if status.he_serial is None:
                problems.append("brak SOA HE")
            elif status.local_serial and status.he_serial != status.local_serial:
                problem, warning = self._secondary_serial_state(
                    "HE", status.local_serial, status.he_serial,
                    status.file_age_seconds,
                )
                if problem:
                    problems.append(problem)
                if warning:
                    warnings.append(warning)
        if status.dnssec is None:
            warnings.append("status DNSSEC nieznany")

        if problems:
            status.health = Health.FAIL
            status.message = "; ".join(problems)
        elif warnings:
            status.health = Health.WARN
            status.message = "; ".join(warnings)
        else:
            status.health = Health.PASS
            status.message = "Podstawowe kontrole poprawne"
        return status
