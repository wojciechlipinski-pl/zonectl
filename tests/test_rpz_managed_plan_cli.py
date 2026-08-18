from pathlib import Path

from zonectl import cli
from zonectl.core.rpz_managed_plan import RpzManagedPlan


class _EmptyConfig:
    def zones(self):
        return []


def _plan(status: str = "READY") -> RpzManagedPlan:
    return RpzManagedPlan(
        status, "cert-rpz.local", "https://hole.cert.pl/domains/v2/domains_rpz.db",
        Path("/etc/bind/named.conf"), Path("/var/lib/zonectl/rpz/domains_rpz.db"),
        Path("/etc/bind/zonectl-rpz.conf"), Path("/usr/lib/zonectl/update-cert-rpz"),
        Path("/etc/systemd/system/zonectl-cert-rpz.service"),
        Path("/etc/systemd/system/zonectl-cert-rpz.timer"),
        Path("/var/backups/zonectl-rpz"),
        () if status == "READY" else ("EXTERNAL: istniejący aktualizator",),
        ("pobierz kandydat", "zweryfikuj kandydat"),
        "Można przygotować dry-run." if status == "READY" else "Nie przejmuj.",
    )


def test_managed_plan_cli_is_read_only(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    monkeypatch.setattr(cli.RpzManagedPlanner, "plan", lambda self: _plan())
    code = cli.main(["bind", "rpz-managed-plan"])
    output = capsys.readouterr().out
    assert code == 0
    assert "TYLKO ODCZYT" in output
    assert "Status:       READY" in output
    assert "niczego nie zapisano" in output


def test_managed_plan_cli_reports_external_blocker(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    monkeypatch.setattr(
        cli.RpzManagedPlanner, "plan", lambda self: _plan("BLOCKED_EXTERNAL")
    )
    code = cli.main(["bind", "rpz-managed-plan"])
    output = capsys.readouterr().out
    assert code == 1
    assert "BLOCKED_EXTERNAL" in output
    assert "EXTERNAL" in output
