import json
from pathlib import Path

from zonectl import cli


class _EmptyConfig:
    def zones(self):
        return []


def _arguments(tmp_path: Path) -> tuple[list[str], Path]:
    bind = tmp_path / "bind"
    managed = bind / "zonectl-zones.d"
    managed.mkdir(parents=True)
    root = bind / "named.conf"
    local = bind / "named.conf.local"
    index = bind / "zonectl-zones.conf"
    root.write_text('include "named.conf.local";\n', encoding="utf-8")
    local.write_text(
        'include "zonectl-zones.conf";\n'
        'zone "example.pl" { type primary; file "/zones/example.pl"; };\n',
        encoding="utf-8",
    )
    index.write_text("", encoding="utf-8")
    return [
        "--root-config",
        str(root),
        "--local-config",
        str(local),
        "--managed-config",
        str(index),
        "--managed-zone-directory",
        str(managed),
    ], local


def test_migration_inventory_cli_json(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    paths, _ = _arguments(tmp_path)

    code = cli.main(["zone", "migration-inventory", *paths, "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["name"] == "example.pl"
    assert payload[0]["state"] == "LEGACY_PRIMARY"
    assert payload[0]["migratable"] is True


def test_migration_plan_cli_is_read_only(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    paths, local = _arguments(tmp_path)
    before = local.read_bytes()

    code = cli.main(["zone", "migration-plan", "example.pl", *paths])

    output = capsys.readouterr().out
    assert code == 0
    assert "PLAN MIGRACJI STREFY" in output
    assert "Wynik: DRY-RUN" in output
    assert local.read_bytes() == before
    assert not (tmp_path / "bind/zonectl-zones.d/example.pl.conf").exists()


def test_migration_plan_cli_rejects_unknown_zone(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    paths, _ = _arguments(tmp_path)

    code = cli.main(["zone", "migration-plan", "missing.pl", *paths])

    assert code == 2
    assert "Nie znaleziono" in capsys.readouterr().err


def test_migration_apply_cli_dry_run(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    paths, local = _arguments(tmp_path)
    before = local.read_bytes()

    code = cli.main(["zone", "migration-apply", "example.pl", *paths])

    assert code == 0
    assert "Status:     DRY-RUN" in capsys.readouterr().out
    assert local.read_bytes() == before


def test_migration_apply_requires_both_write_flags(
    monkeypatch, tmp_path, capsys
) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: _EmptyConfig())
    paths, _ = _arguments(tmp_path)

    code = cli.main(["zone", "migration-apply", "example.pl", *paths, "--commit"])

    assert code == 2
    assert "--commit i --activate" in capsys.readouterr().err
