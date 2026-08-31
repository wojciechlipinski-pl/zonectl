from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from zonectl.core.discovery import BindConfigDiscovery, ZoneConfig
from zonectl.core.dnssec_enable_plan import DnssecEnablePlanError, DnssecEnablePlanner
from zonectl.core.models import Zone
from zonectl.core.zone_lifecycle import ZoneLifecycleError, ZoneLifecyclePlanner


pytestmark = pytest.mark.skipif(
    shutil.which("named-checkzone") is None or shutil.which("named-checkconf") is None,
    reason="Brak narzędzi BIND",
)


def isolated_inline_zone(
    tmp_path: Path,
    *,
    inline_value: str,
) -> tuple[Path, Path, Path]:
    """Create an isolated inline-signing zone and its BIND configuration."""
    zone_file = tmp_path / "inline.example"
    zone_file.write_text(
        "$TTL 3600\n"
        "@ IN SOA ns1.inline.example. hostmaster.inline.example. (\n"
        "  2026083101 3600 900 1209600 3600 )\n"
        "@ IN NS ns1.inline.example.\n"
        "ns1 IN A 192.0.2.53\n",
        encoding="utf-8",
    )
    key_directory = tmp_path / "keys"
    key_directory.mkdir()
    declaration = tmp_path / "named.conf.local"
    declaration.write_text(
        'zone "inline.example" {\n'
        "    type primary;\n"
        f'    file "{zone_file}";\n'
        "    dnssec-policy default;\n"
        f"    inline-signing {inline_value};\n"
        f'    key-directory "{key_directory}";\n'
        "};\n",
        encoding="utf-8",
    )
    root_config = tmp_path / "named.conf"
    root_config.write_text(f'include "{declaration}";\n', encoding="utf-8")
    return root_config, declaration, zone_file


def run_validator(*command: str) -> subprocess.CompletedProcess[str]:
    """Run a local BIND validator without contacting a running name server."""
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )


@pytest.mark.parametrize(
    ("inline_value", "expected_inline", "expected_valid"),
    (("yes", True, True), ("no", False, False)),
)
def test_real_bind_validation_and_discovery_cover_inline_signing_values(
    tmp_path: Path,
    inline_value: str,
    expected_inline: bool,
    expected_valid: bool,
) -> None:
    root_config, _declaration, zone_file = isolated_inline_zone(
        tmp_path,
        inline_value=inline_value,
    )

    zone_check = run_validator(
        "named-checkzone",
        "inline.example",
        str(zone_file),
    )
    config_check = run_validator("named-checkconf", str(root_config))

    assert zone_check.returncode == 0, zone_check.stderr
    assert (config_check.returncode == 0) is expected_valid, config_check.stdout
    zone = BindConfigDiscovery(root_config).discover().zone("inline.example")
    assert zone.dnssec_policy == "default"
    assert zone.inline_signing is expected_inline
    assert zone.dnssec_enabled is True
    assert zone.source_file == zone_file.resolve()


def test_real_bind_rejects_invalid_inline_signing_value(tmp_path: Path) -> None:
    root_config, _declaration, _zone_file = isolated_inline_zone(
        tmp_path,
        inline_value="maybe",
    )

    result = run_validator("named-checkconf", str(root_config))

    assert result.returncode != 0
    diagnostic = result.stdout + result.stderr
    assert "boolean expected" in diagnostic
    assert "maybe" in diagnostic


def test_discovered_inline_zone_is_blocked_from_plain_lifecycle(
    tmp_path: Path,
) -> None:
    root_config, _declaration, _zone_file = isolated_inline_zone(
        tmp_path,
        inline_value="yes",
    )
    discovered = BindConfigDiscovery(root_config).discover().zone("inline.example")
    zone = Zone(
        name=discovered.name,
        file=discovered.source_file,
        dnssec_policy=discovered.dnssec_policy,
        inline_signing=discovered.inline_signing,
        key_directory=discovered.key_directory,
    )

    with pytest.raises(ZoneLifecycleError, match="inline-signing=yes"):
        ZoneLifecyclePlanner.ensure_lifecycle_allowed(
            zone.name,
            [zone],
            "disable",
        )


@pytest.mark.parametrize("inline_value", ("yes", "no"))
def test_enable_plan_rejects_preexisting_inline_directive(
    tmp_path: Path,
    inline_value: str,
) -> None:
    _root_config, declaration, zone_file = isolated_inline_zone(
        tmp_path,
        inline_value=inline_value,
    )
    declaration.write_text(
        declaration.read_text(encoding="utf-8").replace(
            "    dnssec-policy default;\n",
            "",
        ),
        encoding="utf-8",
    )
    zone = ZoneConfig(
        name="inline.example",
        zone_type="primary",
        source_file=zone_file,
        config_file=declaration,
        source_exists=True,
        source_writable=True,
        inline_signing=inline_value == "yes",
    )

    with pytest.raises(DnssecEnablePlanError, match="konfigurację DNSSEC"):
        DnssecEnablePlanner().plan(
            zone,
            key_directory=tmp_path / "new-keys",
            zone_directory=tmp_path,
        )
