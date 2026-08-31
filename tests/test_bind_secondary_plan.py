from pathlib import Path

import pytest

from zonectl.core.bind_secondary_plan import (
    BindSecondaryPlanError,
    BindSecondaryPlanner,
)


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "named.conf"
    root.write_text(
        "primaries dns2-notify { 192.0.2.53; };\n"
        'acl "dns2-transfer" { 192.0.2.54; };\n'
        'zone "a" { type primary; file "/a"; '
        "also-notify { dns2-notify; }; allow-transfer { dns2-transfer; }; };\n",
        encoding="utf-8",
    )
    return root


def test_plan_reports_impact_and_minimal_diff(tmp_path: Path, monkeypatch) -> None:
    root = _root(tmp_path)
    monkeypatch.setattr(
        BindSecondaryPlanner,
        "_validate_candidate",
        lambda self, source, candidate: (True, "kod 0"),
    )
    before = root.read_bytes()
    plan = BindSecondaryPlanner(root).plan(
        "dns2-notify", ["192.0.2.60", "2001:db8::53"]
    )
    assert plan.old_addresses == ("192.0.2.53",)
    assert plan.new_addresses == ("192.0.2.60", "2001:db8::53")
    assert plan.roles == ("notify",)
    assert plan.zones == ("a",)
    assert "192.0.2.60" in plan.diff
    assert root.read_bytes() == before
    assert plan.impact is not None
    assert plan.impact.roles == ("notify",)
    assert plan.impact.zones == ("a",)
    assert plan.impact.risk == "MEDIUM"


@pytest.mark.parametrize("addresses", [[], ["bad"], ["192.0.2.1", "192.0.2.1"]])
def test_plan_rejects_empty_invalid_or_duplicate_addresses(
    tmp_path: Path, addresses
) -> None:
    with pytest.raises(BindSecondaryPlanError):
        BindSecondaryPlanner(_root(tmp_path)).plan("dns2-notify", addresses)


def test_plan_rejects_non_secondary_acl(tmp_path: Path) -> None:
    root = tmp_path / "named.conf"
    root.write_text('acl "trusted" { localhost; };\n', encoding="utf-8")
    with pytest.raises(BindSecondaryPlanError, match="secondary"):
        BindSecondaryPlanner(root).plan("trusted", ["192.0.2.1"])
