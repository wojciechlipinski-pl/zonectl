from pathlib import Path

from elkman_dns.core import paths
from elkman_dns.core.config import (
    DEFAULT_CONFIG,
    DEFAULT_GROUPS,
    DEFAULT_ZONES,
)


def test_legacy_system_paths_are_centralised() -> None:
    assert paths.CONFIG_DIR == Path("/etc/elkman-dns-toolkit")
    assert paths.STATE_DIR == Path("/var/lib/elkman-dns-toolkit")
    assert paths.LOG_DIR == Path("/var/log/elkman-dns-toolkit")
    assert paths.BACKUP_DIR == Path("/var/backups/elkman-dns")
    assert paths.APP_ROOT == Path("/opt/zonectl")


def test_config_defaults_come_from_central_paths() -> None:
    assert DEFAULT_CONFIG is paths.DEFAULT_CONFIG
    assert DEFAULT_ZONES is paths.DEFAULT_ZONES
    assert DEFAULT_GROUPS is paths.DEFAULT_GROUPS


def test_transaction_paths_share_state_and_log_roots() -> None:
    assert paths.TRANSACTION_BACKUP_DIR == paths.STATE_DIR / "backups"
    assert paths.TRANSACTION_DIR == paths.STATE_DIR / "transactions"
    assert paths.LOCK_DIR == paths.STATE_DIR / "locks"
    assert paths.DNSSEC_DS_DIR == paths.STATE_DIR / "ds"
    assert paths.AUDIT_LOG == paths.LOG_DIR / "audit.jsonl"
