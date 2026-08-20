from pathlib import Path

from zonectl import cli


def test_cli_outputs_read_only_impact_report(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.setattr(
        cli.ToolkitConfig,
        "load",
        lambda self: type("EmptyConfig", (), {"zones": lambda self: []})(),
    )
    root = tmp_path / "named.conf"
    root.write_text(
        'acl "trusted" { localhost; 192.0.2.0/24; };\n'
        'options { allow-recursion { trusted; }; };\n',
        encoding="utf-8",
    )
    code = cli.main([
        "bind", "access-impact", "trusted",
        "--entry", "localhost", "--root-config", str(root),
    ])
    output = capsys.readouterr().out
    assert code == 0
    assert "RAPORT WPŁYWU ACL/SECONDARY — TYLKO ODCZYT" in output
    assert "Ryzyko:       MEDIUM" in output
    assert "Usuwane:      192.0.2.0/24" in output
    assert "niczego nie zmieniono" in output
