from pathlib import Path

from zonectl.core.bind_access_audit import BindAccessAuditor
from zonectl.core.bind_access_inventory import (
    BindAccessInventoryReader,
)


def _audit(tmp_path: Path, text: str):
    root = tmp_path / "named.conf"
    root.write_text(text, encoding="utf-8")
    return BindAccessAuditor().audit(BindAccessInventoryReader(root).collect())


def test_detects_duplicate_invalid_and_noncanonical_entries(tmp_path: Path) -> None:
    audit = _audit(
        tmp_path,
        'acl "trusted" { 192.0.2.0/24; 192.0.2.0/24; '
        '192.168.200/24; 10.0.0.1/8; };\n'
        'options { allow-recursion { trusted; }; };\n',
    )
    codes = [item.code for item in audit.findings]
    assert "DUPLICATE_ENTRY" in codes
    assert "INVALID_ADDRESS" in codes
    assert "NON_CANONICAL_NETWORK" in codes
    assert audit.status == "FAIL"


def test_detects_unknown_reference_and_reports_zone(tmp_path: Path) -> None:
    audit = _audit(
        tmp_path,
        'zone "example.pl" { type primary; file "/x"; '
        'allow-transfer { missing-group; }; };\n',
    )
    finding = next(x for x in audit.findings if x.code == "UNKNOWN_REFERENCE")
    assert finding.zones == ("example.pl",)
    assert audit.status == "FAIL"


def test_detects_unused_definition(tmp_path: Path) -> None:
    audit = _audit(tmp_path, 'acl "unused" { 192.0.2.1; };\n')
    assert audit.status == "WARN"
    assert audit.findings[0].code == "UNUSED_DEFINITION"


def test_clean_configuration_passes(tmp_path: Path) -> None:
    audit = _audit(
        tmp_path,
        'acl "trusted" { localhost; 192.0.2.0/24; };\n'
        'options { allow-query { trusted; }; };\n',
    )
    assert audit.status == "PASS"
    assert audit.findings == ()
