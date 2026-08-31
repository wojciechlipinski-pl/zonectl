from __future__ import annotations

import pytest

from zonectl.core.record_validation import (
    ValidationSeverity,
    validate_rdata,
    validate_zone,
)
from zonectl.core.zone_parser import DNSRecord


def record(owner: str, rtype: str, rdata: str, ttl: int = 3600) -> DNSRecord:
    return DNSRecord(owner, ttl, "IN", rtype, rdata, "")


def base_zone() -> list[DNSRecord]:
    return [
        record(
            "example.pl.",
            "SOA",
            "ns.example.pl. hostmaster.example.pl. 1 3600 900 1209600 300",
        ),
        record("example.pl.", "NS", "ns.example.pl."),
        record("example.pl.", "A", "192.0.2.10"),
        record("ns.example.pl.", "A", "192.0.2.53"),
    ]


@pytest.mark.parametrize(
    ("rtype", "value"),
    [
        ("A", "192.0.2.1"),
        ("AAAA", "2001:db8::1"),
        ("MX", "10 mail.example.pl."),
        ("SRV", "10 20 443 service.example.pl."),
        ("CAA", '0 issue "letsencrypt.org"'),
        ("DS", "12345 13 2 " + "ab" * 32),
        ("DNSKEY", "257 3 13 YWJjZA=="),
        ("SSHFP", "1 2 " + "ab" * 32),
        ("TLSA", "3 1 1 " + "ab" * 32),
        (
            "SOA",
            "ns.example.pl. hostmaster.example.pl. 1 3600 900 1209600 300",
        ),
        ("TXT", '"tekst z odstępami"'),
        ("NAPTR", '10 20 "U" "E2U+sip" "!^.*$!sip:x!" .'),
        ("SVCB", "1 svc.example.pl. alpn=h2 port=443"),
        ("HTTPS", "0 service.example.pl."),
    ],
)
def test_valid_type_dependent_rdata(rtype: str, value: str) -> None:
    assert validate_rdata(rtype, value) is None


@pytest.mark.parametrize(
    ("rtype", "value", "fragment"),
    [
        ("A", "999.1.1.1", "IPv4"),
        ("A", "192.0.2", "IPv4"),
        ("A", "192.0.2.1/24", "IPv4"),
        ("AAAA", "2001:db8:::1", "IPv6"),
        ("AAAA", "2001:db8::1/64", "IPv6"),
        ("MX", "mail.example.pl.", "format"),
        ("MX", "70000 mail.example.pl.", "zakres"),
        ("SRV", "10 20 70000 host.example.pl.", "zakres"),
        ("CAA", '0 "bad tag!" "ca.example"', "Tag"),
        ("DS", "1 13 2 abcd", "długość"),
        ("DNSKEY", "257 2 13 YWJjZA==", "wartość 3"),
        ("SSHFP", "1 2 abcd", "długość"),
        ("TLSA", "3 1 1 abcd", "długość"),
        ("SOA", "ns.example.pl. hostmaster.example.pl. 1", "wymaga"),
        ("TXT", '"niedomknięty', "cudzysłowy"),
        ("SVCB", "0 svc.example.pl. alpn=h2", "AliasMode"),
    ],
)
def test_invalid_type_dependent_rdata(
    rtype: str,
    value: str,
    fragment: str,
) -> None:
    error = validate_rdata(rtype, value)
    assert error is not None
    assert fragment.casefold() in error.casefold()


def issue_codes(records: list[DNSRecord]) -> set[str]:
    return {issue.code for issue in validate_zone("example.pl", records)}


def test_valid_zone_has_no_errors() -> None:
    issues = validate_zone("example.pl", base_zone())
    assert not [issue for issue in issues if issue.severity is ValidationSeverity.ERROR]


def test_cname_cannot_coexist_with_address() -> None:
    records = base_zone() + [
        record("www.example.pl.", "A", "192.0.2.20"),
        record("www.example.pl.", "CNAME", "example.pl."),
    ]
    assert "cname-conflict" in issue_codes(records)


def test_cname_at_apex_is_rejected_by_coexistence_rule() -> None:
    records = base_zone() + [
        record("example.pl.", "CNAME", "external.example."),
    ]
    assert "cname-conflict" in issue_codes(records)


def test_local_dangling_cname_is_warning_not_error() -> None:
    issues = validate_zone(
        "example.pl",
        base_zone()
        + [
            record("www.example.pl.", "CNAME", "missing.example.pl."),
        ],
    )
    dangling = [issue for issue in issues if issue.code == "missing-local-target"]
    assert len(dangling) == 1
    assert dangling[0].severity is ValidationSeverity.WARN


def test_external_cname_does_not_require_local_address() -> None:
    codes = issue_codes(
        base_zone()
        + [
            record("www.example.pl.", "CNAME", "www.example.net."),
        ]
    )
    assert "missing-local-target" not in codes


def test_cname_loop_is_error() -> None:
    records = base_zone() + [
        record("one.example.pl.", "CNAME", "two.example.pl."),
        record("two.example.pl.", "CNAME", "one.example.pl."),
    ]
    assert "cname-loop" in issue_codes(records)


def test_mx_target_cannot_be_cname() -> None:
    records = base_zone() + [
        record("example.pl.", "MX", "10 mail.example.pl."),
        record("mail.example.pl.", "CNAME", "external.example."),
    ]
    assert "alias-service-target" in issue_codes(records)


def test_local_ns_requires_glue_address() -> None:
    records = [item for item in base_zone() if item.owner != "ns.example.pl."]
    issues = validate_zone("example.pl", records)
    glue = [issue for issue in issues if issue.code == "missing-local-target"]
    assert glue
    assert glue[0].severity is ValidationSeverity.ERROR


def test_duplicate_record_is_warning() -> None:
    duplicate = record("www.example.pl.", "A", "192.0.2.20")
    issues = validate_zone(
        "example.pl",
        base_zone() + [duplicate, duplicate],
    )
    assert any(
        issue.code == "duplicate-record" and issue.severity is ValidationSeverity.WARN
        for issue in issues
    )
