from pathlib import Path

from zonectl import cli
from zonectl.core.bind_secondary_health import (
    SecondarySoaObservation,
    SecondaryZoneHealth,
)


class _EmptyConfig:
    def zones(self):
        return []


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "named.conf"
    root.write_text(
        "primaries dns2-notify { 192.0.2.53; };\n"
        "acl dns2-transfer { 192.0.2.53; };\n"
        'zone "example.test" { type primary; file "/tmp/example";\n'
        " also-notify { dns2-notify; };\n"
        " allow-transfer { dns2-transfer; }; };\n",
        encoding="utf-8",
    )
    return root


def test_secondary_health_cli_is_read_only(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    monkeypatch.setattr(
        cli.BindSecondaryHealthGate,
        "check",
        lambda self, zones, servers: (
            SecondaryZoneHealth(
                zones[0],
                "PASS",
                2026082001,
                (SecondarySoaObservation(servers[0], True, 2026082001, "OK"),),
                "Secondary zgodny",
            ),
        ),
    )
    root = _root(tmp_path)
    before = root.read_bytes()

    code = cli.main(
        [
            "bind",
            "secondary-health",
            "--pair",
            "dns2",
            "--root-config",
            str(root),
        ]
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "AUDYT OPERACYJNY SECONDARY" in output
    assert "[PASS] example.test" in output
    assert "niczego nie zmieniono" in output
    assert root.read_bytes() == before


def test_secondary_health_uses_notify_endpoint_and_skips_rpz(
    monkeypatch, tmp_path, capsys
) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    root = tmp_path / "named.conf"
    root.write_text(
        "primaries he-notify { 192.0.2.53; };\n"
        "acl he-transfer { 192.0.2.54; };\n"
        'zone "cert-rpz.local" { type primary; file "/tmp/rpz";\n'
        " also-notify { he-notify; }; allow-transfer { he-transfer; }; };\n",
        encoding="utf-8",
    )
    calls = []
    monkeypatch.setattr(
        cli.BindSecondaryHealthGate,
        "check",
        lambda self, zones, servers: calls.append((zones, servers)) or (),
    )

    code = cli.main(
        [
            "bind",
            "secondary-health",
            "--root-config",
            str(root),
        ]
    )

    output = capsys.readouterr().out
    assert code == 0
    assert calls == [((), ("192.0.2.53",))]
    assert "[SKIP] cert-rpz.local" in output


def test_secondary_health_cli_rejects_unknown_pair(
    monkeypatch, tmp_path, capsys
) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())

    code = cli.main(
        [
            "bind",
            "secondary-health",
            "--pair",
            "missing",
            "--root-config",
            str(_root(tmp_path)),
        ]
    )

    assert code == 2
    assert "Nieznane pary" in capsys.readouterr().err
