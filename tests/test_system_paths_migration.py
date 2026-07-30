from pathlib import Path

from tools.migrations.m001_system_paths import (
    PathPlan,
    migration_plan,
    rewrite_legacy_paths,
)


def test_rewrite_legacy_paths_updates_known_roots() -> None:
    original = (
        "state_dir = /var/lib/elkman-dns-toolkit\n"
        "audit_log = /var/log/elkman-dns-toolkit/audit.jsonl\n"
        "backup_dir = /var/backups/elkman-dns\n"
        "config = /etc/elkman-dns-toolkit/toolkit.conf\n"
        "bind_dir = /etc/bind\n"
    )

    assert rewrite_legacy_paths(original) == (
        "state_dir = /var/lib/zonectl\n"
        "audit_log = /var/log/zonectl/audit.jsonl\n"
        "backup_dir = /var/backups/zonectl\n"
        "config = /etc/zonectl/toolkit.conf\n"
        "bind_dir = /etc/bind\n"
    )


def test_migration_plan_reports_existing_paths(
    tmp_path: Path,
) -> None:
    source = tmp_path / "old"
    target = tmp_path / "new"
    source.mkdir()

    assert migration_plan(((source, target),)) == [
        PathPlan(
            source=source,
            target=target,
            source_exists=True,
            target_exists=False,
        )
    ]


def test_rewrite_is_idempotent() -> None:
    current = "config = /etc/zonectl/toolkit.conf\n"

    assert rewrite_legacy_paths(current) == current
