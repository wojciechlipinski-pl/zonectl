from __future__ import annotations

import json
from pathlib import Path

import pytest

from zonectl.core.discovery import ZoneConfig
from zonectl.core.dnssec_enable_transaction import DnssecEnableStep
from zonectl.core.dnssec_policy_inventory import (
    DnssecPolicy,
    DnssecPolicyInventory,
    PolicyKey,
    PolicyTiming,
)
from zonectl.core.dnssec_policy_migration import (
    DnssecPolicyMigrationWorkflow,
    migration_ds_identity_evidence,
)
from zonectl.core.dnssec_policy_migration_plan import (
    DnssecPolicyMigrationPlanError,
    DnssecPolicyMigrationPlanner,
)

from zonectl.core.dnssec_policy_migration_state import (
    DnssecPolicyMigrationStore,
    MigrationEvidence,
    MigrationPhase,
)


SOURCE_DS = "12345 15 2 " + "A" * 64
TARGET_DS = "54321 13 2 " + "B" * 64


def policy(
    name: str,
    keys: tuple[PolicyKey, ...],
    *,
    safety: str = "PASS",
    compatibility: str = "COMPATIBLE",
) -> DnssecPolicy:
    return DnssecPolicy(
        name,
        False,
        keys,
        True,
        False,
        None,
        None,
        PolicyTiming(dnskey_ttl="1h", parent_ds_ttl="1d"),
        ("SHA-256",),
        True,
        False,
        safety,
        (),
        (),
        compatibility,
        (),
    )


def setup(tmp_path: Path, *, target_compatibility: str = "COMPATIBLE"):
    zone_file = tmp_path / "alpha.db"
    zone_file.write_text("$TTL 3600\n", encoding="utf-8")
    declaration = tmp_path / "zones.conf"
    declaration.write_text(
        f'''zone "alpha.example.test" {{
 type primary;
 file "{zone_file}";
 dnssec-policy old;
 inline-signing yes;
}};
''',
        encoding="utf-8",
    )
    zone = ZoneConfig(
        "alpha.example.test",
        "primary",
        zone_file,
        declaration,
        dnssec_policy="old",
        inline_signing=True,
        source_exists=True,
        source_writable=True,
    )
    old = policy("old", (PolicyKey("CSK", "ED25519", "P1Y"),))
    new = policy(
        "new",
        (
            PolicyKey("KSK", "ECDSAP256SHA256", "P2Y"),
            PolicyKey("ZSK", "ECDSAP256SHA256", "P90D"),
        ),
        compatibility=target_compatibility,
    )
    inventory = DnssecPolicyInventory(tmp_path / "named.conf", (old, new), ())
    return zone, inventory, declaration


def make_plan(tmp_path: Path):
    zone, inventory, declaration = setup(tmp_path)
    plan = DnssecPolicyMigrationPlanner().plan(
        zone,
        source_policy="old",
        target_policy="new",
        policy_inventory=inventory,
    )
    # The transaction intentionally refuses plans not validated against a candidate.
    object.__setattr__(plan, "candidate_validation", "PASS")
    return plan, declaration


def ok(name: str):
    return lambda *_args: DnssecEnableStep(name, True, "OK")


def workflow(tmp_path: Path, evidence=lambda _state: MigrationEvidence()):
    return DnssecPolicyMigrationWorkflow(
        tmp_path / "backups",
        tmp_path / "state",
        root_config=tmp_path / "named.conf",
        config_validator=ok("checkconf"),
        activator=ok("reconfig"),
        loaded_verifier=ok("loaded"),
        kasp_verifier=ok("kasp"),
        evidence_collector=evidence,
        source_ds_collector=lambda _zone: (SOURCE_DS,),
    )


def test_plan_compares_csk_with_ksk_zsk_and_ds_change(tmp_path: Path) -> None:
    plan, declaration = make_plan(tmp_path)
    assert plan.source.key_model == "CSK"
    assert plan.target.key_model == "KSK+ZSK"
    assert plan.ds_impact == "CHANGE_REQUIRED"
    assert "dnssec-policy new;" in plan.candidate_text
    assert "algorithms" in " ".join(plan.differences)
    assert declaration.read_text(encoding="utf-8") == plan.original_text


def test_timing_only_policy_change_still_requires_ds_review_gate(
    tmp_path: Path,
) -> None:
    zone, _, _ = setup(tmp_path)
    old = policy("old", (PolicyKey("CSK", "ED25519", "P1Y"),))
    new = policy("new", (PolicyKey("CSK", "ED25519", "P2Y"),))
    inventory = DnssecPolicyInventory(tmp_path / "named.conf", (old, new), ())
    plan = DnssecPolicyMigrationPlanner().plan(
        zone,
        source_policy="old",
        target_policy="new",
        policy_inventory=inventory,
    )
    assert plan.ds_impact == "REVIEW_REQUIRED"


