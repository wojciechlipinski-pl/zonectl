from __future__ import annotations

import json
from pathlib import Path

from zonectl import cli
from zonectl.core.discovery import ZoneConfig
from zonectl.core.dnssec_enable_transaction import (
    DnssecEnableResult,
    DnssecEnableStep,
)
from zonectl.core.models import Zone


class FakeConfig:
    toolkit = {}

    def __init__(self, tmp_path: Path):
        source = tmp_path / "example.pl"
        source.write_text("zone\n")
        declaration = tmp_path / "named.conf.local"
        declaration.write_text(
            'zone "example.pl" {\n'
            "    type primary;\n"
            f'    file "{source}";\n'
            "};\n"
        )
        self.zone = Zone("example.pl", source)
        self.discovered = ZoneConfig(
            name="example.pl",
            zone_type="primary",
            source_file=source,
            config_file=declaration,
            source_exists=True,
            source_writable=True,
        )

    def zones(self):
        return [self.zone]

    def discovered_zone(self, _name: str):
        return self.discovered


class FakeTransaction:
    calls = []

    def __init__(self, backup_root, manifest_directory, *, root_config):
        self.calls.append((backup_root, manifest_directory, root_config))

    def apply(self, _plan, *, commit, activate):
        self.calls.append((commit, activate))
        return DnssecEnableResult(
            "tx-test",
            "example.pl",
            "COMMIT" if commit else "DRY-RUN",
            committed=commit,
            steps=[DnssecEnableStep("dry-run", True, "OK")],
        )


def configure(monkeypatch, tmp_path: Path):
    config = FakeConfig(tmp_path)
    FakeTransaction.calls = []
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: config)
    monkeypatch.setattr(cli, "DnssecEnableTransaction", FakeTransaction)
    return config


def test_enable_defaults_to_dry_run(monkeypatch, capsys, tmp_path: Path) -> None:
    config = configure(monkeypatch, tmp_path)
    before = config.discovered.config_file.read_bytes()

    code = cli.main(["dnssec", "enable", "example.pl", "--json"])

    assert code == 0
    assert config.discovered.config_file.read_bytes() == before
    assert FakeTransaction.calls[-1] == (False, False)
    assert json.loads(capsys.readouterr().out)["status"] == "DRY-RUN"


def test_enable_requires_both_commit_and_activate(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    configure(monkeypatch, tmp_path)

    assert cli.main(["dnssec", "enable", "example.pl", "--commit"]) == 2
    assert cli.main(["dnssec", "enable", "example.pl", "--activate"]) == 2
    assert "--commit i --activate" in capsys.readouterr().err
    assert FakeTransaction.calls == []


def test_enable_passes_explicit_double_confirmation(
    monkeypatch, tmp_path: Path
) -> None:
    configure(monkeypatch, tmp_path)

    code = cli.main(
        ["dnssec", "enable", "example.pl", "--commit", "--activate"]
    )

    assert code == 0
    assert FakeTransaction.calls[-1] == (True, True)
