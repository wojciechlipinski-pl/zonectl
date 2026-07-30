"""Centralne ścieżki systemowe ZoneCTL.

Ten moduł jest jedynym źródłem domyślnych ścieżek używanych przez kod
Pythona. Na tym etapie zachowujemy dotychczasowe katalogi systemowe.
Ich migracja do przestrzeni nazw ZoneCTL zostanie wykonana osobno,
z backupem i możliwością wycofania.
"""

from pathlib import Path


CONFIG_DIR = Path("/etc/elkman-dns-toolkit")
STATE_DIR = Path("/var/lib/elkman-dns-toolkit")
LOG_DIR = Path("/var/log/elkman-dns-toolkit")
BACKUP_DIR = Path("/var/backups/elkman-dns")
APP_ROOT = Path("/opt/zonectl")

DEFAULT_CONFIG = CONFIG_DIR / "toolkit.conf"
DEFAULT_ZONES = CONFIG_DIR / "zones.conf"
DEFAULT_GROUPS = CONFIG_DIR / "groups.yaml"

TRANSACTION_BACKUP_DIR = STATE_DIR / "backups"
TRANSACTION_DIR = STATE_DIR / "transactions"
LOCK_DIR = STATE_DIR / "locks"
DNSSEC_DS_DIR = STATE_DIR / "ds"
AUDIT_LOG = LOG_DIR / "audit.jsonl"