def test_plan_requires_explicit_matching_source_and_distinct_target(
    tmp_path: Path,
) -> None:
    zone, inventory, _ = setup(tmp_path)
    with pytest.raises(DnssecPolicyMigrationPlanError, match="nie odpowiada"):
        DnssecPolicyMigrationPlanner().plan(
            zone, source_policy="new", target_policy="old", policy_inventory=inventory
        )
    with pytest.raises(DnssecPolicyMigrationPlanError, match="różnić"):
        DnssecPolicyMigrationPlanner().plan(
            zone, source_policy="old", target_policy="old", policy_inventory=inventory
        )


def test_review_requires_acknowledgement(tmp_path: Path) -> None:
    zone, inventory, _ = setup(tmp_path, target_compatibility="REVIEW")
    with pytest.raises(DnssecPolicyMigrationPlanError, match="jawnego"):
        DnssecPolicyMigrationPlanner().plan(
            zone, source_policy="old", target_policy="new", policy_inventory=inventory
        )
    assert (
        DnssecPolicyMigrationPlanner()
        .plan(
            zone,
            source_policy="old",
            target_policy="new",
            policy_inventory=inventory,
            acknowledge_policy_review=True,
        )
        .safety_status
        == "REVIEW"
    )


def test_start_is_dry_run_and_requires_all_confirmations(tmp_path: Path) -> None:
    plan, declaration = make_plan(tmp_path)
    before = declaration.read_bytes()
    assert workflow(tmp_path).start(plan).status == "DRY-RUN"
    assert (
        workflow(tmp_path)
        .start(plan, commit=True, activate=True, confirmation="wrong")
        .status
        == "REJECTED"
    )
    assert declaration.read_bytes() == before
    assert not (tmp_path / "backups").exists()


def test_start_failure_rolls_back_declaration(tmp_path: Path) -> None:
    plan, declaration = make_plan(tmp_path)
    before = declaration.read_bytes()
    validations = 0

    def fail_candidate_then_accept_restore(_root: Path) -> DnssecEnableStep:
        nonlocal validations
        validations += 1
        return DnssecEnableStep("checkconf", validations > 1, "synthetic")

    engine = DnssecPolicyMigrationWorkflow(
        tmp_path / "backups",
        tmp_path / "state",
        root_config=tmp_path / "named.conf",
        config_validator=fail_candidate_then_accept_restore,
        activator=ok("reconfig"),
        loaded_verifier=ok("loaded"),
        kasp_verifier=ok("kasp"),
        source_ds_collector=lambda _zone: (SOURCE_DS,),
    )
    result = engine.start(plan, commit=True, activate=True, confirmation=plan.zone)
    assert result.status == "ROLLED_BACK"
    assert result.rolled_back is True
    assert declaration.read_bytes() == before
    persisted = DnssecPolicyMigrationStore(tmp_path / "state").load(plan.zone)
    assert persisted.phase == MigrationPhase.ROLLED_BACK
    assert persisted.source_key_ids == ("12345:15",)
    assert persisted.declaration_file == "zones.conf"


@pytest.mark.parametrize(
    "failed_restore_step",
    ("checkconf", "reconfig", "loaded", "kasp"),
)
def test_start_failure_restore_verification_failure_persists_failed(
    tmp_path: Path, failed_restore_step: str
) -> None:
    case = tmp_path / failed_restore_step
    case.mkdir()
    plan, declaration = make_plan(case)
    before = declaration.read_bytes()
    calls = {"checkconf": 0}

    def checkconf(_root: Path) -> DnssecEnableStep:
        calls["checkconf"] += 1
        # The first failure enters rollback; a second failure injects the
        # named-checkconf restore-verification case.
        ok_result = calls["checkconf"] > 1 and failed_restore_step != "checkconf"
        return DnssecEnableStep("checkconf", ok_result, "synthetic")

    def restore_step(name: str):
        return lambda *_args: DnssecEnableStep(
            name, name != failed_restore_step, "synthetic"
        )

    engine = DnssecPolicyMigrationWorkflow(
        case / "backups",
        case / "state",
        root_config=case / "named.conf",
        config_validator=checkconf,
        activator=restore_step("reconfig"),
        loaded_verifier=restore_step("loaded"),
        kasp_verifier=restore_step("kasp"),
        source_ds_collector=lambda _zone: (SOURCE_DS,),
    )

    result = engine.start(plan, commit=True, activate=True, confirmation=plan.zone)

    assert result.status == "FAILED"
    assert result.rolled_back is False
    assert declaration.read_bytes() == before
    persisted = DnssecPolicyMigrationStore(case / "state").load(plan.zone)
    assert persisted.phase == MigrationPhase.FAILED
    assert persisted.failure == f"Rollback failed at {failed_restore_step}"


