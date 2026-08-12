import json
from pathlib import Path

from zonectl import cli


class _EmptyConfig:
    def zones(self):
        return []


def test_secondary_report_cli(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    root = tmp_path / "named.conf"
    root.write_text(
        'primaries dns2-notify { 192.0.2.53; };\n'
        'acl "dns2-transfer" { 192.0.2.54; };\n'
        'zone "a" { type primary; file "/a"; also-notify { dns2-notify; }; '
        'allow-transfer { dns2-transfer; }; };\n', encoding="utf-8"
    )
    code = cli.main([
        "bind", "secondary-report", "--root-config", str(root), "--json"
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["pairs"][0]["name"] == "dns2"
