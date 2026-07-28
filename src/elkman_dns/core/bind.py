from __future__ import annotations

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
        self.dns2_server = t.get("dns2_server", "5.172.189.198")
        self.he_server = t.get("he_server", "216.218.133.2")
        self.timeout = int(t.get("dig_timeout", "3"))

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
        status = ZoneStatus(zone=zone)
        status.file_exists = bool(zone.file and zone.file.exists())
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
                problems.append("inny serial DNS2")
        if zone.he:
            if status.he_serial is None:
                problems.append("brak SOA HE")
            elif status.local_serial and status.he_serial != status.local_serial:
                problems.append("inny serial HE")
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