def test_start_failure_atomic_restore_failure_persists_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, declaration = make_plan(tmp_path)
    original_write = DnssecPolicyMigrationWorkflow._atomic_write
    writes = 0

    def fail_restore(*args):
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("synthetic restore failure")
        return original_write(*args)

    monkeypatch.setattr(
        DnssecPolicyMigrationWorkflow, "_atomic_write", staticmethod(fail_restore)
    )
    engine = workflow(tmp_path)
    engine.config_validator = lambda _root: DnssecEnableStep(
        "checkconf", False, "candidate failure"
    )

    result = engine.start(plan, commit=True, activate=True, confirmation=plan.zone)

    assert result.status == "FAILED"
    assert result.rolled_back is False
    assert "dnssec-policy new;" in declaration.read_text(encoding="utf-8")
    persisted = DnssecPolicyMigrationStore(tmp_path / "state").load(plan.zone)
    assert persisted.phase == MigrationPhase.FAILED
    assert persisted.failure == "Rollback failed at declaration-restore"


def test_evidence_drives_each_phase_and_never_elapsed_time(tmp_path: Path) -> None:
    plan, _ = make_plan(tmp_path)
    current = MigrationEvidence()
    engine = workflow(tmp_path, lambda _state: current)
    assert (
        engine.start(plan, commit=True, activate=True, confirmation=plan.zone).status
        == "POLICY_APPLIED"
    )
    assert engine.advance(plan.zone).phase == "WAITING_DNSKEY"
    current = MigrationEvidence(True, True, True, True, True)
    assert engine.advance(plan.zone).phase == "WAITING_DS"
    current = MigrationEvidence(True, True, True, True, True, 1, True, True)
    assert engine.advance(plan.zone).status == "WAITING"
    current = MigrationEvidence(True, True, True, True, True, 2, True, True)
    assert engine.advance(plan.zone).phase == "WAITING_PROPAGATION"
    assert engine.advance(plan.zone).phase == "READY_TO_FINALIZE"
    assert engine.finalize(plan.zone).status == "DRY-RUN"
    assert (
        engine.finalize(plan.zone, commit=True, confirmation=plan.zone).phase
        == "COMPLETE"
    )


def test_rollback_is_blocked_after_target_ds_observation(tmp_path: Path) -> None:
    plan, _ = make_plan(tmp_path)
    evidence = MigrationEvidence(True, True, True, True, True, 2, True, True)
    engine = workflow(tmp_path, lambda _state: evidence)
    engine.start(plan, commit=True, activate=True, confirmation=plan.zone)
    engine.advance(plan.zone)
    engine.advance(plan.zone)
    result = engine.rollback(plan.zone, confirmation=plan.zone)
    assert result.status == "REJECTED"
    assert "DS" in result.steps[0].message


def test_state_rejects_corruption_and_contains_no_dns_material(tmp_path: Path) -> None:
    plan, _ = make_plan(tmp_path)
    engine = workflow(tmp_path)
    result = engine.start(plan, commit=True, activate=True, confirmation=plan.zone)
    state_path = Path(result.state_file or "")
    payload = state_path.read_text(encoding="utf-8")
    assert "AwEAAsecret-key-material" not in payload
    assert "203.0.113.53" not in payload
    assert str(tmp_path) not in payload
    state_path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="odczytać"):
        DnssecPolicyMigrationStore(tmp_path / "state").load(plan.zone)


def test_state_json_uses_explicit_phase(tmp_path: Path) -> None:
    plan, _ = make_plan(tmp_path)
    result = workflow(tmp_path).start(
        plan, commit=True, activate=True, confirmation=plan.zone
    )
    payload = json.loads(Path(result.state_file or "").read_text(encoding="utf-8"))
    assert payload["phase"] == MigrationPhase.POLICY_APPLIED.value


def test_generic_match_for_source_key_never_counts_as_target() -> None:
    source_only = (("MATCH", (SOURCE_DS,)), ("MATCH", (SOURCE_DS,)))
    consistent, target_seen, source_seen = migration_ds_identity_evidence(
        ("12345:15",), (SOURCE_DS, TARGET_DS), source_only
    )
    assert consistent is True
    assert target_seen is False
    assert source_seen is True

    mixed = (("MATCH", (SOURCE_DS, TARGET_DS)), ("MATCH", (TARGET_DS,)))
    _, target_seen, source_seen = migration_ds_identity_evidence(
        ("12345:15",), (SOURCE_DS, TARGET_DS), mixed
    )
    assert target_seen is True
    assert source_seen is False


