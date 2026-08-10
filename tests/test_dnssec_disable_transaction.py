from __future__ import annotations

import json
from pathlib import Path

from zonectl.core.discovery import ZoneConfig
from zonectl.core.dnssec_disable_plan import DnssecDisablePlanner
from zonectl.core.dnssec_disable_transaction import (
    DnssecDisableStep,
    DnssecDisableTransaction,
    DsStateReading,
    read_ds_state,
)


def setup_plan(tmp_path: Path):
    source = tmp_path / "var" / "example.pl"
    source.parent.mkdir(parents=True)
    source.write_text("$TTL 3600\n", encoding="utf-8")
    keys = tmp_path / "keys"
    keys.mkdir()
    declaration = tmp_path / "named.conf.local"
    declaration.write_text(
        'zone "example.pl" {\n'
        "    type primary;\n"
        f'    file "{source}";\n'
        "    dnssec-policy default;\n"
        "    inline-signing yes;\n"
        f'    key-directory "{keys}";\n'
        "};\n",
        encoding="utf-8",
    )
    zone = ZoneConfig(
        name="example.pl",
        zone_type="primary",
        source_file=source,
        config_file=declaration,
        source_exists=True,
        source_writable=True,
        dnssec_policy="default",
        inline_signing=True,
        key_directory=keys,
    )
    plan = DnssecDisablePlanner().plan(zone)
    return plan, declaration


def state(value: str | None, message: str = "stub"):
    return lambda _zone: DsStateReading(value, message)


def ok(name: str):
    return lambda *_args: DnssecDisableStep(name, True, "OK")


def engine(tmp_path: Path, **overrides):
    defaults = {
        "state_reader": state("hidden"),
        "config_validator": ok("named-checkconf"),
        "activator": ok("rndc-reconfig"),
        "loaded_verifier": ok("rndc-zonestatus"),
    }
    defaults.update(overrides)
    return DnssecDisableTransaction(
        tmp_path / "backups",
        tmp_path / "manifests",
        root_config=tmp_path / "named.conf",
        **defaults,
    )


def test_dry_run_changes_nothing(tmp_path: Path) -> None:
    plan, declaration = setup_plan(tmp_path)
    before = declaration.read_text(encoding="utf-8")

    result = engine(tmp_path).apply(plan)

    assert result.status == "DRY-RUN"
    assert result.committed is False
    assert declaration.read_text(encoding="utf-8") == before
    assert not (tmp_path / "backups").exists()


def test_blocked_when_kasp_ds_is_not_hidden(tmp_path: Path) -> None:
    plan, declaration = setup_plan(tmp_path)
    before = declaration.read_text(encoding="utf-8")

    result = engine(tmp_path, state_reader=state("omnipresent")).apply(
        plan, commit=True
    )

    assert result.status == "BLOCKED"
    assert result.ds_state == "omnipresent"
    assert result.committed is False
    assert declaration.read_text(encoding="utf-8") == before


def test_non_hidden_state_cannot_be_overridden(tmp_path: Path) -> None:
    plan, declaration = setup_plan(tmp_path)
    before = declaration.read_text(encoding="utf-8")

    result = engine(tmp_path, state_reader=state("unretentive")).apply(
        plan, commit=True, acknowledge_unsigned=True
    )

    assert result.status == "BLOCKED"
    assert declaration.read_text(encoding="utf-8") == before


def test_unreadable_state_blocks_without_acknowledgement(tmp_path: Path) -> None:
    plan, declaration = setup_plan(tmp_path)
    before = declaration.read_text(encoding="utf-8")

    result = engine(tmp_path, state_reader=state(None, "brak rndc")).apply(
        plan, commit=True
    )

    assert result.status == "BLOCKED"
    assert declaration.read_text(encoding="utf-8") == before


def test_unreadable_state_may_be_acknowledged(tmp_path: Path) -> None:
    plan, declaration = setup_plan(tmp_path)

    result = engine(tmp_path, state_reader=state(None, "brak rndc")).apply(
        plan, commit=True, acknowledge_unsigned=True
    )

    assert result.status == "COMMIT"
    assert result.committed is True
    assert "dnssec-policy" not in declaration.read_text(encoding="utf-8")


def test_commit_removes_dnssec_directives_and_keeps_keys(tmp_path: Path) -> None:
    plan, declaration = setup_plan(tmp_path)

    result = engine(tmp_path).apply(plan, commit=True, activate=True)

    assert result.status == "COMMIT"
    assert result.committed is True
    text = declaration.read_text(encoding="utf-8")
    assert "dnssec-policy" not in text
    assert "inline-signing" not in text
    assert "key-directory" not in text
    assert "type primary;" in text
    # Klucze muszą przetrwać — są jedyną drogą powrotu.
    assert list((tmp_path / "keys").parent.glob("keys")) != []
    payload = json.loads(Path(result.manifest).read_text(encoding="utf-8"))
    assert payload["status"] == "COMMIT"


def test_rollback_restores_declaration_when_checkconf_fails(tmp_path: Path) -> None:
    plan, declaration = setup_plan(tmp_path)
    before = declaration.read_text(encoding="utf-8")

    result = engine(
        tmp_path,
        config_validator=lambda _p: DnssecDisableStep(
            "named-checkconf", False, "błąd składni"
        ),
    ).apply(plan, commit=True)

    assert result.status == "ROLLED-BACK"
    assert result.rolled_back is True
    assert result.committed is False
    assert declaration.read_text(encoding="utf-8") == before


def test_conflict_when_declaration_changed_since_plan(tmp_path: Path) -> None:
    plan, declaration = setup_plan(tmp_path)
    declaration.write_text("zone \"other.pl\" {};\n", encoding="utf-8")

    result = engine(tmp_path).apply(plan, commit=True)

    assert result.status == "CONFLICT"
    assert result.committed is False


def test_read_ds_state_parses_rndc_output(monkeypatch) -> None:
    import zonectl.core.dnssec_disable_transaction as module
    from zonectl.core.runner import CommandResult

    output = (
        "dnssec-policy: default\n"
        "key: 13062 (ECDSAP256SHA256), CSK\n"
        "  - goal:           hidden\n"
        "  - dnskey:         omnipresent\n"
        "  - ds:             hidden\n"
    )
    monkeypatch.setattr(
        module, "run", lambda *_a, **_k: CommandResult(0, output, "")
    )

    assert read_ds_state("example.pl").state == "hidden"


def test_read_ds_state_reports_unparsable_output(monkeypatch) -> None:
    import zonectl.core.dnssec_disable_transaction as module
    from zonectl.core.runner import CommandResult

    monkeypatch.setattr(
        module, "run", lambda *_a, **_k: CommandResult(0, "nieznany format\n", "")
    )

    assert read_ds_state("example.pl").state is None
