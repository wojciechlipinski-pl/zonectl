from pathlib import Path

from zonectl.core.bind_access_impact import BindAccessImpactReporter
from zonectl.core.bind_access_inventory import BindAccessInventoryReader


def _impact(tmp_path: Path, text: str, name: str, entries=None):
    root = tmp_path / "named.conf"
    root.write_text(text, encoding="utf-8")
    inventory = BindAccessInventoryReader(root).collect()
    return BindAccessImpactReporter().build(inventory, name, entries)


def test_reports_direct_and_nested_roles_and_zones(tmp_path: Path) -> None:
    report = _impact(
        tmp_path,
        'acl "operators" { localhost; };\n'
        'acl "trusted" { operators; 192.0.2.0/24; };\n'
        "options { allow-recursion { trusted; }; };\n"
        'zone "dynamic.invalid" { type primary; file "/dynamic"; '
        "allow-update { operators; }; };\n"
        'zone "example.invalid" { type primary; file "/zone"; '
        "allow-transfer { trusted; }; };\n",
        "operators",
        ("localhost", "198.51.100.10"),
    )
    assert report.roles == ("administration", "recursion", "transfer")
    assert report.zones == ("dynamic.invalid", "example.invalid")
    assert report.dependent_definitions == ("trusted",)
    assert report.added_entries == ("198.51.100.10",)
    assert report.risk == "LOW"
    assert {usage.directive for usage in report.usages} == {
        "allow-update",
        "allow-recursion",
        "allow-transfer",
    }


def test_removal_from_administrative_acl_is_high_risk(tmp_path: Path) -> None:
    report = _impact(
        tmp_path,
        'acl "operators" { localhost; 192.0.2.10; };\n'
        'zone "dynamic.invalid" { type primary; file "/dynamic"; '
        "allow-update { operators; }; };\n",
        "operators",
        ("localhost",),
    )
    assert report.removed_entries == ("192.0.2.10",)
    assert report.risk == "HIGH"


def test_cycle_is_reported_as_indeterminate_blocker(tmp_path: Path) -> None:
    report = _impact(
        tmp_path,
        'acl "a" { b; };\nacl "b" { a; };\noptions { allow-query { a; }; };\n',
        "a",
    )
    assert report.risk == "INDETERMINATE"
    assert report.blockers
    assert "a -> b -> a" in report.blockers[0]


def test_unchanged_used_definition_has_no_change_risk(tmp_path: Path) -> None:
    report = _impact(
        tmp_path,
        'acl "trusted" { localhost; 192.0.2.0/24; };\n'
        "options { allow-recursion { trusted; }; };\n",
        "trusted",
    )
    assert report.roles == ("recursion",)
    assert report.risk == "NONE"
    assert report.added_entries == ()
    assert report.removed_entries == ()


def test_removing_all_remote_query_clients_is_high_risk(tmp_path: Path) -> None:
    report = _impact(
        tmp_path,
        'acl "trusted" { localhost; 192.0.2.0/24; 2001:db8::/32; };\n'
        "options { allow-query { trusted; }; allow-recursion { trusted; }; };\n",
        "trusted",
        ("localhost",),
    )
    assert report.removed_entries == ("192.0.2.0/24", "2001:db8::/32")
    assert report.risk == "HIGH"


def test_query_acl_with_remaining_remote_network_is_medium_risk(
    tmp_path: Path,
) -> None:
    report = _impact(
        tmp_path,
        'acl "trusted" { localhost; 192.0.2.0/24; 198.51.100.0/24; };\n'
        "options { allow-recursion { trusted; }; };\n",
        "trusted",
        ("localhost", "198.51.100.0/24"),
    )
    assert report.risk == "MEDIUM"


def test_emptying_active_transfer_acl_is_high_risk(tmp_path: Path) -> None:
    report = _impact(
        tmp_path,
        'acl "zone-transfer" { 192.0.2.53; };\n'
        'zone "example.invalid" { type primary; file "/zone"; '
        "allow-transfer { zone-transfer; }; };\n",
        "zone-transfer",
        ("none",),
    )
    assert report.roles == ("transfer",)
    assert report.removed_entries == ("192.0.2.53",)
    assert report.risk == "HIGH"


def test_removing_one_transfer_endpoint_with_another_remaining_is_medium(
    tmp_path: Path,
) -> None:
    report = _impact(
        tmp_path,
        'acl "zone-transfer" { 192.0.2.53; 198.51.100.53; };\n'
        'zone "example.invalid" { type primary; file "/zone"; '
        "allow-transfer { zone-transfer; }; };\n",
        "zone-transfer",
        ("198.51.100.53",),
    )
    assert report.risk == "MEDIUM"
