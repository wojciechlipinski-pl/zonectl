from __future__ import annotations

import os
import time
from pathlib import Path

from zonectl.core.bind import BindService
from zonectl.core.models import Health, Zone


class FakeConfig:
    def __init__(self, grace: int = 600):
        self.toolkit = {
            "secondary_propagation_grace_seconds": str(grace),
        }


def status_for(
    tmp_path: Path,
    monkeypatch,
    *,
    primary: str = "2026082102",
    dns2: str | None = "2026082102",
    he: str | None = "2026082101",
    age: int = 60,
    grace: int = 600,
):
    zone_file = tmp_path / "example.test"
    zone_file.write_text("zone", encoding="utf-8")
    timestamp = time.time() - age
    os.utime(zone_file, (timestamp, timestamp))
    service = BindService(FakeConfig(grace))
    serials = {
        service.local_server: primary,
        service.dns2_server: dns2,
        service.he_server: he,
    }
    monkeypatch.setattr(service, "serial", lambda server, _zone: serials[server])
    monkeypatch.setattr(service, "dnssec_enabled", lambda _zone: True)
    return service.quick_status(Zone("example.test", zone_file, dns2=True, he=True))


def test_secondary_lag_is_warning_during_propagation(tmp_path, monkeypatch):
    status = status_for(tmp_path, monkeypatch, age=75)
    assert status.health is Health.WARN
    assert "propagacja HE" in status.message
    assert "75/600s" in status.message


def test_secondary_lag_fails_after_grace_period(tmp_path, monkeypatch):
    status = status_for(tmp_path, monkeypatch, age=601)
    assert status.health is Health.FAIL
    assert status.message == "nieaktualny serial HE"


def test_secondary_ahead_of_primary_fails_immediately(tmp_path, monkeypatch):
    status = status_for(tmp_path, monkeypatch, he="2026082103", age=5)
    assert status.health is Health.FAIL
    assert status.message == "serial HE wyższy od primary"


def test_missing_secondary_soa_fails_immediately(tmp_path, monkeypatch):
    status = status_for(tmp_path, monkeypatch, he=None, age=5)
    assert status.health is Health.FAIL
    assert status.message == "brak SOA HE"


def test_serial_comparison_handles_32_bit_wrap():
    assert BindService._serial_relation("0", "4294967295") == "behind"
    assert BindService._serial_relation("4294967295", "0") == "ahead"