def test_source_identity_and_target_evidence_resume_after_restart(
    tmp_path: Path,
) -> None:
    plan, _ = make_plan(tmp_path)
    first = workflow(tmp_path)
    first.start(plan, commit=True, activate=True, confirmation=plan.zone)

    def resumed_evidence(state):
        assert state.source_key_ids == ("12345:15",)
        _, target_seen, source_seen = migration_ds_identity_evidence(
            state.source_key_ids,
            (SOURCE_DS, TARGET_DS),
            (("MATCH", (TARGET_DS,)), ("MATCH", (TARGET_DS,))),
        )
        return MigrationEvidence(
            True, True, True, True, True, 2, True, target_seen, source_seen
        )

    resumed = workflow(tmp_path, resumed_evidence)
    assert resumed.status(plan.zone).phase == MigrationPhase.POLICY_APPLIED
    assert resumed.check(plan.zone).status == "OBSERVED"
    loaded = DnssecPolicyMigrationStore(tmp_path / "state").load(plan.zone)
    assert loaded.evidence.target_ds_observed is True
    assert loaded.evidence.checked_at is not None
    assert loaded.source_key_ids == ("12345:15",)


def test_start_rejects_commit_without_trustworthy_source_identity(
    tmp_path: Path,
) -> None:
    plan, declaration = make_plan(tmp_path)
    before = declaration.read_bytes()
    engine = workflow(tmp_path)
    engine.source_ds_collector = lambda _zone: ("not a DS",)
    result = engine.start(plan, commit=True, activate=True, confirmation=plan.zone)
    assert result.status == "REJECTED"
    assert declaration.read_bytes() == before
    assert not (tmp_path / "state" / "alpha.example.test.json").exists()


@pytest.mark.parametrize(
    "field,value",
    (
        ("extra", "unexpected"),
        ("rollback_allowed", "false"),
        ("transaction_id", "../../escape"),
        ("ds_impact", "NO_CHANGE"),
        ("source_key_ids", ["12345:15", "bad"]),
        ("backup_file", "../../zones.conf"),
        ("declaration_file", "../zones.conf"),
    ),
)
def test_state_schema_rejects_tampering(
    tmp_path: Path, field: str, value: object
) -> None:
    plan, _ = make_plan(tmp_path)
    result = workflow(tmp_path).start(
        plan, commit=True, activate=True, confirmation=plan.zone
    )
    path = Path(result.state_file or "")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        DnssecPolicyMigrationStore(tmp_path / "state").load(plan.zone)


@pytest.mark.parametrize(
    "attribute,failed_name",
    (
        ("config_validator", "checkconf"),
        ("activator", "reconfig"),
        ("loaded_verifier", "loaded"),
        ("kasp_verifier", "kasp"),
    ),
)
def test_rollback_post_restore_failure_is_persisted_as_failed(
    tmp_path: Path, attribute: str, failed_name: str
) -> None:
    case = tmp_path / attribute
    case.mkdir()
    plan, declaration = make_plan(case)
    source = declaration.read_text(encoding="utf-8")
    engine = workflow(case)
    engine.start(plan, commit=True, activate=True, confirmation=plan.zone)
    setattr(
        engine,
        attribute,
        lambda *_args: DnssecEnableStep(failed_name, False, "synthetic failure"),
    )
    result = engine.rollback(plan.zone, confirmation=plan.zone)
    assert result.status == "FAILED"
    assert result.rolled_back is False
    assert declaration.read_text(encoding="utf-8") == source
    persisted = DnssecPolicyMigrationStore(case / "state").load(plan.zone)
    assert persisted.phase == MigrationPhase.FAILED
    assert persisted.failure == f"Rollback failed at {failed_name}"


def test_state_and_audit_are_privacy_safe(tmp_path: Path) -> None:
    plan, _ = make_plan(tmp_path)
    result = workflow(tmp_path).start(
        plan, commit=True, activate=True, confirmation=plan.zone
    )
    state_text = Path(result.state_file or "").read_text(encoding="utf-8")
    audit_text = (tmp_path / "audit-v1.jsonl").read_text(encoding="utf-8")
    for forbidden in ("A" * 32, "203.0.113.53", str(tmp_path), SOURCE_DS):
        assert forbidden not in state_text
        assert forbidden not in audit_text
    assert '"12345:15"' in state_text
