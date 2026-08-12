from pathlib import Path

from zonectl import cli
from zonectl.core.bind_acl_plan import BindAclPlanner


class _EmptyConfig:
    def zones(self):
        return []


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "named.conf"
    root.write_text(
        'acl "trusted" { 192.168.200/24; };\n', encoding="utf-8"
    )
    return root


def test_acl_apply_cli_dry_run(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    monkeypatch.setattr(
        BindAclPlanner, "_validate_candidate",
        lambda self, source, candidate: (True, "kod 0"),
    )
    root = _root(tmp_path)
    before = root.read_bytes()
    code = cli.main([
        "bind", "acl-apply", "trusted", "--root-config", str(root),
        "--replace", "192.168.200/24=192.168.200.0/24",
    ])
    assert code == 0
    assert "Status:      DRY-RUN" in capsys.readouterr().out
    assert root.read_bytes() == before


def test_acl_apply_requires_both_flags(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    code = cli.main([
        "bind", "acl-apply", "trusted", "--root-config", str(_root(tmp_path)),
        "--commit",
    ])
    assert code == 2
    assert "--commit i --activate" in capsys.readouterr().err


def test_acl_apply_full_entry_list_is_dry_run(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    monkeypatch.setattr(
        BindAclPlanner, "_validate_candidate",
        lambda self, source, candidate: (True, "kod 0"),
    )
    root = tmp_path / "named.conf"
    root.write_text(
        'acl "trusted" {\n  localhost;\n  192.0.2.0/24;\n};\n',
        encoding="utf-8",
    )
    before = root.read_bytes()
    code = cli.main([
        "bind", "acl-apply", "trusted", "--entry", "localhost",
        "--entry", "198.51.100.0/24", "--root-config", str(root),
    ])
    assert code == 0
    assert "DRY-RUN" in capsys.readouterr().out
    assert root.read_bytes() == before


def test_acl_apply_requires_exact_confirmation(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    code = cli.main([
        "bind", "acl-apply", "trusted", "--root-config", str(_root(tmp_path)),
        "--commit", "--activate", "--confirm", "wrong",
    ])
    assert code == 2
    assert "pełnej nazwie ACL" in capsys.readouterr().err
