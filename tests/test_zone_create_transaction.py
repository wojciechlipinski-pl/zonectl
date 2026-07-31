from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from zonectl.core.zone_create_transaction import (
    ZoneCreateStep,
    ZoneCreateTransaction,
)
from zonectl.core.zone_lifecycle import (
    ZoneCreateRequest,
    ZoneLifecyclePlanner,
)


def plan(tmp_path: Path):
    return ZoneLifecyclePlanner(
        [],
        today_provider=lambda: date(2026, 7, 31),
    ).plan_create(
        ZoneCreateRequest(
            name="example.pl",
            primary_ns="ns1.elkman.pl.",
            admin="hostmaster.elkman.pl.",
            nameservers=("ns1.elkman.pl.",),
            zone_directory=tmp_path / "zones",
            managed_config=tmp_path / "bind" / "zones.conf",
            managed_zone_directory=tmp_path / "bind" / "zones.d",
        )
    )


def valid_zone(_name: str, _path: Path) -> ZoneCreateStep:
    return ZoneCreateStep("named-checkzone", True, "OK")


def valid_config(_path: Path) -> ZoneCreateStep:
    return ZoneCreateStep("named-checkconf", True, "OK")


def transaction(tmp_path: Path, zone=valid_zone, config=valid_config):
    return ZoneCreateTransaction(
        tmp_path / "manifests",
        zone_validator=zone,
        config_validator=config,
    )


def test_dry_run_has_no_side_effects(tmp_path: Path) -> None:
    candidate = plan(tmp_path)
    result = transaction(tmp_path).apply(candidate)

    assert result.status == "DRY-RUN"
    assert result.ok is True
    assert not candidate.zone_file.exists()
    assert not candidate.managed_config.exists()
    assert not (tmp_path / "manifests").exists()


def test_commit_creates_files_and_manifest(tmp_path: Path) -> None:
    candidate = plan(tmp_path)
    result = transaction(tmp_path).apply(candidate, commit=True)

    assert result.status == "COMMIT"
    assert result.committed is True
    assert candidate.zone_file.read_text() == candidate.zone_text
    assert (
        candidate.zone_declaration_file.read_text()
        == candidate.bind_declaration
    )
    assert (
        f'include "{candidate.zone_declaration_file}";'
        in candidate.managed_config.read_text()
    )
    manifest = Path(result.manifest or "")
    assert manifest.is_file()
    assert json.loads(manifest.read_text())["status"] == "COMMIT"


def test_existing_managed_config_is_preserved(tmp_path: Path) -> None:
    candidate = plan(tmp_path)
    candidate.managed_config.parent.mkdir(parents=True)
    candidate.managed_config.write_text("// existing\n")

    result = transaction(tmp_path).apply(candidate, commit=True)

    assert result.committed is True
    assert candidate.managed_config.read_text().startswith("// existing\n")


def test_zone_validation_failure_rolls_back_both_files(
    tmp_path: Path,
) -> None:
    candidate = plan(tmp_path)
    candidate.managed_config.parent.mkdir(parents=True)
    candidate.managed_config.write_text("// original\n")

    def invalid(_name: str, _path: Path) -> ZoneCreateStep:
        return ZoneCreateStep("named-checkzone", False, "syntax error")

    result = transaction(tmp_path, zone=invalid).apply(
        candidate,
        commit=True,
    )

    assert result.status == "ROLLED-BACK"
    assert result.rolled_back is True
    assert not candidate.zone_file.exists()
    assert not candidate.zone_declaration_file.exists()
    assert candidate.managed_config.read_text() == "// original\n"


def test_config_validation_failure_removes_new_files(
    tmp_path: Path,
) -> None:
    candidate = plan(tmp_path)

    def invalid(_path: Path) -> ZoneCreateStep:
        return ZoneCreateStep("named-checkconf", False, "bad config")

    result = transaction(tmp_path, config=invalid).apply(
        candidate,
        commit=True,
    )

    assert result.status == "ROLLED-BACK"
    assert not candidate.zone_file.exists()
    assert not candidate.zone_declaration_file.exists()
    assert not candidate.managed_config.exists()


def test_existing_zone_file_is_never_overwritten(tmp_path: Path) -> None:
    candidate = plan(tmp_path)
    candidate.zone_file.parent.mkdir(parents=True)
    candidate.zone_file.write_text("keep me\n")

    result = transaction(tmp_path).apply(candidate, commit=True)

    assert result.status == "CONFLICT"
    assert candidate.zone_file.read_text() == "keep me\n"


def test_activation_and_loaded_verification_are_explicit(
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def activate(name: str) -> ZoneCreateStep:
        calls.append(f"activate:{name}")
        return ZoneCreateStep("rndc-reconfig", True, "OK")

    def verify(name: str) -> ZoneCreateStep:
        calls.append(f"verify:{name}")
        return ZoneCreateStep("rndc-zonestatus", True, "OK")

    candidate = plan(tmp_path)
    engine = ZoneCreateTransaction(
        tmp_path / "manifests",
        zone_validator=valid_zone,
        config_validator=valid_config,
        activator=activate,
        loaded_verifier=verify,
    )
    result = engine.apply(candidate, commit=True, activate=True)
    assert result.status == "COMMIT"
    assert calls == ["activate:example.pl", "verify:example.pl"]


def test_failed_loaded_verification_rolls_back_and_reconfigures(
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def activate(name: str) -> ZoneCreateStep:
        calls.append(f"activate:{name}")
        return ZoneCreateStep("rndc-reconfig", True, "OK")

    def verify(name: str) -> ZoneCreateStep:
        calls.append(f"verify:{name}")
        return ZoneCreateStep("rndc-zonestatus", False, "not loaded")

    candidate = plan(tmp_path)
    engine = ZoneCreateTransaction(
        tmp_path / "manifests",
        zone_validator=valid_zone,
        config_validator=valid_config,
        activator=activate,
        loaded_verifier=verify,
    )
    result = engine.apply(candidate, commit=True, activate=True)
    assert result.status == "ROLLED-BACK"
    assert calls == [
        "activate:example.pl",
        "verify:example.pl",
        "activate:example.pl",
    ]
    assert not candidate.zone_file.exists()
    assert not candidate.zone_declaration_file.exists()
