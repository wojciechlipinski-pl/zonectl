from pathlib import Path

from zonectl.core.bind_access_inventory import BindAccessInventoryReader
from zonectl.core.bind_secondary_report import BindSecondaryReporter


def _report(tmp_path: Path, text: str):
    root = tmp_path / "named.conf"
    root.write_text(text, encoding="utf-8")
    inventory = BindAccessInventoryReader(root).collect()
    return BindSecondaryReporter().build(inventory)


def test_pairs_notify_and_transfer_and_lists_impacted_zones(tmp_path: Path) -> None:
    report = _report(
        tmp_path,
        "primaries dns2-notify { 192.0.2.53; };\n"
        'acl "dns2-transfer" { 192.0.2.54; };\n'
        'zone "a.example" { type primary; file "/a"; '
        "also-notify { dns2-notify; }; allow-transfer { dns2-transfer; }; };\n"
        'zone "b.example" { type primary; file "/b"; '
        "also-notify { dns2-notify; }; allow-transfer { dns2-transfer; }; };\n",
    )
    pair = report.pairs[0]
    assert pair.name == "dns2"
    assert pair.status == "PASS"
    assert pair.notify_addresses == ("192.0.2.53",)
    assert pair.transfer_addresses == ("192.0.2.54",)
    assert pair.zones == ("a.example", "b.example")
    groups = {item.name: item for item in report.groups}
    assert groups["dns2-notify"].usage_count == 2
    assert groups["dns2-transfer"].roles == ("transfer",)


def test_missing_pair_role_is_warning(tmp_path: Path) -> None:
    report = _report(
        tmp_path,
        "primaries he-notify { 192.0.2.53; };\n"
        'zone "a.example" { type primary; file "/a"; '
        "also-notify { he-notify; }; };\n",
    )
    assert report.pairs[0].status == "WARN"
    assert report.pairs[0].transfer_groups == ()


def test_json_payload_is_serializable_shape(tmp_path: Path) -> None:
    report = _report(
        tmp_path,
        'acl "dns2-transfer" { 192.0.2.54; };\n'
        'zone "a" { type primary; file "/a"; '
        "allow-transfer { dns2-transfer; }; };\n",
    )
    payload = report.to_dict()
    assert payload["groups"][0]["entries"] == ["192.0.2.54"]
    assert payload["pairs"][0]["status"] == "WARN"
