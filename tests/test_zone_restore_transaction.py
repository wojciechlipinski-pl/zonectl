from pathlib import Path

import pytest

from zonectl.core.zone_restore_transaction import (
    ZoneRestoreError,
    ZoneRestoreStep,
    ZoneRestoreTransaction,
)


def setup(tmp_path: Path):
    zone = tmp_path / "zones/example.invalid"
    declaration = tmp_path / "bind/zones.d/example.invalid.conf"
    archived = tmp_path / "disabled/example.invalid/example.invalid.conf"
    index = tmp_path / "bind/zones.conf"
    zone.parent.mkdir(parents=True)
    declaration.parent.mkdir(parents=True)
    archived.parent.mkdir(parents=True)
    zone.write_text("zone data\n")
    archived.write_text('zone "example.invalid" { type primary; };\n')
    index.write_text("# keep\n")
    plan = ZoneRestoreTransaction.plan(
        "example.invalid",
        zone_file=zone,
        declaration_file=declaration,
        managed_index=index,
        disabled_root=tmp_path / "disabled",
        root_config=tmp_path / "bind/named.conf",
    )
    return zone, declaration, archived, index, plan


def ok(name: str) -> ZoneRestoreStep:
    return ZoneRestoreStep(name, True, "OK")


def engine(tmp_path: Path, loaded=None):
    return ZoneRestoreTransaction(
        tmp_path / "manifests",
        zone_validator=lambda name, path: ok("named-checkzone"),
        config_validator=lambda path: ok("named-checkconf"),
        activator=lambda name: ok("rndc-reconfig"),
        loaded_verifier=loaded or (lambda name: ok("rndc-zonestatus")),
    )


def test_dry_run_has_no_side_effects(tmp_path: Path) -> None:
    zone, declaration, archived, index, plan = setup(tmp_path)
    result = engine(tmp_path).apply(plan)
    assert result.status == "DRY-RUN"
    assert archived.exists() and not declaration.exists()
    assert "example.invalid" not in index.read_text()


def test_restore_activates_zone_and_consumes_archive(tmp_path: Path) -> None:
    zone, declaration, archived, index, plan = setup(tmp_path)
    result = engine(tmp_path).apply(plan, commit=True)
    assert result.status == "RESTORED"
    assert declaration.is_file()
    assert not archived.exists()
    assert f'include "{declaration}";' in index.read_text()
    assert zone.read_text() == "zone data\n"
    assert Path(result.manifest).is_file()


def test_failed_loaded_check_restores_disabled_state(tmp_path: Path) -> None:
    zone, declaration, archived, index, plan = setup(tmp_path)
    original = index.read_bytes()
    result = engine(
        tmp_path,
        loaded=lambda name: ZoneRestoreStep(
            "rndc-zonestatus", False, "not loaded"
        ),
    ).apply(plan, commit=True)
    assert result.status == "ROLLED-BACK"
    assert archived.exists() and not declaration.exists()
    assert index.read_bytes() == original


def test_missing_archive_or_existing_declaration_is_rejected(
    tmp_path: Path,
) -> None:
    zone, declaration, archived, index, plan = setup(tmp_path)
    archived.unlink()
    with pytest.raises(ZoneRestoreError, match="Brak archiwalnej"):
        ZoneRestoreTransaction.plan(
            "example.invalid",
            zone_file=zone,
            declaration_file=declaration,
            managed_index=index,
            disabled_root=tmp_path / "disabled",
        )
