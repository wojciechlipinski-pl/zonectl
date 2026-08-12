import json
from pathlib import Path

from zonectl import cli


class _EmptyConfig:
    def zones(self):
        return []


def test_bind_audit_cli_reports_failure(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    root = tmp_path / "named.conf"
    root.write_text(
        'options { allow-transfer { missing; }; };\n', encoding="utf-8"
    )
    code = cli.main(["bind", "audit", "--root-config", str(root)])
    assert code == 1
    assert "UNKNOWN_REFERENCE" in capsys.readouterr().out


def test_bind_audit_cli_json(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    root = tmp_path / "named.conf"
    root.write_text(
        'acl "trusted" { localhost; };\n'
        'options { allow-query { trusted; }; };\n', encoding="utf-8"
    )
    code = cli.main([
        "bind", "audit", "--root-config", str(root), "--json"
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload == {"status": "PASS", "findings": []}
