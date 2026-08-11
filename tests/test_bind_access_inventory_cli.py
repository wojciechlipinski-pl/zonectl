import json
from pathlib import Path

from zonectl import cli


class _EmptyConfig:
    def zones(self):
        return []


def test_bind_inventory_cli_json(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    root = tmp_path / "named.conf"
    root.write_text('acl "trusted" { 192.0.2.0/24; };\n', encoding="utf-8")
    code = cli.main([
        "bind", "inventory", "--root-config", str(root), "--json"
    ])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["definitions"][0]["name"] == "trusted"


def test_bind_inventory_cli_text(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    root = tmp_path / "named.conf"
    root.write_text(
        'primaries dns2 { 192.0.2.53; };\n'
        'zone "x" { also-notify { dns2; }; };\n', encoding="utf-8"
    )
    code = cli.main(["bind", "inventory", "--root-config", str(root)])
    output = capsys.readouterr().out
    assert code == 0
    assert "[PRIMARIES] dns2" in output
    assert "[also-notify]" in output
