from pathlib import Path

from zonectl import cli
from zonectl.core.bind_zone_secondary import BindZoneSecondaryPlanner


class _EmptyConfig:
    def zones(self): return []


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "named.conf"
    root.write_text(
        'primaries dns2-notify { 192.0.2.53; };\n'
        'acl dns2-transfer { 192.0.2.53; };\n'
        'zone "example.pl" { type primary; file "/tmp/example";\n'
        'also-notify { dns2-notify; }; allow-transfer { dns2-transfer; }; };\n',
        encoding="utf-8",
    )
    return root


def test_zone_secondary_apply_defaults_to_dry_run(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    monkeypatch.setattr(
        "zonectl.core.bind_secondary_plan.BindSecondaryPlanner._validate_candidate",
        lambda self, source, candidate: (True, "kod 0"),
    )
    root = _root(tmp_path)
    before = root.read_bytes()
    code = cli.main(["bind", "zone-secondary-apply", "example.pl", "--pair", "dns2", "--root-config", str(root)])
    assert code == 0
    assert "DRY-RUN" in capsys.readouterr().out
    assert root.read_bytes() == before


def test_zone_secondary_apply_requires_both_flags(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    code = cli.main(["bind", "zone-secondary-apply", "example.pl", "--pair", "dns2", "--root-config", str(_root(tmp_path)), "--commit"])
    assert code == 2
    assert "--commit i --activate" in capsys.readouterr().err
