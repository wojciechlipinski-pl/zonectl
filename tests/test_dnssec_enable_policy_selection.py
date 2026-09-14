from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from zonectl.core.discovery import ZoneConfig
from zonectl.core.dnssec_enable_plan import DnssecEnablePlanError, DnssecEnablePlanner
from zonectl.core.dnssec_policy_inventory import (
    DnssecPolicy,
    DnssecPolicyInventory,
    PolicyKey,
    PolicyTiming,
)


def zone(tmp_path: Path) -> ZoneConfig:
    source = tmp_path / "example.test"
    source.write_text("zone data\n", encoding="utf-8")
    declaration = tmp_path / "named.conf"
    declaration.write_text(
        f'zone "example.test" {{ type primary; file "{source}"; }};\n',
        encoding="utf-8",
    )
    return ZoneConfig(
        "example.test",
        "primary",
        source,
        declaration,
        source_exists=True,
        source_writable=True,
    )


def policy(
    name: str,
    keys: tuple[PolicyKey, ...],
    *,
    safety: str = "PASS",
    compatibility: str = "COMPATIBLE",
) -> DnssecPolicy:
    return DnssecPolicy(
        name=name,
        built_in=False,
        keys=keys,
        inline_signing=True,
        nsec3=False,
        nsec3_iterations=None,
        nsec3_optout=None,
        timing=PolicyTiming(dnskey_ttl="1h", parent_ds_ttl="1d", publish_safety="PT1H"),
        cds_digest_types=("SHA-256",),
        cdnskey=True,
        offline_ksk=False,
        status=safety,
        warnings=(),
        zones=(),
        bind_compatibility=compatibility,
        compatibility_findings=(),
    )


def inventory(tmp_path: Path, selected: DnssecPolicy) -> DnssecPolicyInventory:
    return DnssecPolicyInventory(tmp_path / "named.conf", (selected,), ())


def test_named_csk_policy_facts_are_carried_into_plan(tmp_path: Path) -> None:
    selected = policy("modern-csk", (PolicyKey("CSK", "ED25519", "P1Y"),))

    plan = DnssecEnablePlanner().plan(
        zone(tmp_path),
        policy="modern-csk",
        policy_inventory=inventory(tmp_path, selected),
        zone_directory=tmp_path,
    )

    assert plan.policy == "modern-csk"
    assert plan.policy_safety == "PASS"
    assert plan.bind_compatibility == "COMPATIBLE"
    assert plan.key_model == "CSK"
    assert plan.algorithms == ("ED25519",)
    assert plan.rollover == ("CSK: lifetime=P1Y",)
    assert "DNSKEY TTL=1h" in plan.publication
    assert "nie zmienia DS" in plan.ds_guidance


def test_split_ksk_zsk_policy_reports_both_roles_and_algorithms(
    tmp_path: Path,
) -> None:
    selected = policy(
        "split",
        (
            PolicyKey("KSK", "ECDSAP384SHA384", "P2Y"),
            PolicyKey("ZSK", "ECDSAP256SHA256", "P90D"),
        ),
    )
    plan = DnssecEnablePlanner().plan(
        zone(tmp_path),
        policy="split",
        policy_inventory=inventory(tmp_path, selected),
        zone_directory=tmp_path,
    )

    assert plan.key_model == "KSK+ZSK"
    assert plan.algorithms == ("ECDSAP384SHA384", "ECDSAP256SHA256")


@pytest.mark.parametrize("compatibility", ["BLOCKED", "UNKNOWN"])
def test_blocked_and_unknown_bind_compatibility_are_rejected(
    tmp_path: Path, compatibility: str
) -> None:
    selected = policy(
        "unsafe", (PolicyKey("CSK", "ED25519", "P1Y"),), compatibility=compatibility
    )
    with pytest.raises(DnssecEnablePlanError, match="Zgodność"):
        DnssecEnablePlanner().plan(
            zone(tmp_path),
            policy="unsafe",
            policy_inventory=inventory(tmp_path, selected),
            zone_directory=tmp_path,
        )


def test_review_requires_explicit_acknowledgement(tmp_path: Path) -> None:
    selected = policy(
        "future", (PolicyKey("CSK", "ED25519", "P1Y"),), compatibility="REVIEW"
    )
    with pytest.raises(DnssecEnablePlanError, match="acknowledge-policy-review"):
        DnssecEnablePlanner().plan(
            zone(tmp_path),
            policy="future",
            policy_inventory=inventory(tmp_path, selected),
            zone_directory=tmp_path,
        )

    plan = DnssecEnablePlanner().plan(
        zone(tmp_path),
        policy="future",
        policy_inventory=inventory(tmp_path, selected),
        acknowledge_policy_review=True,
        zone_directory=tmp_path,
    )
    assert plan.review_acknowledged is True


def test_safety_blocked_policy_and_uninventoried_name_are_rejected(
    tmp_path: Path,
) -> None:
    selected = policy(
        "weak",
        (PolicyKey("CSK", "RSASHA1", "P1Y"),),
        safety="BLOCKED",
    )
    with pytest.raises(DnssecEnablePlanError, match="bezpieczeństwa BLOCKED"):
        DnssecEnablePlanner().plan(
            zone(tmp_path),
            policy="weak",
            policy_inventory=inventory(tmp_path, selected),
            zone_directory=tmp_path,
        )
    with pytest.raises(DnssecEnablePlanError, match="inwentarzu"):
        DnssecEnablePlanner().plan(
            zone(tmp_path),
            policy="missing",
            policy_inventory=inventory(tmp_path, replace(selected, status="PASS")),
            zone_directory=tmp_path,
        )


def test_candidate_validation_failure_blocks_plan(tmp_path: Path) -> None:
    selected = policy("safe", (PolicyKey("CSK", "ED25519", "P1Y"),))
    planner = DnssecEnablePlanner(
        tmp_path / "named.conf",
        candidate_validator=lambda *_args: (False, "synthetic invalid candidate"),
    )
    with pytest.raises(DnssecEnablePlanError, match="synthetic invalid candidate"):
        planner.plan(
            zone(tmp_path),
            policy="safe",
            policy_inventory=inventory(tmp_path, selected),
            zone_directory=tmp_path,
        )
