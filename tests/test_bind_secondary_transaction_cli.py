from pathlib import Path

from zonectl import cli
from zonectl.core.bind_secondary_plan import BindSecondaryPlanner


class _EmptyConfig:
    def zones(self):
        return []


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "named.conf"
    root.write_text(
        'primaries dns2-notify { 192.0.2.53; };\n'
        'zone "a" { type primary; file "/a"; also-notify { dns2-notify; }; };\n',
        encoding="utf-8",
    )
    return root


def test_secondary_apply_dry_run(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    monkeypatch.setattr(
        BindSecondaryPlanner, "_validate_candidate",
        lambda self, source, candidate: (True, "kod 0"),
    )
    root = _root(tmp_path)
    before = root.read_bytes()
    code = cli.main([
        "bind", "secondary-apply", "dns2-notify", "--address", "192.0.2.53",
        "--root-config", str(root),
    ])
    assert code == 0
    assert "Status:      DRY-RUN" in capsys.readouterr().out
    assert root.read_bytes() == before


def test_secondary_apply_requires_both_flags(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    code = cli.main([
        "bind", "secondary-apply", "dns2-notify", "--address", "192.0.2.53",
        "--root-config", str(_root(tmp_path)), "--commit",
    ])
    assert code == 2
    assert "--commit i --activate" in capsys.readouterr().err


def test_secondary_apply_requires_exact_confirmation(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    code = cli.main([
        "bind", "secondary-apply", "dns2-notify", "--address", "192.0.2.53",
        "--root-config", str(_root(tmp_path)), "--commit", "--activate",
        "--confirm", "wrong",
    ])
    assert code == 2
    assert "pełnej nazwie grupy" in capsys.readouterr().err


def test_secondary_apply_commit_requires_reason(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())

    code = cli.main([
        "bind", "secondary-apply", "dns2-notify",
        "--address", "192.0.2.53", "--root-config", str(_root(tmp_path)),
        "--commit", "--activate", "--confirm", "dns2-notify",
    ])

    assert code == 2
    assert "--reason" in capsys.readouterr().err
