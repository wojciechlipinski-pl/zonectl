"""Model prezentacyjny stałego panelu szczegółów strefy."""

from __future__ import annotations

from dataclasses import dataclass

from ..core.models import Zone, ZoneStatus


@dataclass(frozen=True, slots=True)
class ZoneDetailsView:
    """Zwięzłe szczegóły aktywnej strefy do prawego panelu TUI."""

    title: str
    lines: tuple[str, ...]
    summary_title: str
    summary_lines: tuple[str, ...]

    @classmethod
    def build(cls, zone: Zone, status: ZoneStatus) -> "ZoneDetailsView":
        profile = zone.health_profile.upper()
        lines = [
            f"Grupa         {zone.group}",
            f"Plik          {zone.file or '-'}",
            "",
        ]
        if zone.health_profile.casefold() == "rpz":
            lines.extend(
                (
                    f"Wiek RPZ      {cls._age(status.file_age_seconds)}",
                    f"Limit wieku   {cls._age(zone.rpz_max_age)}",
                    f"Plik istnieje {cls._yes_no(status.file_exists)}",
                    "Szczegóły      F3",
                )
            )
        else:
            lines.extend(
                (
                    f"SOA primary   {status.local_serial or '-'}",
                    f"SOA dns2      {status.dns2_serial or '-'}",
                    f"SOA HE        {status.he_serial or '-'}",
                    f"DNSSEC        {cls._dnssec(status.dnssec)}",
                    f"Secondary     {cls._secondary(zone)}",
                )
            )
        summary = [
            f"Status        {status.health.value}",
            f"Profil        {profile}",
        ]
        if zone.health_profile.casefold() != "rpz":
            summary.extend(
                (
                    f"DNSSEC        {cls._dnssec(status.dnssec)}",
                    f"Secondary     {cls._secondary(zone)}",
                )
            )
        summary.extend(("", "KOMUNIKAT", status.message or "-"))
        return cls(
            title=zone.name,
            lines=tuple(lines),
            summary_title="Stan operacyjny",
            summary_lines=tuple(summary),
        )

    @staticmethod
    def _age(seconds: int | None) -> str:
        if seconds is None:
            return "-"
        minutes, remainder = divmod(max(0, seconds), 60)
        return f"{minutes} min {remainder} s"

    @staticmethod
    def _yes_no(value: bool | None) -> str:
        if value is None:
            return "NIEZNANY"
        return "TAK" if value else "NIE"

    @staticmethod
    def _dnssec(value: bool | None) -> str:
        if value is None:
            return "NIEZNANY"
        return "AKTYWNY" if value else "WYŁĄCZONY"

    @staticmethod
    def _secondary(zone: Zone) -> str:
        targets: list[str] = []
        if zone.dns2:
            targets.append("dns2")
        if zone.he:
            targets.append("HE")
        return ", ".join(targets) or "-"
