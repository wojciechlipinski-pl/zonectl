from pathlib import Path

from zonectl import cli
from zonectl.core.bind_acl_plan import BindAclPlanner


class _EmptyConfig:
    def zones(self):
        return []


def test_acl_plan_cli_is_read_only(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    monkeypatch.setattr(
        BindAclPlanner,
        "_validate_candidate",
        lambda self, source, candidate: (True, "kod 0"),
    )
    root = tmp_path / "named.conf"
    root.write_text(
        'acl "trusted" { 192.168.200/24; };\n', encoding="utf-8"
    )
    before = root.read_bytes()
    code = cli.main([
        "bind", "acl-plan", "trusted", "--root-config", str(root),
        "--replace", "192.168.200/24=192.168.200.0/24",
    ])
    output = capsys.readouterr().out
    assert code == 0
    assert "192.168.200.0/24" in output
    assert "DRY-RUN" in output
    assert root.read_bytes() == before


def test_acl_plan_accepts_full_entry_list(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    root = tmp_path / "named.conf"
    root.write_text(
        'acl "trusted" {\n  localhost;\n  192.0.2.0/24;\n};\n'
        'options { allow-query { trusted; }; };\n', encoding="utf-8"
    )
    monkeypatch.setattr(
        BindAclPlanner, "_validate_candidate",
        lambda self, source, candidate: (True, "kod 0"),
    )
    code = cli.main([
        "bind", "acl-plan", "trusted", "--entry", "localhost",
        "--entry", "198.51.100.0/24", "--root-config", str(root),
    ])
    assert code == 0
    assert "198.51.100.0/24" in capsys.readouterr().out
