from pathlib import Path

import pytest

from zonectl.core.discovery import BindDiscoveryError
from zonectl.core.dnssec_policy_inventory import DnssecPolicyInventoryReader


def config(tmp_path: Path, policy: str, zone_policy: str = "modern") -> Path:
    root = tmp_path / "named.conf"
    zone = tmp_path / "alpha.db"
    zone.write_text("", encoding="utf-8")
    root.write_text(
        policy
        + f'''\nzone "alpha.example.test" {{
  type primary;
  file "{zone}";
  dnssec-policy {zone_policy};
}};\n''',
        encoding="utf-8",
    )
    return root


def test_reads_allowlisted_policy_parameters_and_zone_use(tmp_path: Path) -> None:
    root = config(
        tmp_path,
        """dnssec-policy "modern" {
  inline-signing yes;
  keys {
    ksk lifetime P1Y algorithm ECDSAP384SHA384;
    zsk lifetime 60d algorithm ECDSAP384SHA384;
  };
  nsec3param iterations 0 optout no salt-length 0;
  dnskey-ttl 1h;
  parent-ds-ttl 1d;
  publish-safety PT1H;
  retire-safety PT2H;
  zone-propagation-delay 5m;
  parent-propagation-delay 2h;
  signatures-refresh 5d;
  signatures-validity 14d;
  signatures-validity-dnskey 14d;
  max-zone-ttl 1d;
  cds-digest-types SHA-256 SHA-384;
  cdnskey yes;
  offline-ksk no;
};""",
    )
    report = DnssecPolicyInventoryReader(root).read()
    policy = next(item for item in report.policies if item.name == "modern")
    assert policy.status == "PASS"
    assert [key.role for key in policy.keys] == ["KSK", "ZSK"]
    assert policy.nsec3_iterations == 0
    assert policy.nsec3_optout is False
    assert policy.zones == ("alpha.example.test",)
    assert policy.timing.dnskey_ttl == "1h"
    assert policy.timing.parent_propagation_delay == "2h"
    assert policy.timing.signatures_validity_dnskey == "14d"
    assert policy.cds_digest_types == ("SHA-256", "SHA-384")
    assert policy.cdnskey is True
    assert policy.offline_ksk is False


def test_blocks_obsolete_unknown_and_nonzero_nsec3(tmp_path: Path) -> None:
    root = config(
        tmp_path,
        """dnssec-policy weak {
  keys { csk lifetime unlimited algorithm RSASHA1 2048; };
  nsec3param iterations 5 optout yes salt-length 8;
};""",
        "weak",
    )
    policy = next(
        item
        for item in DnssecPolicyInventoryReader(root).read().policies
        if item.name == "weak"
    )
    assert policy.status == "BLOCKED"
    assert any("Przestarzały" in warning for warning in policy.warnings)
    assert any("iterations" in warning for warning in policy.warnings)


def test_reports_undefined_zone_policy(tmp_path: Path) -> None:
    root = config(tmp_path, "", "missing-policy")
    report = DnssecPolicyInventoryReader(root).read()
    assert report.undefined_references == ("missing-policy",)


def test_rejects_duplicate_policy_names(tmp_path: Path) -> None:
    root = config(
        tmp_path,
        """dnssec-policy same { keys { csk lifetime unlimited algorithm ED25519; }; };
dnssec-policy \"same\" { keys { csk lifetime unlimited algorithm ED448; }; };""",
        "same",
    )
    with pytest.raises(BindDiscoveryError, match="więcej niż jedną"):
        DnssecPolicyInventoryReader(root).read()


def test_json_payload_never_contains_unrelated_secret(tmp_path: Path) -> None:
    root = config(
        tmp_path,
        """key "transfer" { algorithm hmac-sha256; secret "TOP-SECRET"; };
dnssec-policy safe { keys { csk lifetime unlimited algorithm ED25519; }; };""",
        "safe",
    )
    payload = str(DnssecPolicyInventoryReader(root).read().to_dict())
    assert "TOP-SECRET" not in payload
    assert "secret" not in payload.casefold()


def test_builtin_default_remains_available(tmp_path: Path) -> None:
    root = config(tmp_path, "", "default")
    policy = next(
        item
        for item in DnssecPolicyInventoryReader(root).read().policies
        if item.name == "default"
    )
    assert policy.built_in is True
    assert policy.status == "PASS"
    assert policy.keys[0].role == "CSK"
