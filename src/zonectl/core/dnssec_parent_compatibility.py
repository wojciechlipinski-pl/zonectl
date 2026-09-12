"""Privacy-safe evaluation of policy parameters observed at the parent zone."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .dnssec_ds_check import DnssecDsCheck
from .dnssec_policy_inventory import DnssecPolicy


ALGORITHM_NUMBERS = {
    "RSASHA256": 8,
    "RSASHA512": 10,
    "ECDSAP256SHA256": 13,
    "ECDSAP384SHA384": 14,
    "ED25519": 15,
    "ED448": 16,
}
DIGEST_NUMBERS = {
    "SHA-1": 1,
    "SHA1": 1,
    "SHA-256": 2,
    "SHA256": 2,
    "SHA-384": 4,
    "SHA384": 4,
}
RECOMMENDED_DIGESTS = {2, 4}


@dataclass(frozen=True, slots=True)
class ParentPolicyCompatibility:
    """Allowlisted evidence of DNSSEC policy compatibility at the parent."""

    zone: str
    status: str
    policy_algorithms: tuple[int, ...]
    policy_digest_types: tuple[int, ...]
    observed_ds_algorithms: tuple[int, ...]
    observed_digest_types: tuple[int, ...]
    findings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return no DS hashes, DNSKEY material, resolver or server addresses."""

        return asdict(self)


def evaluate_parent_compatibility(
    policy: DnssecPolicy, check: DnssecDsCheck
) -> ParentPolicyCompatibility:
    """Evaluate only what published DS evidence can prove about the parent."""

    findings: list[str] = []
    policy_algorithms = tuple(
        sorted(
            {
                ALGORITHM_NUMBERS[key.algorithm]
                for key in policy.keys
                if key.role in {"KSK", "CSK"} and key.algorithm in ALGORITHM_NUMBERS
            }
        )
    )
    unknown_algorithms = sorted(
        {
            key.algorithm
            for key in policy.keys
            if key.role in {"KSK", "CSK"} and key.algorithm not in ALGORITHM_NUMBERS
        }
    )
    policy_digests = tuple(
        sorted(
            {
                DIGEST_NUMBERS[value]
                for value in policy.cds_digest_types
                if value in DIGEST_NUMBERS
            }
        )
    )
    unknown_digests = sorted(
        value for value in policy.cds_digest_types if value not in DIGEST_NUMBERS
    )
    observed_algorithms, observed_digests = _observed_ds_parameters(check)

    if unknown_algorithms:
        findings.append(
            "Nie można ocenić numeru algorytmu: " + ", ".join(unknown_algorithms)
        )
    if unknown_digests:
        findings.append(
            "Nie można ocenić typu skrótu DS: " + ", ".join(unknown_digests)
        )
    if 1 in policy_digests:
        findings.append("SHA-1 nie jest akceptowany jako bezpieczny skrót DS")
    if findings:
        status = "BLOCKED"
    elif check.status == "FAIL":
        status = "BLOCKED"
        findings.append("Kontrola delegacji DS zakończyła się błędem")
    elif check.status in {"INDETERMINATE", "PROPAGATING"}:
        status = "INDETERMINATE"
        findings.append("Delegacja DS nie daje jeszcze jednoznacznego wyniku")
    elif check.status in {"NOT_PUBLISHED", "NOT_READY"}:
        status = "NOT_CONFIRMED"
        findings.append(
            "Brak opublikowanego DS; obsługi parametrów przez rodzica nie potwierdzono"
        )
    elif not observed_algorithms or not observed_digests:
        status = "INDETERMINATE"
        findings.append("Nie odczytano publicznych parametrów DS")
    elif policy_algorithms and not set(policy_algorithms) & set(observed_algorithms):
        status = "BLOCKED"
        findings.append("Algorytm opublikowanego DS nie odpowiada polityce KASP")
    elif policy_digests and not set(policy_digests) & set(observed_digests):
        status = "BLOCKED"
        findings.append("Typ skrótu opublikowanego DS nie odpowiada polityce KASP")
    elif not set(observed_digests) <= RECOMMENDED_DIGESTS:
        status = "BLOCKED"
        findings.append("Rodzic publikuje niezalecony typ skrótu DS")
    else:
        status = "COMPATIBLE"
        findings.append("Opublikowany DS potwierdza obsługę parametrów przez rodzica")

    return ParentPolicyCompatibility(
        zone=check.zone,
        status=status,
        policy_algorithms=policy_algorithms,
        policy_digest_types=policy_digests,
        observed_ds_algorithms=observed_algorithms,
        observed_digest_types=observed_digests,
        findings=tuple(findings),
    )


def _observed_ds_parameters(
    check: DnssecDsCheck,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    algorithms: set[int] = set()
    digests: set[int] = set()
    for resolver in check.resolver_checks:
        for record in resolver.records:
            fields = record.split()
            if len(fields) < 4:
                continue
            try:
                algorithms.add(int(fields[1]))
                digests.add(int(fields[2]))
            except ValueError:
                continue
    return tuple(sorted(algorithms)), tuple(sorted(digests))
