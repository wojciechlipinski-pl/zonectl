from pathlib import Path

from zonectl.core.bind_zone_secondary import BindZoneSecondaryPlanner


def _config(tmp_path: Path) -> Path:
    root = tmp_path / "named.conf"
    root.write_text(
        'primaries dns2-notify { 192.0.2.53; };\n'
        'acl dns2-transfer { 192.0.2.53; };\n'
        'primaries he-notify { 192.0.2.54; };\n'
        'acl he-transfer { 192.0.2.55; };\n'
        'zone "example.pl" { type primary; file "/tmp/example";\n'
        ' also-notify { dns2-notify; };\n'
        ' allow-transfer { dns2-transfer; };\n};\n', encoding="utf-8"
    )
    return root


def test_plan_assigns_complete_logical_pairs(tmp_path: Path, monkeypatch) -> None:
    root = _config(tmp_path)
    monkeypatch.setattr(
        BindZoneSecondaryPlanner, "available_pairs",
        lambda self: __import__("zonectl.core.bind_secondary_report", fromlist=["BindSecondaryReporter"])
        .BindSecondaryReporter().build(
            __import__("zonectl.core.bind_access_inventory", fromlist=["BindAccessInventoryReader"])
            .BindAccessInventoryReader(root).collect()
        ).pairs,
    )
    monkeypatch.setattr(
        "zonectl.core.bind_secondary_plan.BindSecondaryPlanner._validate_candidate",
        lambda self, source, candidate: (True, "kod 0"),
    )
    plan = BindZoneSecondaryPlanner(root).plan("example.pl", ["dns2", "he"])
    assert plan.old_pairs == ("dns2",)
    assert "he-notify" in plan.candidate_text
    assert "he-transfer" in plan.candidate_text
    assert plan.impact.risk == "LOW"
    assert root.read_text() == plan.original_text


def test_transaction_adapter_preserves_audit_context(tmp_path: Path, monkeypatch) -> None:
    root = _config(tmp_path)
    monkeypatch.setattr(
        "zonectl.core.bind_secondary_plan.BindSecondaryPlanner._validate_candidate",
        lambda self, source, candidate: (True, "kod 0"),
    )
    plan = BindZoneSecondaryPlanner(root).plan("example.pl", ["dns2"])
    adapted = plan.transaction_plan()
    assert adapted.zones == ("example.pl",)
    assert adapted.old_addresses == ("dns2",)
    assert adapted.new_addresses == ("dns2",)
    assert adapted.impact is plan.impact
    assert adapted.operational_addresses == ("192.0.2.53",)


def test_removing_last_secondary_pair_is_high_risk(
    tmp_path: Path, monkeypatch
) -> None:
    root = _config(tmp_path)
    monkeypatch.setattr(
        "zonectl.core.bind_secondary_plan.BindSecondaryPlanner._validate_candidate",
        lambda self, source, candidate: (True, "kod 0"),
    )

    plan = BindZoneSecondaryPlanner(root).plan("example.pl", [])

    assert plan.old_pairs == ("dns2",)
    assert plan.new_pairs == ()
    assert plan.impact.risk == "HIGH"
    assert plan.impact.removed_entries == ("dns2",)
