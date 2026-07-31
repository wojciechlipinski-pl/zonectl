from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from zonectl.core.models import Zone
from zonectl.core.zone_lifecycle import (
    ZoneCreateRequest,
    ZoneLifecycleError,
    ZoneLifecyclePlanner,
    normalize_zone_name,
)


def planner(*names: str) -> ZoneLifecyclePlanner:
    return ZoneLifecyclePlanner(
        [Zone(name=name, file=Path(f"/zones/{name}")) for name in names],
        today_provider=lambda: date(2026, 7, 31),
    )


def request(**changes) -> ZoneCreateRequest:
    values = {
        "name": "example.pl",
        "primary_ns": "ns1.elkman.pl.",
        "admin": "hostmaster.elkman.pl.",
        "nameservers": ("ns1.elkman.pl.", "ns2.elkman.pl."),
    }
    values.update(changes)
    return ZoneCreateRequest(**values)


@pytest.mark.parametrize(
    "value",
    ["", "localhost", "-bad.pl", "bad-.pl", "bad_thing.pl"],
)
def test_invalid_zone_names_are_rejected(value: str) -> None:
    with pytest.raises(ZoneLifecycleError):
        normalize_zone_name(value)


def test_existing_zone_is_rejected_case_insensitively() -> None:
    with pytest.raises(ZoneLifecycleError, match="już istnieje"):
        planner("Example.PL").plan_create(request())


def test_plan_is_deterministic_and_has_no_side_effects(
    tmp_path: Path,
) -> None:
    zone_directory = tmp_path / "zones"
    managed_config = tmp_path / "zonectl-zones.conf"

    plan = planner().plan_create(
        request(
            zone_directory=zone_directory,
            managed_config=managed_config,
            managed_zone_directory=tmp_path / "zonectl-zones.d",
            apex_ipv4="192.0.2.10",
            apex_ipv6="2001:db8::10",
            add_www=True,
        )
    )

    assert plan.zone_name == "example.pl"
    assert plan.serial == 2026073100
    assert plan.zone_file == zone_directory.resolve() / "example.pl"
    assert "@ IN SOA ns1.elkman.pl. hostmaster.elkman.pl." in plan.zone_text
    assert "@ IN NS ns2.elkman.pl." in plan.zone_text
    assert "www IN A 192.0.2.10" in plan.zone_text
    assert "www IN AAAA 2001:db8::10" in plan.zone_text
    assert 'zone "example.pl" IN {' in plan.bind_declaration
    assert plan.zone_declaration_file == (
        tmp_path / "zonectl-zones.d" / "example.pl.conf"
    ).resolve()
    assert not zone_directory.exists()
    assert not managed_config.exists()


def test_primary_ns_must_be_listed() -> None:
    with pytest.raises(ZoneLifecycleError, match="primary_ns"):
        planner().plan_create(
            request(nameservers=("ns2.elkman.pl.",))
        )


def test_www_requires_an_apex_address() -> None:
    with pytest.raises(ZoneLifecycleError, match="www"):
        planner().plan_create(request(add_www=True))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("apex_ipv4", "999.1.1.1", "IPv4"),
        ("apex_ipv4", "2001:db8::1", "IPv4"),
        ("apex_ipv6", "192.0.2.1", "IPv6"),
    ],
)
def test_address_family_is_validated(
    field: str,
    value: str,
    message: str,
) -> None:
    with pytest.raises(ZoneLifecycleError, match=message):
        planner().plan_create(request(**{field: value}))
