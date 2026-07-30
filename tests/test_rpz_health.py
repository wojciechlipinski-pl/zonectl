from pathlib import Path

from zonectl.core.bind import BindService
from zonectl.core.models import Health, Zone
from zonectl.core.runner import CommandResult


class FakeConfig:
    toolkit = {
        "local_server": "127.0.0.1",
        "dig_timeout": "3",
    }


def result(returncode: int = 0) -> CommandResult:
    return CommandResult(
        returncode=returncode,
        stdout="",
        stderr="",
    )


def test_rpz_profile_does_not_query_soa_or_dnssec(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "cert-rpz.local"
    source.write_text("rpz\n", encoding="utf-8")
    monkeypatch.setattr(
        "zonectl.core.bind.run",
        lambda *args, **kwargs: result(),
    )
    monkeypatch.setattr(
        "zonectl.core.bind.time.time",
        lambda: source.stat().st_mtime + 60,
    )

    service = BindService(FakeConfig())
    monkeypatch.setattr(
        service,
        "serial",
        lambda *args: (_ for _ in ()).throw(
            AssertionError("RPZ nie powinna pytać o SOA")
        ),
    )
    monkeypatch.setattr(
        service,
        "dnssec_enabled",
        lambda *args: (_ for _ in ()).throw(
            AssertionError("RPZ nie powinna pytać o DNSSEC")
        ),
    )

    status = service.quick_status(
        Zone(
            name="cert-rpz.local",
            file=source,
            health_profile="rpz",
            rpz_max_age=600,
        )
    )

    assert status.health is Health.PASS
    assert status.file_age_seconds == 60


def test_stale_rpz_fails_health_check(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "cert-rpz.local"
    source.write_text("rpz\n", encoding="utf-8")
    monkeypatch.setattr(
        "zonectl.core.bind.run",
        lambda *args, **kwargs: result(),
    )
    monkeypatch.setattr(
        "zonectl.core.bind.time.time",
        lambda: source.stat().st_mtime + 601,
    )

    status = BindService(FakeConfig()).quick_status(
        Zone(
            name="cert-rpz.local",
            file=source,
            health_profile="rpz",
            rpz_max_age=600,
        )
    )

    assert status.health is Health.FAIL
    assert "nieaktualna" in status.message
