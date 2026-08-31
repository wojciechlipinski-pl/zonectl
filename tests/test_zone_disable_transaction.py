from pathlib import Path

import pytest

from zonectl.core.zone_disable_transaction import (
    ZoneDisableError,
    ZoneDisableStep,
    ZoneDisableTransaction,
)


def setup(tmp_path: Path):
    zone = tmp_path / "zones/example.invalid"
    declaration = tmp_path / "bind/zones.d/example.invalid.conf"
    index = tmp_path / "bind/zones.conf"
    zone.parent.mkdir(parents=True)
    declaration.parent.mkdir(parents=True)
    zone.write_text("zone data\n")
    declaration.write_text('zone "example.invalid" { type primary; };\n')
    index.write_text(f'# keep\ninclude "{declaration}";\n')
    plan = ZoneDisableTransaction.plan(
        "example.invalid",
        zone_file=zone,
        declaration_file=declaration,
        managed_index=index,
        root_config=tmp_path / "bind/named.conf",
        disabled_root=tmp_path / "disabled",
        reason="test",
    )
    return zone, declaration, index, plan


def ok(name: str) -> ZoneDisableStep:
    return ZoneDisableStep(name, True, "OK")


def engine(tmp_path: Path, *, unavailable=None):
    return ZoneDisableTransaction(
        tmp_path / "manifests",
        config_validator=lambda path: ok("named-checkconf"),
        activator=lambda name: ok("rndc-reconfig"),
        unavailable_verifier=unavailable or (lambda name: ok("rndc-zone-unavailable")),
    )


def test_dry_run_has_no_side_effects(tmp_path: Path) -> None:
    zone, declaration, index, plan = setup(tmp_path)
    original = index.read_text()
    result = engine(tmp_path).apply(plan)
    assert result.status == "DRY-RUN"
    assert zone.exists() and declaration.exists()
    assert index.read_text() == original


def test_disable_archives_declaration_and_preserves_zone(tmp_path: Path) -> None:
    zone, declaration, index, plan = setup(tmp_path)
    result = engine(tmp_path).apply(plan, commit=True)
    assert result.status == "DISABLED"
    assert zone.read_text() == "zone data\n"
    assert not declaration.exists()
    assert plan.archived_declaration.is_file()
    assert "example.invalid" not in index.read_text()
    assert Path(result.manifest).is_file()


def test_failed_verification_restores_active_configuration(tmp_path: Path) -> None:
    zone, declaration, index, plan = setup(tmp_path)
    original = index.read_bytes()
    calls = []

    def activate(name: str) -> ZoneDisableStep:
        calls.append(name)
        return ok("rndc-reconfig")

    transaction = ZoneDisableTransaction(
        tmp_path / "manifests",
        config_validator=lambda path: ok("named-checkconf"),
        activator=activate,
        unavailable_verifier=lambda name: ZoneDisableStep(
            "rndc-zone-unavailable", False, "still loaded"
        ),
    )
    result = transaction.apply(plan, commit=True)
    assert result.status == "ROLLED-BACK"
    assert declaration.exists()
    assert index.read_bytes() == original
    assert not plan.archived_declaration.exists()
    assert calls == ["example.invalid", "example.invalid"]


def test_missing_or_duplicate_include_is_rejected(tmp_path: Path) -> None:
    zone, declaration, index, plan = setup(tmp_path)
    index.write_text("# empty\n")
    with pytest.raises(ZoneDisableError, match="znaleziono: 0"):
        ZoneDisableTransaction.plan(
            "example.invalid",
            zone_file=zone,
            declaration_file=declaration,
            managed_index=index,
            reason="test",
        )
