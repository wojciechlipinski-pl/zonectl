from pathlib import Path

import pytest

from zonectl.core.discovery import (
    BindConfigDiscovery,
    BindDiscoveryError,
)


def test_discovers_zone_from_included_file(tmp_path: Path) -> None:
    zones_dir = tmp_path / "zones"
    zones_dir.mkdir()

    zone_file = tmp_path / "db.example.pl"
    zone_file.write_text(
        "$TTL 3600\n"
        "@ IN SOA ns1.example.pl. hostmaster.example.pl. "
        "2026072901 3600 900 1209600 3600\n",
        encoding="utf-8",
    )

    root = tmp_path / "named.conf"
    local = tmp_path / "named.conf.local"
    zone_config = zones_dir / "example.pl.conf"

    root.write_text(
        'include "named.conf.local";\n',
        encoding="utf-8",
    )

    local.write_text(
        'include "zones/example.pl.conf";\n',
        encoding="utf-8",
    )

    zone_config.write_text(
        f'''
        zone "example.pl" {{
            type primary;
            file "{zone_file}";
            dnssec-policy default;
            inline-signing yes;
            key-directory "/var/lib/bind/keys";
        }};
        ''',
        encoding="utf-8",
    )

    result = BindConfigDiscovery(root).discover()
    zone = result.zone("example.pl")

    assert zone.name == "example.pl"
    assert zone.zone_type == "primary"
    assert zone.source_file == zone_file.resolve()
    assert zone.config_file == zone_config.resolve()
    assert zone.dnssec_policy == "default"
    assert zone.inline_signing is True
    assert zone.dnssec_enabled is True
    assert zone.source_exists is True
    assert zone.is_primary is True
    assert zone.save_mode == "ATOMIC_REPLACE_RELOAD"


def test_detects_source_journal(tmp_path: Path) -> None:
    zone_file = tmp_path / "example.pl"
    zone_file.write_text("test\n", encoding="utf-8")
    Path(f"{zone_file}.jnl").write_text("journal\n", encoding="utf-8")

    config = tmp_path / "named.conf"
    config.write_text(
        f'''
        zone "example.pl" {{
            type master;
            file "{zone_file}";
            inline-signing yes;
        }};
        ''',
        encoding="utf-8",
    )

    zone = BindConfigDiscovery(config).discover().zone("example.pl")

    assert zone.journal_exists is True
    assert zone.requires_freeze is True
    assert zone.save_mode == "FREEZE_SYNC_REPLACE_THAW"


def test_signed_journal_alone_does_not_require_freeze(
    tmp_path: Path,
) -> None:
    zone_file = tmp_path / "example.pl"
    zone_file.write_text("test\n", encoding="utf-8")
    Path(f"{zone_file}.signed.jnl").write_text(
        "signed journal\n",
        encoding="utf-8",
    )

    config = tmp_path / "named.conf"
    config.write_text(
        f'''
        zone "example.pl" {{
            type master;
            file "{zone_file}";
            inline-signing yes;
        }};
        ''',
        encoding="utf-8",
    )

    zone = BindConfigDiscovery(config).discover().zone("example.pl")

    assert zone.signed_journal_exists is True
    assert zone.journal_exists is False
    assert zone.requires_freeze is False
    assert zone.save_mode == "ATOMIC_REPLACE_RELOAD"


def test_rejects_signed_file_as_source(tmp_path: Path) -> None:
    signed_file = tmp_path / "example.pl.signed"
    signed_file.write_text("signed\n", encoding="utf-8")

    config = tmp_path / "named.conf"
    config.write_text(
        f'''
        zone "example.pl" {{
            type master;
            file "{signed_file}";
        }};
        ''',
        encoding="utf-8",
    )

    zone = BindConfigDiscovery(config).discover().zone("example.pl")

    assert zone.is_managed_signed_file is True
    assert zone.editable is False
    assert zone.save_mode == "REJECT_SIGNED_FILE"


def test_secondary_zone_is_read_only(tmp_path: Path) -> None:
    zone_file = tmp_path / "secondary.example"
    zone_file.write_text("test\n", encoding="utf-8")

    config = tmp_path / "named.conf"
    config.write_text(
        f'''
        zone "example.pl" {{
            type secondary;
            file "{zone_file}";
        }};
        ''',
        encoding="utf-8",
    )

    zone = BindConfigDiscovery(config).discover().zone("example.pl")

    assert zone.is_secondary is True
    assert zone.editable is False
    assert zone.save_mode == "READ_ONLY"


def test_ignores_commented_zone(tmp_path: Path) -> None:
    config = tmp_path / "named.conf"
    config.write_text(
        """
        // zone "commented-one.pl" {
        //     type master;
        //     file "/tmp/commented-one.pl";
        // };

        /*
        zone "commented-two.pl" {
            type master;
            file "/tmp/commented-two.pl";
        };
        */

        # zone "commented-three.pl" { type master; };

        zone "active.pl" {
            type master;
            file "/tmp/active.pl";
        };
        """,
        encoding="utf-8",
    )

    result = BindConfigDiscovery(config).discover()

    assert [zone.name for zone in result.zones] == ["active.pl"]


def test_duplicate_zone_is_reported(tmp_path: Path) -> None:
    config = tmp_path / "named.conf"
    config.write_text(
        """
        zone "example.pl" {
            type master;
            file "/tmp/first";
        };

        zone "example.pl" {
            type master;
            file "/tmp/second";
        };
        """,
        encoding="utf-8",
    )

    result = BindConfigDiscovery(config).discover()

    with pytest.raises(BindDiscoveryError, match="kilka aktywnych"):
        result.zone("example.pl")


def test_missing_include_is_reported(tmp_path: Path) -> None:
    config = tmp_path / "named.conf"
    config.write_text(
        'include "missing.conf";\n',
        encoding="utf-8",
    )

    with pytest.raises(BindDiscoveryError, match="nie istnieje"):
        BindConfigDiscovery(config).discover()


def test_include_loop_is_reported(tmp_path: Path) -> None:
    first = tmp_path / "first.conf"
    second = tmp_path / "second.conf"

    first.write_text(
        'include "second.conf";\n',
        encoding="utf-8",
    )

    second.write_text(
        'include "first.conf";\n',
        encoding="utf-8",
    )

    with pytest.raises(BindDiscoveryError, match="zapętlenie"):
        BindConfigDiscovery(first).discover()
