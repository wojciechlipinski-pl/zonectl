from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from zonectl import cli
from zonectl.core.discovery import ZoneConfig
from zonectl.core.models import Zone


class FakeConfig:
    def __init__(self, discovered: ZoneConfig | None) -> None:
        self.discovered = discovered
        self.toolkit = {}

    def zones(self):
        return [Zone("example.pl", Path("/zones/example.pl"))]

    def discovered_zone(self, name: str):
        return self.discovered


class FakeReport:
    def __init__(self, **kwargs):
        pass

    def collect(self, zone, key_directory):
        return SimpleNamespace(to_dict=lambda: {"status": "PASS"})


class FakeCheck:
    def __init__(self, **kwargs):
        pass

    def collect(self, zone, resolvers):
        return SimpleNamespace(to_dict=lambda: {"status": "PASS"})


def discovered_zone(tmp_path: Path) -> ZoneConfig:
    zone_file = tmp_path / "example.pl"
    zone_file.write_text("zone data\n")
    keys = tmp_path / "keys"
    keys.mkdir()
    declaration = tmp_path / "zones.conf"
    declaration.write_text(
        'zone "example.pl" {\n'
        "    type primary;\n"
        f'    file "{zone_file}";\n'
        "    dnssec-policy default;\n"
        "    inline-signing yes;\n"
        f'    key-directory "{keys}";\n'
        "};\n",
        encoding="utf-8",
    )
    return ZoneConfig(
        "example.pl",
        "primary",
        zone_file,
        declaration,
        dnssec_policy="default",
        inline_signing=True,
        key_directory=keys,
        source_exists=True,
    )


def add_test_keys(zone: ZoneConfig) -> None:
    assert zone.key_directory is not None
    for suffix in ("key", "private", "state"):
        (zone.key_directory / f"Kexample.pl.+013+1.{suffix}").write_text(suffix)


def test_disable_plan_cli_prints_ordered_safety_gates(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    config = FakeConfig(discovered_zone(tmp_path))
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: config)

    code = cli.main(["dnssec", "disable-plan", "example.pl"])
    output = capsys.readouterr().out

    assert code == 0
    assert "BEZ ZMIAN W SYSTEMIE" in output
    assert "usuń DS u rejestratora" in output
    assert "withdrawn" in output
    assert "dopiero po wycofaniu DS" in output
    assert config.discovered.config_file.read_text().count("dnssec-policy") == 1


def test_disable_plan_cli_outputs_json(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli.ToolkitConfig,
        "load",
        lambda self: FakeConfig(discovered_zone(tmp_path)),
    )

    code = cli.main(["dnssec", "disable-plan", "example.pl", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["zone"] == "example.pl"
    assert "dnssec-policy" not in payload["candidate_text"]


def test_disable_plan_cli_rejects_missing_discovery(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli.ToolkitConfig,
        "load",
        lambda self: FakeConfig(None),
    )

    code = cli.main(["dnssec", "disable-plan", "example.pl"])

    assert code == 2
    assert "autodetekcji" in capsys.readouterr().err


def test_withdrawal_backup_cli_defaults_to_dry_run(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    config = FakeConfig(discovered_zone(tmp_path))
    add_test_keys(config.discovered)
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: config)
    monkeypatch.setattr(cli, "DnssecReporter", FakeReport)
    monkeypatch.setattr(cli, "DnssecDsChecker", FakeCheck)
    backup_root = tmp_path / "backups"

    code = cli.main(
        [
            "dnssec",
            "withdrawal-backup",
            "example.pl",
            "--backup-root",
            str(backup_root),
        ]
    )

    assert code == 0
    assert "DRY-RUN" in capsys.readouterr().out
    assert not backup_root.exists()


def test_withdrawal_backup_cli_creates_package_only_with_commit(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    config = FakeConfig(discovered_zone(tmp_path))
    add_test_keys(config.discovered)
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: config)
    monkeypatch.setattr(cli, "DnssecReporter", FakeReport)
    monkeypatch.setattr(cli, "DnssecDsChecker", FakeCheck)
    backup_root = tmp_path / "backups"

    code = cli.main(
        [
            "dnssec",
            "withdrawal-backup",
            "example.pl",
            "--backup-root",
            str(backup_root),
            "--commit",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["status"] == "BACKUP-CREATED"
    assert Path(payload["manifest"]).is_file()
