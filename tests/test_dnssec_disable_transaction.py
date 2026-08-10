from __future__ import annotations

import json
from pathlib import Path

from zonectl.core.discovery import ZoneConfig
from zonectl.core.dnssec_disable_plan import DnssecDisablePlanner
from zonectl.core.dnssec_disable_transaction import (
    DnssecDisableStep,
    DnssecDisableTransaction,
    KaspReading,
    read_kasp_states,
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
    return DnssecDisablePlanner().plan(zone), declaration


def kasp(all_hidden: bool | None, states=("goal=hidden",)):
    return lambda _zone: KaspReading(all_hidden, tuple(states), "stub")


def ok(name: str):
    return lambda *_args: DnssecDisableStep(name, True, "OK")


def engine(tmp_path: Path, **overrides):
    defaults = {
        "kasp_reader": kasp(True),
        "ds_gate": lambda _zone: True,
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


# --- plan ---------------------------------------------------------------


def test_plan_offers_both_candidate_texts(tmp_path: Path) -> None:
    plan, _ = setup_plan(tmp_path)

    assert "dnssec-policy insecure;" in plan.insecure_text
    assert "inline-signing yes;" in plan.insecure_text
    assert "dnssec-policy" not in plan.candidate_text
    assert "inline-signing" not in plan.candidate_text


# --- etap insecure ------------------------------------------------------


def test_insecure_dry_run_changes_nothing(tmp_path: Path) -> None:
    plan, declaration = setup_plan(tmp_path)
    before = declaration.read_text(encoding="utf-8")

    result = engine(tmp_path).apply(plan, stage="insecure")

    assert result.status == "DRY-RUN"
    assert declaration.read_text(encoding="utf-8") == before


def test_insecure_blocked_while_ds_still_visible(tmp_path: Path) -> None:
    plan, declaration = setup_plan(tmp_path)
    before = declaration.read_text(encoding="utf-8")

    result = engine(tmp_path, ds_gate=lambda _z: False).apply(
        plan, stage="insecure", commit=True
    )

    assert result.status == "BLOCKED"
    assert declaration.read_text(encoding="utf-8") == before


def test_visible_ds_cannot_be_overridden(tmp_path: Path) -> None:
    plan, declaration = setup_plan(tmp_path)
    before = declaration.read_text(encoding="utf-8")

    result = engine(tmp_path, ds_gate=lambda _z: False).apply(
        plan, stage="insecure", commit=True, acknowledge_unsigned=True
    )

    assert result.status == "BLOCKED"
    assert declaration.read_text(encoding="utf-8") == before


def test_insecure_commit_swaps_policy_and_keeps_inline_signing(
    tmp_path: Path,
) -> None:
    plan, declaration = setup_plan(tmp_path)

    result = engine(tmp_path).apply(
        plan, stage="insecure", commit=True, activate=True
    )

    assert result.status == "COMMIT"
    text = declaration.read_text(encoding="utf-8")
    assert "dnssec-policy insecure;" in text
    assert "inline-signing yes;" in text
    assert "type primary;" in text


# --- etap finalize ------------------------------------------------------


def test_finalize_blocked_while_keys_not_hidden(tmp_path: Path) -> None:
    plan, declaration = setup_plan(tmp_path)
    before = declaration.read_text(encoding="utf-8")

    result = engine(
        tmp_path, kasp_reader=kasp(False, ("goal=hidden", "dnskey=omnipresent"))
    ).apply(plan, stage="finalize", commit=True)

    assert result.status == "BLOCKED"
    assert "dnskey=omnipresent" in result.steps[0].message
    assert declaration.read_text(encoding="utf-8") == before


def test_visible_keys_cannot_be_overridden(tmp_path: Path) -> None:
    plan, declaration = setup_plan(tmp_path)
    before = declaration.read_text(encoding="utf-8")

    result = engine(tmp_path, kasp_reader=kasp(False, ("ds=unretentive",))).apply(
        plan, stage="finalize", commit=True, acknowledge_unsigned=True
    )

    assert result.status == "BLOCKED"
    assert declaration.read_text(encoding="utf-8") == before


def test_unreadable_kasp_blocks_without_acknowledgement(tmp_path: Path) -> None:
    plan, declaration = setup_plan(tmp_path)
    before = declaration.read_text(encoding="utf-8")

    result = engine(tmp_path, kasp_reader=kasp(None, ())).apply(
        plan, stage="finalize", commit=True
    )

    assert result.status == "BLOCKED"
    assert declaration.read_text(encoding="utf-8") == before


def test_unreadable_kasp_may_be_acknowledged(tmp_path: Path) -> None:
    plan, declaration = setup_plan(tmp_path)

    result = engine(tmp_path, kasp_reader=kasp(None, ())).apply(
        plan, stage="finalize", commit=True, acknowledge_unsigned=True
    )

    assert result.status == "COMMIT"
    assert "dnssec-policy" not in declaration.read_text(encoding="utf-8")


def test_finalize_removes_all_dnssec_directives(tmp_path: Path) -> None:
    plan, declaration = setup_plan(tmp_path)

    result = engine(tmp_path).apply(plan, stage="finalize", commit=True)

    assert result.status == "COMMIT"
    text = declaration.read_text(encoding="utf-8")
    assert "dnssec-policy" not in text
    assert "inline-signing" not in text
    assert "key-directory" not in text
    assert "type primary;" in text
    assert (tmp_path / "keys").is_dir()
    payload = json.loads(Path(result.manifest).read_text(encoding="utf-8"))
    assert payload["stage"] == "finalize"


# --- wspólne ------------------------------------------------------------


def test_rollback_restores_declaration_when_checkconf_fails(tmp_path: Path) -> None:
    plan, declaration = setup_plan(tmp_path)
    before = declaration.read_text(encoding="utf-8")

    result = engine(
        tmp_path,
        config_validator=lambda _p: DnssecDisableStep(
            "named-checkconf", False, "błąd składni"
        ),
    ).apply(plan, stage="insecure", commit=True)

    assert result.status == "ROLLED-BACK"
    assert result.rolled_back is True
    assert declaration.read_text(encoding="utf-8") == before


def test_conflict_when_declaration_changed_since_plan(tmp_path: Path) -> None:
    plan, declaration = setup_plan(tmp_path)
    declaration.write_text('zone "other.pl" {};\n', encoding="utf-8")

    result = engine(tmp_path).apply(plan, stage="insecure", commit=True)

    assert result.status == "CONFLICT"


def test_read_kasp_states_detects_all_hidden(monkeypatch) -> None:
    import zonectl.core.dnssec_disable_transaction as module
    from zonectl.core.runner import CommandResult

    output = (
        "key: 13062 (ECDSAP256SHA256), CSK\n"
        "  - goal:           hidden\n"
        "  - dnskey:         hidden\n"
        "  - ds:             hidden\n"
    )
    monkeypatch.setattr(module, "run", lambda *_a, **_k: CommandResult(0, output, ""))

    assert read_kasp_states("example.pl").all_hidden is True


def test_read_kasp_states_detects_visible_key(monkeypatch) -> None:
    import zonectl.core.dnssec_disable_transaction as module
    from zonectl.core.runner import CommandResult

    output = (
        "  - goal:           omnipresent\n"
        "  - dnskey:         omnipresent\n"
        "  - ds:             omnipresent\n"
    )
    monkeypatch.setattr(module, "run", lambda *_a, **_k: CommandResult(0, output, ""))

    assert read_kasp_states("example.pl").all_hidden is False


def test_read_kasp_states_reports_unparsable_output(monkeypatch) -> None:
    import zonectl.core.dnssec_disable_transaction as module
    from zonectl.core.runner import CommandResult

    monkeypatch.setattr(
        module, "run", lambda *_a, **_k: CommandResult(0, "nieznany format\n", "")
    )

    assert read_kasp_states("example.pl").all_hidden is None
