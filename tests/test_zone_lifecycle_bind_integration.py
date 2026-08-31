from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from zonectl.core.zone_disable_transaction import (
    ZoneDisableStep,
    ZoneDisableTransaction,
)
from zonectl.core.zone_quarantine_restore import (
    QuarantineRestoreStep,
    QuarantineRestoreTransaction,
)
from zonectl.core.zone_restore_transaction import (
    ZoneRestoreStep,
    ZoneRestoreTransaction,
)


pytestmark = pytest.mark.skipif(
    not (shutil.which("named-checkzone") and shutil.which("named-checkconf")),
    reason="Brak narzędzi walidacyjnych BIND",
)


ZONE_TEXT = """$TTL 3600
@ IN SOA ns1.example.invalid. hostmaster.example.invalid. (
  2026073100 3600 900 1209600 3600 )
@ IN NS ns1.example.invalid.
ns1 IN A 192.0.2.53
"""


def isolated_bind(tmp_path: Path):
    bind = tmp_path / "bind"
    declarations = bind / "zones.d"
    zones = tmp_path / "zones"
    declarations.mkdir(parents=True)
    zones.mkdir()
    zone = zones / "example.invalid"
    declaration = declarations / "example.invalid.conf"
    index = bind / "zones.conf"
    root = bind / "named.conf"
    zone.write_text(ZONE_TEXT, encoding="utf-8")
    declaration.write_text(
        f'zone "example.invalid" IN {{\n    type primary;\n    file "{zone}";\n}};\n',
        encoding="utf-8",
    )
    index.write_text(f'include "{declaration}";\n', encoding="utf-8")
    root.write_text(f'include "{index}";\n', encoding="utf-8")
    return zone, declaration, index, root


def test_disable_uses_real_named_checkconf_without_contacting_rndc(
    tmp_path: Path,
) -> None:
    zone, declaration, index, root = isolated_bind(tmp_path)
    plan = ZoneDisableTransaction.plan(
        "example.invalid",
        zone_file=zone,
        declaration_file=declaration,
        managed_index=index,
        root_config=root,
        disabled_root=tmp_path / "disabled",
        reason="integration test",
    )
    transaction = ZoneDisableTransaction(
        tmp_path / "manifests",
        activator=lambda name: ZoneDisableStep("rndc-reconfig", True, "isolated"),
        unavailable_verifier=lambda name: ZoneDisableStep(
            "rndc-zone-unavailable", True, "isolated"
        ),
    )

    result = transaction.apply(plan, commit=True)

    assert result.status == "DISABLED"
    assert any(step.name == "named-checkconf" and step.ok for step in result.steps)
    assert zone.is_file() and not declaration.exists()


def test_restore_uses_real_bind_validators_without_contacting_rndc(
    tmp_path: Path,
) -> None:
    zone, declaration, index, root = isolated_bind(tmp_path)
    archived = tmp_path / "disabled/example.invalid/example.invalid.conf"
    archived.parent.mkdir(parents=True)
    declaration.replace(archived)
    index.write_text("# disabled\n", encoding="utf-8")
    plan = ZoneRestoreTransaction.plan(
        "example.invalid",
        zone_file=zone,
        declaration_file=declaration,
        managed_index=index,
        disabled_root=tmp_path / "disabled",
        root_config=root,
    )
    transaction = ZoneRestoreTransaction(
        tmp_path / "manifests",
        activator=lambda name: ZoneRestoreStep("rndc-reconfig", True, "isolated"),
        loaded_verifier=lambda name: ZoneRestoreStep(
            "rndc-zonestatus", True, "isolated"
        ),
    )

    result = transaction.apply(plan, commit=True)

    assert result.status == "RESTORED"
    assert any(step.name == "named-checkzone" and step.ok for step in result.steps)
    assert any(step.name == "named-checkconf" and step.ok for step in result.steps)
    assert declaration.is_file() and not archived.exists()


def test_quarantine_restore_uses_real_bind_validators(
    tmp_path: Path,
) -> None:
    zone, declaration, index, root = isolated_bind(tmp_path)
    package = tmp_path / "quarantine/example.invalid/tx"
    package.mkdir(parents=True)
    zone.replace(package / "zone.db")
    declaration.replace(package / "zone.conf")
    index.write_text("# quarantined\n", encoding="utf-8")
    files = {
        name: hashlib.sha256((package / name).read_bytes()).hexdigest()
        for name in ("zone.db", "zone.conf")
    }
    (package / "manifest.json").write_text(
        json.dumps(
            {"zone": "example.invalid", "status": "QUARANTINED", "files": files}
        ),
        encoding="utf-8",
    )
    plan = QuarantineRestoreTransaction.plan(
        "example.invalid",
        package_directory=package,
        zone_file=zone,
        active_declaration=declaration,
        managed_index=index,
        root_config=root,
    )
    transaction = QuarantineRestoreTransaction(
        activator=lambda name: QuarantineRestoreStep("rndc-reconfig", True, "isolated"),
        loaded_verifier=lambda name: QuarantineRestoreStep(
            "rndc-zonestatus", True, "isolated"
        ),
    )

    result = transaction.apply(plan, commit=True)

    assert result.status == "RESTORED"
    assert any(step.name == "named-checkzone" and step.ok for step in result.steps)
    assert any(step.name == "named-checkconf" and step.ok for step in result.steps)
    assert zone.is_file() and declaration.is_file() and package.is_dir()
