from __future__ import annotations

import json
from pathlib import Path

from zonectl import cli
from zonectl.core.discovery import ZoneConfig
from zonectl.core.models import Zone


class FakeConfig:
    toolkit = {}

    def __init__(self, tmp_path: Path):
        zone_file = tmp_path / "example.pl"
        zone_file.write_text("zone\n", encoding="utf-8")
        declaration = tmp_path / "example.conf"
        declaration.write_text(
            'zone "example.pl" {\n'
            "    type primary;\n"
            f'    file "{zone_file}";\n'
            "};\n",
            encoding="utf-8",
        )
        self.zone = Zone("example.pl", zone_file)
        self.discovered = ZoneConfig(
            name="example.pl",
            zone_type="primary",
            source_file=zone_file,
            config_file=declaration,
            source_exists=True,
            source_writable=True,
        )

    def zones(self):
        return [self.zone]

    def discovered_zone(self, name: str):
        if name.rstrip(".").casefold() == "example.pl":
            return self.discovered
        return None


def test_enable_plan_cli_json_has_no_side_effects(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    config = FakeConfig(tmp_path)
    before = config.discovered.config_file.read_bytes()
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: config)

    code = cli.main(["dnssec", "enable-plan", "example.pl", "--json"])

    assert code == 0
    assert config.discovered.config_file.read_bytes() == before
    payload = json.loads(capsys.readouterr().out)
    assert payload["zone"] == "example.pl"
    assert payload["migration_required"] is True
    assert payload["target_zone_file"] == "/var/lib/bind/Primary/example.pl"
    assert "dnssec-policy default;" in payload["candidate_text"]
    assert payload["actions"][-1] == "nie publikuj ani nie usuwaj DS automatycznie"


def test_enable_plan_cli_rejects_rpz(monkeypatch, capsys, tmp_path: Path) -> None:
    config = FakeConfig(tmp_path)
    config.zone.health_profile = "rpz"
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: config)

    code = cli.main(["dnssec", "enable-plan", "example.pl"])

    assert code == 2
    assert "RPZ" in capsys.readouterr().err
