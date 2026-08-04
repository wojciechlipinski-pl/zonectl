from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from zonectl.core.discovery import ZoneConfig
from zonectl.core.dnssec_enable_plan import DnssecEnablePlanner
from zonectl.core.dnssec_enable_transaction import DnssecEnableTransaction


pytestmark = pytest.mark.skipif(
    shutil.which("named-checkzone") is None or shutil.which("named-checkconf") is None,
    reason="Brak narzędzi BIND",
)


def isolated_plan(tmp_path: Path):
    source = tmp_path / "legacy" / "dnssec-test.invalid"
    source.parent.mkdir()
    source.write_text(
        "$TTL 3600\n"
        "@ IN SOA ns1.dnssec-test.invalid. hostmaster.dnssec-test.invalid. (\n"
        "  2026080400 3600 900 1209600 3600 )\n"
        "@ IN NS ns1.dnssec-test.invalid.\n"
        "ns1 IN A 192.0.2.53\n",
        encoding="utf-8",
    )
    declaration = tmp_path / "named.conf.local"
    declaration.write_text(
        'zone "dnssec-test.invalid" {\n'
        "    type primary;\n"
        f'    file "{source}";\n'
        "};\n",
        encoding="utf-8",
    )
    root_config = tmp_path / "named.conf"
    root_config.write_text(
        f'include "{declaration}";\n',
        encoding="utf-8",
    )
    target_directory = tmp_path / "managed"
    target_directory.mkdir()
    zone = ZoneConfig(
        name="dnssec-test.invalid",
        zone_type="primary",
        source_file=source,
        config_file=declaration,
        source_exists=True,
        source_writable=True,
    )
    plan = DnssecEnablePlanner().plan(
        zone,
        key_directory=tmp_path / "keys",
        zone_directory=target_directory,
    )
    transaction = DnssecEnableTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=root_config,
    )
    return plan, transaction, declaration, root_config


def test_real_bind_accepts_dnssec_candidate(tmp_path: Path) -> None:
    plan, transaction, declaration, _root_config = isolated_plan(tmp_path)

    result = transaction.apply(plan, commit=True)

    assert result.status == "COMMIT"
    assert plan.target_zone_file.is_file()
    text = declaration.read_text(encoding="utf-8")
    assert f'file "{plan.target_zone_file}";' in text
    assert "dnssec-policy default;" in text
    assert "inline-signing yes;" in text


def test_real_named_checkconf_failure_rolls_back(tmp_path: Path) -> None:
    plan, transaction, declaration, _root_config = isolated_plan(tmp_path)
    original = declaration.read_bytes()
    broken = replace(
        plan,
        candidate_text=plan.candidate_text.replace(
            "dnssec-policy default;",
            "dnssec-policy ;",
        ),
    )

    result = transaction.apply(broken, commit=True)

    assert result.status == "ROLLED-BACK"
    assert declaration.read_bytes() == original
    assert not plan.target_zone_file.exists()
    assert Path(result.manifest).is_file()
