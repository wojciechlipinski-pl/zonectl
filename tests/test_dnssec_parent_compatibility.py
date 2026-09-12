from zonectl.core.dnssec_ds_check import DnssecDsCheck, DsResolverCheck
from zonectl.core.dnssec_parent_compatibility import evaluate_parent_compatibility
from zonectl.core.dnssec_policy_inventory import DnssecPolicy, PolicyKey, PolicyTiming


def policy(
    *, algorithm: str = "ED25519", digests: tuple[str, ...] = ("SHA-256",)
) -> DnssecPolicy:
    return DnssecPolicy(
        name="modern",
        built_in=False,
        keys=(PolicyKey("CSK", algorithm, "unlimited"),),
        inline_signing=True,
        nsec3=False,
        nsec3_iterations=None,
        nsec3_optout=None,
        timing=PolicyTiming(),
        cds_digest_types=digests,
        cdnskey=True,
        offline_ksk=False,
        status="PASS",
        warnings=(),
        zones=("alpha.example.test",),
    )


def check(status: str, record: str = "12345 15 2 ABCDEF") -> DnssecDsCheck:
    return DnssecDsCheck(
        zone="alpha.example.test",
        status=status,
        kasp_ready=True,
        expected_ds=(),
        resolver_checks=(DsResolverCheck("resolver", "MATCH", (record,), "ok"),),
        authority_checks=(),
        next_action="",
        errors=(),
    )


def test_matching_published_ds_confirms_parent_support_without_hashes() -> None:
    result = evaluate_parent_compatibility(policy(), check("PASS"))

    assert result.status == "COMPATIBLE"
    assert result.observed_ds_algorithms == (15,)
    assert result.observed_digest_types == (2,)
    assert "ABCDEF" not in str(result.to_dict())
    assert "resolver" not in str(result.to_dict())


def test_mismatched_algorithm_is_blocked() -> None:
    result = evaluate_parent_compatibility(policy(), check("PASS", "12345 13 2 A"))

    assert result.status == "BLOCKED"
    assert "algorytm" in result.findings[0].casefold()


def test_missing_ds_does_not_claim_parent_support() -> None:
    result = evaluate_parent_compatibility(policy(), check("NOT_PUBLISHED", ""))

    assert result.status == "NOT_CONFIRMED"


def test_unknown_algorithm_and_sha1_digest_are_blocked() -> None:
    unknown = evaluate_parent_compatibility(
        policy(algorithm="PRIVATE123", digests=("SHA-1",)), check("PASS")
    )

    assert unknown.status == "BLOCKED"
    assert len(unknown.findings) == 2


def test_propagation_is_indeterminate() -> None:
    result = evaluate_parent_compatibility(policy(), check("PROPAGATING"))

    assert result.status == "INDETERMINATE"
