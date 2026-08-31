from pathlib import Path

from zonectl import cli
from zonectl.core.bind_secondary_plan import BindSecondaryPlanner


class _EmptyConfig:
    def zones(self):
        return []


def test_secondary_plan_cli_is_read_only(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    monkeypatch.setattr(
        BindSecondaryPlanner,
        "_validate_candidate",
        lambda self, source, candidate: (True, "kod 0"),
    )
    root = tmp_path / "named.conf"
    root.write_text(
        "primaries dns2-notify { 192.0.2.53; };\n"
        'zone "a" { type primary; file "/a"; '
        "also-notify { dns2-notify; }; };\n",
        encoding="utf-8",
    )
    before = root.read_bytes()
    code = cli.main(
        [
            "bind",
            "secondary-plan",
            "dns2-notify",
            "--address",
            "192.0.2.60",
            "--root-config",
            str(root),
        ]
    )
    output = capsys.readouterr().out
    assert code == 0
    assert "Strefy (1)" in output
    assert "DRY-RUN" in output
    assert root.read_bytes() == before
