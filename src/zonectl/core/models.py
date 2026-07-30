from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Health(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(slots=True)
class Zone:
    name: str
    file: Path | None
    enabled: bool = True
    dns2: bool = True
    he: bool = False
    notify: bool = True
    reload: bool = True
    group: str = "Pozostałe"
    health_profile: str = "authoritative"
    rpz_max_age: int = 600


@dataclass(slots=True)
class ZoneStatus:
    zone: Zone
    health: Health = Health.UNKNOWN
    local_serial: str | None = None
    dns2_serial: str | None = None
    he_serial: str | None = None
    dnssec: bool | None = None
    file_exists: bool | None = None
    file_age_seconds: int | None = None
    message: str = "Nie sprawdzono"
