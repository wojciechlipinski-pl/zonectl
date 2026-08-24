from __future__ import annotations

import shutil
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from zonectl.core.zone_create_transaction import ZoneCreateTransaction
from zonectl.core.zone_lifecycle import (
    ZoneCreateRequest,
    ZoneLifecyclePlanner,
)


pytestmark = pytest.mark.skipif(
    not (
        shutil.which("named-checkzone")
        and shutil.which("named-checkconf")
    ),
    reason="Brak narzędzi walidacyjnych BIND",
)


def plan(tmp_path: Path):
    return ZoneLifecyclePlanner(
        [],
        today_provider=lambda: date(2026, 7, 31),
    ).plan_create(
        ZoneCreateRequest(
            name="integration.example",
            primary_ns="ns1.example.pl.",
            admin="hostmaster.example.pl.",
            nameservers=(
                "ns1.example.pl.",
                "ns2.example.pl.",
            ),
            zone_directory=tmp_path / "zones",
            managed_config=tmp_path / "bind" / "zones.conf",
            managed_zone_directory=tmp_path / "bind" / "zones.d",
            apex_ipv4="192.0.2.44",
        )
    )


def test_real_bind_tools_accept_generated_zone(
    tmp_path: Path,
) -> None:
    candidate = plan(tmp_path)
    root_config = tmp_path / "bind" / "named.conf"
    root_config.parent.mkdir(parents=True, exist_ok=True)
    root_config.write_text(
        f'include "{candidate.managed_config}";\n',
        encoding="utf-8",
    )

    result = ZoneCreateTransaction(
        tmp_path / "manifests",
        root_config=root_config,
    ).apply(candidate, commit=True)

    assert result.status == "COMMIT"
    assert result.committed is True
    assert [step.name for step in result.steps] == [
        "zone-file",
        "zone-declaration",
        "managed-config",
        "named-checkzone",
        "named-checkconf",
    ]
    assert candidate.zone_file.is_file()
    assert candidate.managed_config.is_file()
    assert candidate.zone_declaration_file.is_file()


def test_real_named_checkzone_failure_rolls_back(
    tmp_path: Path,
) -> None:
    candidate = plan(tmp_path)
    broken = replace(
        candidate,
        zone_text=candidate.zone_text
        + "broken IN A 999.999.999.999\n",
    )

    result = ZoneCreateTransaction(
        tmp_path / "manifests"
    ).apply(broken, commit=True)

    assert result.status == "ROLLED-BACK"
    assert result.rolled_back is True
    assert not broken.zone_file.exists()
    assert not broken.managed_config.exists()
    assert not broken.zone_declaration_file.exists()
    assert any(
        step.name == "named-checkzone" and not step.ok
        for step in result.steps
    )


def test_named_checkconf_uses_root_configuration_context(
    tmp_path: Path,
) -> None:
    candidate = plan(tmp_path)
    root_config = tmp_path / "bind" / "named.conf"
    definitions = tmp_path / "bind" / "definitions.conf"
    root_config.parent.mkdir(parents=True, exist_ok=True)
    definitions.write_text(
        'acl "transfer-peers" { 192.0.2.53; };\n',
        encoding="utf-8",
    )
    root_config.write_text(
        f'include "{definitions}";\n'
        f'include "{candidate.managed_config}";\n',
        encoding="utf-8",
    )
    declaration = candidate.bind_declaration.replace(
        "};\n",
        "    allow-transfer { transfer-peers; };\n};\n",
    )
    candidate = replace(candidate, bind_declaration=declaration)

    result = ZoneCreateTransaction(
        tmp_path / "manifests",
        root_config=root_config,
    ).apply(candidate, commit=True)

    assert result.status == "COMMIT"
    assert next(
        step for step in result.steps if step.name == "named-checkconf"
    ).ok is True
