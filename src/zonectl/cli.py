from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .core.bind import BindService
from .core.bind_access_inventory import (
    BindAccessInventoryError,
    BindAccessInventoryReader,
)
from .core.bind_access_audit import BindAccessAuditor
from .core.bind_access_impact import (
    BindAccessImpactError,
    BindAccessImpactReporter,
)
from .core.bind_environment_report import BindEnvironmentReporter
from .core.rpz_managed_plan import RpzManagedPlanner
from .core.rpz_managed_install import (
    RpzManagedInstallDryRun,
    RpzManagedInstallTransaction,
)
from .core.rpz_external_migration_plan import RpzExternalMigrationPlanner
from .core.rpz_external_migration_dry_run import RpzExternalMigrationDryRun
from .core.rpz_external_migration_transaction import RpzExternalMigrationTransaction
from .core.bind_onboarding_report import BindOnboardingReporter
from .core.discovery import BindDiscoveryError
from .core.bind_acl_plan import BindAclPlanError, BindAclPlanner
from .core.bind_acl_transaction import BindAclTransaction
from .core.bind_secondary_report import BindSecondaryReporter
from .core.bind_secondary_health import BindSecondaryHealthGate
from .core.bind_secondary_plan import (
    BindSecondaryPlanError,
    BindSecondaryPlanner,
)
from .core.bind_secondary_transaction import BindSecondaryTransaction
from .core.bind_zone_secondary import BindZoneSecondaryError, BindZoneSecondaryPlanner
from .core.config import DEFAULT_CONFIG, DEFAULT_GROUPS, DEFAULT_ZONES, ToolkitConfig
from .core.dnssec_enable_plan import (
    DnssecEnablePlanError,
    DnssecEnablePlanner,
)
from .core.dnssec_enable_transaction import DnssecEnableTransaction
from .core.dnssec_disable_transaction import DnssecDisableTransaction
from .core.dnssec_finalize_serial import DnssecFinalizeSerialTransaction
from .core.dnssec_disable_plan import (
    DnssecDisablePlanError,
    DnssecDisablePlanner,
)
from .core.dnssec_withdrawal_backup import DnssecWithdrawalBackup
from .core.dnssec_withdrawal_check import DnssecWithdrawalChecker
from .core.dnssec_withdrawal_confirm import DnssecWithdrawalConfirmTransaction
from .core.dnssec_ds_check import DnssecDsChecker
from .core.dnssec_confirm_ds import DnssecConfirmDsTransaction
from .core.dnssec_guidance import build_dnssec_guidance
from .core.dnssec_report import DnssecReporter
from .core.transaction import TransactionEngine, TransactionResult
from .core.zone_create_transaction import ZoneCreateTransaction
from .core.zone_disable_transaction import (
    ZoneDisableError,
    ZoneDisableTransaction,
)
from .core.zone_restore_transaction import (
    ZoneRestoreError,
    ZoneRestoreTransaction,
)
from .core.zone_quarantine import (
    ZoneQuarantineError,
    ZoneQuarantineTransaction,
)
from .core.zone_quarantine_restore import (
    QuarantineRestoreError,
    QuarantineRestoreTransaction,
)
from .core.zone_lifecycle import (
    ZoneCreateRequest,
    ZoneLifecycleError,
    ZoneLifecyclePlanner,
)
from .core.zone_inventory import ZoneInventory
from .core.zone_quarantine_retention import (
    QuarantineRetentionAuditor,
    format_days_pl,
)
from .core.zone_quarantine_purge import (
    QuarantinePurgeError,
    QuarantinePurgeTransaction,
)
from .core.managed_zone_migration import (
    ManagedZoneMigrationError,
    ManagedZoneMigrationPlanner,
)
from .core.managed_zone_migration_transaction import (
    ManagedZoneMigrationTransaction,
)
from .presentation import transaction_exit_code, transaction_lines
from .ui.curses_app import CursesApp


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="zctl",
        description=f"ZoneCTL {__version__} — Transactional DNS Management Toolkit",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--zones", type=Path, default=DEFAULT_ZONES)
    p.add_argument("--groups", type=Path, default=DEFAULT_GROUPS)
    sub = p.add_subparsers(dest="command")
    sub.add_parser("tui", help="uruchom interfejs terminalowy")
    domains = sub.add_parser("domains", help="wyświetl listę domen")
    domains.add_argument("--grouped", action="store_true", help="pokaż domeny w grupach")
    sub.add_parser("groups", help="wyświetl przypisanie domen do grup")

    bind_config = sub.add_parser("bind", help="odczyt konfiguracji BIND")
    bind_sub = bind_config.add_subparsers(dest="bind_command", required=True)
    bind_inventory = bind_sub.add_parser(
        "inventory", help="pokaż ACL i grupy serwerów secondary bez zmian"
    )
    bind_inventory.add_argument(
        "--root-config", type=Path, default=Path("/etc/bind/named.conf")
    )
    bind_inventory.add_argument("--json", action="store_true")
    bind_audit = bind_sub.add_parser(
        "audit", help="wykryj błędy i ryzyka ACL oraz secondary bez zmian"
    )
    bind_audit.add_argument(
        "--root-config", type=Path, default=Path("/etc/bind/named.conf")
    )
    bind_audit.add_argument("--json", action="store_true")
    bind_environment = bind_sub.add_parser(
        "environment-report",
        help="rozpoznaj BIND i integrację RPZ bez zmian w systemie",
    )
    bind_environment.add_argument(
        "--root-config", type=Path, default=Path("/etc/bind/named.conf")
    )
    bind_environment.add_argument("--rpz-max-age", type=int, default=600)
    bind_environment.add_argument(
        "--timer-unit", default="update-cert-rpz.timer"
    )
    bind_environment.add_argument(
        "--service-unit", default="update-cert-rpz.service"
    )
    bind_environment.add_argument("--json", action="store_true")
    rpz_managed_plan = bind_sub.add_parser(
        "rpz-managed-plan",
        help="pokaż odczytowy plan opcjonalnej integracji CERT Polska RPZ",
    )
    rpz_managed_plan.add_argument(
        "--root-config", type=Path, default=Path("/etc/bind/named.conf")
    )
    rpz_managed_plan.add_argument("--zone", default="cert-rpz.local")
    rpz_managed_plan.add_argument(
        "--source-url",
        default="https://hole.cert.pl/domains/v2/domains_rpz.db",
    )
    rpz_managed_plan.add_argument("--json", action="store_true")
    rpz_managed_dry_run = bind_sub.add_parser(
        "rpz-managed-dry-run",
        help="pobierz i zweryfikuj kandydatów świeżej instalacji RPZ bez zmian",
    )
    rpz_managed_dry_run.add_argument(
        "--root-config", type=Path, default=Path("/etc/bind/named.conf")
    )
    rpz_managed_dry_run.add_argument("--zone", default="cert-rpz.local")
    rpz_managed_dry_run.add_argument(
        "--source-url",
        default="https://hole.cert.pl/domains/v2/domains_rpz.db",
    )
    rpz_managed_dry_run.add_argument("--json", action="store_true")
    rpz_managed_apply = bind_sub.add_parser(
        "rpz-managed-apply",
        help="zainstaluj opcjonalną RPZ; domyślnie wykonaj wyłącznie dry-run",
    )
    rpz_managed_apply.add_argument(
        "--root-config", type=Path, default=Path("/etc/bind/named.conf")
    )
    rpz_managed_apply.add_argument("--zone", default="cert-rpz.local")
    rpz_managed_apply.add_argument(
        "--source-url",
        default="https://hole.cert.pl/domains/v2/domains_rpz.db",
    )
    rpz_managed_apply.add_argument("--commit", action="store_true")
    rpz_managed_apply.add_argument("--activate", action="store_true")
    rpz_managed_apply.add_argument("--confirm")
    rpz_managed_apply.add_argument(
        "--manifest-directory", type=Path,
        default=Path("/var/backups/zonectl-rpz/manifests"),
    )
    rpz_managed_apply.add_argument("--json", action="store_true")
    rpz_migration_plan = bind_sub.add_parser(
        "rpz-external-migration-plan",
        help="zinwentaryzuj odczytowo migrację RPZ z EXTERNAL do MANAGED",
    )
    rpz_migration_plan.add_argument(
        "--root-config", type=Path, default=Path("/etc/bind/named.conf")
    )
    rpz_migration_plan.add_argument("--json", action="store_true")
    rpz_migration_dry_run = bind_sub.add_parser(
        "rpz-external-migration-dry-run",
        help="zweryfikuj migrację RPZ w katalogu tymczasowym bez przełączenia",
    )
    rpz_migration_dry_run.add_argument(
        "--root-config", type=Path, default=Path("/etc/bind/named.conf")
    )
    rpz_migration_dry_run.add_argument("--json", action="store_true")
    rpz_migration_apply = bind_sub.add_parser(
        "rpz-external-migration-apply",
        help="migracja RPZ EXTERNAL do MANAGED; domyślnie bezpieczny dry-run",
    )
    rpz_migration_apply.add_argument(
        "--root-config", type=Path, default=Path("/etc/bind/named.conf")
    )
    rpz_migration_apply.add_argument("--commit", action="store_true")
    rpz_migration_apply.add_argument("--activate", action="store_true")
    rpz_migration_apply.add_argument("--confirm")
    rpz_migration_apply.add_argument(
        "--backup-root", type=Path,
        default=Path("/var/backups/zonectl-rpz/migrations"),
    )
    rpz_migration_apply.add_argument(
        "--manifest-directory", type=Path,
        default=Path("/var/backups/zonectl-rpz/manifests"),
    )
    rpz_migration_apply.add_argument("--json", action="store_true")
    bind_onboarding = bind_sub.add_parser(
        "onboarding-report",
        help="oceń gotowość istniejącego BIND do bezpiecznego importu",
    )
    bind_onboarding.add_argument(
        "--root-config", type=Path, default=Path("/etc/bind/named.conf")
    )
    bind_onboarding.add_argument("--json", action="store_true")
    bind_acl_plan = bind_sub.add_parser(
        "acl-plan", help="pokaż zwalidowany plan uporządkowania jednej ACL"
    )
    bind_acl_plan.add_argument("name")
    bind_acl_plan.add_argument(
        "--replace", action="append", default=[], metavar="STARY=NOWY"
    )
    bind_acl_plan.add_argument(
        "--entry", action="append", dest="entries",
        help="element pełnej docelowej listy ACL; opcję można powtarzać",
    )
    bind_acl_plan.add_argument("--keep-duplicates", action="store_true")
    bind_acl_plan.add_argument(
        "--root-config", type=Path, default=Path("/etc/bind/named.conf")
    )
    bind_acl_plan.add_argument("--json", action="store_true")
    bind_access_impact = bind_sub.add_parser(
        "access-impact",
        help="pokaż odczytowo zależności i wpływ zmiany ACL/secondary",
    )
    bind_access_impact.add_argument("name")
    bind_access_impact.add_argument(
        "--entry", action="append", dest="entries",
        help="element rozważanej listy docelowej; opcję można powtarzać",
    )
    bind_access_impact.add_argument(
        "--root-config", type=Path, default=Path("/etc/bind/named.conf")
    )
    bind_access_impact.add_argument("--json", action="store_true")
    bind_acl_apply = bind_sub.add_parser(
        "acl-apply", help="transakcyjnie zastosuj plan ACL; domyślnie dry-run"
    )
    bind_acl_apply.add_argument("name")
    bind_acl_apply.add_argument(
        "--replace", action="append", default=[], metavar="STARY=NOWY"
    )
    bind_acl_apply.add_argument(
        "--entry", action="append", dest="entries",
        help="element pełnej docelowej listy ACL; opcję można powtarzać",
    )
    bind_acl_apply.add_argument("--keep-duplicates", action="store_true")
    bind_acl_apply.add_argument("--confirm")
    bind_acl_apply.add_argument("--reason", help="uzasadnienie zapisywane w manifeście")
    bind_acl_apply.add_argument("--commit", action="store_true")
    bind_acl_apply.add_argument("--activate", action="store_true")
    bind_acl_apply.add_argument(
        "--root-config", type=Path, default=Path("/etc/bind/named.conf")
    )
    bind_acl_apply.add_argument(
        "--backup-root", type=Path,
        default=Path("/var/backups/zonectl-bind-acl/backups"),
    )
    bind_acl_apply.add_argument(
        "--manifest-directory", type=Path,
        default=Path("/var/backups/zonectl-bind-acl/manifests"),
    )
    bind_acl_apply.add_argument("--json", action="store_true")
    bind_secondary = bind_sub.add_parser(
        "secondary-report",
        help="pokaż grupy notify/transfer i korzystające strefy bez zmian",
    )
    bind_secondary.add_argument(
        "--root-config", type=Path, default=Path("/etc/bind/named.conf")
    )
    bind_secondary.add_argument("--json", action="store_true")
    bind_secondary_health = bind_sub.add_parser(
        "secondary-health",
        help="sprawdź AA i SOA stref na skonfigurowanych secondary bez zmian",
    )
    bind_secondary_health.add_argument(
        "--pair", action="append", dest="pairs",
        help="ogranicz audyt do wskazanej pary logicznej; można powtarzać",
    )
    bind_secondary_health.add_argument(
        "--root-config", type=Path, default=Path("/etc/bind/named.conf")
    )
    bind_secondary_health.add_argument("--json", action="store_true")
    bind_secondary_plan = bind_sub.add_parser(
        "secondary-plan", help="pokaż zwalidowany plan zmiany jednej grupy"
    )
    bind_secondary_plan.add_argument("name")
    bind_secondary_plan.add_argument(
        "--address", action="append", required=True, dest="addresses"
    )
    bind_secondary_plan.add_argument(
        "--root-config", type=Path, default=Path("/etc/bind/named.conf")
    )
    bind_secondary_plan.add_argument("--json", action="store_true")
    bind_secondary_apply = bind_sub.add_parser(
        "secondary-apply",
        help="transakcyjnie zastosuj zmianę grupy; domyślnie dry-run",
    )
    bind_secondary_apply.add_argument("name")
    bind_secondary_apply.add_argument(
        "--address", action="append", required=True, dest="addresses"
    )
    bind_secondary_apply.add_argument("--confirm")
    bind_secondary_apply.add_argument("--reason", help="uzasadnienie zapisywane w manifeście")
    bind_secondary_apply.add_argument("--commit", action="store_true")
    bind_secondary_apply.add_argument("--activate", action="store_true")
    bind_secondary_apply.add_argument(
        "--root-config", type=Path, default=Path("/etc/bind/named.conf")
    )
    bind_secondary_apply.add_argument(
        "--backup-root", type=Path,
        default=Path("/var/backups/zonectl-bind-secondary/backups"),
    )
    bind_secondary_apply.add_argument(
        "--manifest-directory", type=Path,
        default=Path("/var/backups/zonectl-bind-secondary/manifests"),
    )
    bind_secondary_apply.add_argument("--json", action="store_true")
    bind_zone_secondary_plan = bind_sub.add_parser(
        "zone-secondary-plan", help="pokaż plan przypisania strefy do par secondary"
    )
    bind_zone_secondary_plan.add_argument("zone")
    bind_zone_secondary_plan.add_argument("--pair", action="append", default=[], dest="pairs")
    bind_zone_secondary_plan.add_argument("--root-config", type=Path, default=Path("/etc/bind/named.conf"))
    bind_zone_secondary_plan.add_argument("--json", action="store_true")
    bind_zone_secondary_apply = bind_sub.add_parser(
        "zone-secondary-apply", help="transakcyjnie przypisz strefę do par secondary"
    )
    bind_zone_secondary_apply.add_argument("zone")
    bind_zone_secondary_apply.add_argument("--pair", action="append", default=[], dest="pairs")
    bind_zone_secondary_apply.add_argument("--confirm")
    bind_zone_secondary_apply.add_argument("--reason", help="uzasadnienie zapisywane w manifeście")
    bind_zone_secondary_apply.add_argument("--commit", action="store_true")
    bind_zone_secondary_apply.add_argument("--activate", action="store_true")
    bind_zone_secondary_apply.add_argument("--root-config", type=Path, default=Path("/etc/bind/named.conf"))
    bind_zone_secondary_apply.add_argument("--backup-root", type=Path, default=Path("/var/backups/zonectl-bind-secondary/backups"))
    bind_zone_secondary_apply.add_argument("--manifest-directory", type=Path, default=Path("/var/backups/zonectl-bind-secondary/manifests"))
    bind_zone_secondary_apply.add_argument("--json", action="store_true")

    dnssec = sub.add_parser(
        "dnssec",
        help="odczytowy raport i przyszłe operacje DNSSEC",
    )
    dnssec_sub = dnssec.add_subparsers(dest="dnssec_command", required=True)
    dnssec_report = dnssec_sub.add_parser(
        "report",
        help="pokaż konfigurację, DNSKEY, RRSIG i DS bez wykonywania zmian",
    )
    dnssec_report.add_argument("name")
    dnssec_report.add_argument("--server")
    dnssec_report.add_argument("--resolver", default="1.1.1.1")
    dnssec_report.add_argument("--json", action="store_true")
    dnssec_check_ds = dnssec_sub.add_parser(
        "check-ds",
        help="sprawdź DS i zgodność serwerów autorytatywnych bez zmian",
    )
    dnssec_check_ds.add_argument("name")
    dnssec_check_ds.add_argument("--server")
    dnssec_check_ds.add_argument(
        "--resolver",
        action="append",
        dest="resolvers",
        help="resolver do kontroli DS; opcję można podać wielokrotnie",
    )
    dnssec_check_ds.add_argument("--json", action="store_true")
    dnssec_withdrawal_check = dnssec_sub.add_parser(
        "withdrawal-check",
        help="sprawdź zniknięcie DS na wielu resolwerach; blokuje przedwczesny withdrawn",
    )
    dnssec_withdrawal_check.add_argument("name")
    dnssec_withdrawal_check.add_argument(
        "--resolver",
        action="append",
        dest="resolvers",
        help="resolver do kontroli DS; opcję można podać wielokrotnie",
    )
    dnssec_withdrawal_check.add_argument("--json", action="store_true")
    dnssec_withdrawal_confirm = dnssec_sub.add_parser(
        "withdrawal-confirm",
        help="wykonaj rndc dnssec -checkds withdrawn; domyślnie dry-run",
    )
    dnssec_withdrawal_confirm.add_argument("name")
    dnssec_withdrawal_confirm.add_argument(
        "--resolver", action="append", dest="resolvers"
    )
    dnssec_withdrawal_confirm.add_argument(
        "--manifest-directory",
        type=Path,
        default=Path("/var/backups/zonectl-dnssec-withdrawal-confirm/manifests"),
    )
    dnssec_withdrawal_confirm.add_argument("--commit", action="store_true")
    dnssec_withdrawal_confirm.add_argument(
        "--acknowledge-withdrawn", action="store_true"
    )
    dnssec_withdrawal_confirm.add_argument("--json", action="store_true")
    dnssec_confirm_ds = dnssec_sub.add_parser(
        "confirm-ds",
        help="potwierdź w KASP zweryfikowaną publikację DS; domyślnie dry-run",
    )
    dnssec_confirm_ds.add_argument("name")
    dnssec_confirm_ds.add_argument("--server")
    dnssec_confirm_ds.add_argument(
        "--resolver", action="append", dest="resolvers"
    )
    dnssec_confirm_ds.add_argument(
        "--manifest-directory",
        type=Path,
        default=Path("/var/backups/zonectl-dnssec-confirm-ds/manifests"),
    )
    dnssec_confirm_ds.add_argument("--commit", action="store_true")
    dnssec_confirm_ds.add_argument(
        "--acknowledge-published", action="store_true"
    )
    dnssec_confirm_ds.add_argument("--json", action="store_true")
    dnssec_enable_plan = dnssec_sub.add_parser(
        "enable-plan",
        help="pokaż plan włączenia DNSSEC bez wykonywania zmian",
    )
    dnssec_enable_plan.add_argument("name")
    dnssec_enable_plan.add_argument("--policy", default="default")
    dnssec_enable_plan.add_argument(
        "--key-directory",
        type=Path,
        default=Path("/var/lib/bind/keys"),
    )
    dnssec_enable_plan.add_argument(
        "--zone-directory",
        type=Path,
        default=Path("/var/lib/bind/Primary"),
    )
    dnssec_enable_plan.add_argument("--json", action="store_true")
    dnssec_enable = dnssec_sub.add_parser(
        "enable",
        help="włącz DNSSEC transakcyjnie; domyślnie wykonaj dry-run",
    )
    dnssec_enable.add_argument("name")
    dnssec_enable.add_argument("--policy", default="default")
    dnssec_enable.add_argument(
        "--key-directory", type=Path, default=Path("/var/lib/bind/keys")
    )
    dnssec_enable.add_argument(
        "--zone-directory", type=Path, default=Path("/var/lib/bind/Primary")
    )
    dnssec_enable.add_argument(
        "--backup-root",
        type=Path,
        default=Path("/var/backups/zonectl-dnssec-enable/backups"),
    )
    dnssec_enable.add_argument(
        "--manifest-directory",
        type=Path,
        default=Path("/var/backups/zonectl-dnssec-enable/manifests"),
    )
    dnssec_enable.add_argument(
        "--root-config", type=Path, default=Path("/etc/bind/named.conf")
    )
    dnssec_enable.add_argument("--commit", action="store_true")
    dnssec_enable.add_argument("--activate", action="store_true")
    dnssec_enable.add_argument("--json", action="store_true")
    dnssec_disable_plan = dnssec_sub.add_parser(
        "disable-plan",
        help="pokaż wieloetapowy plan bezpiecznego wycofania DNSSEC bez zmian",
    )
    dnssec_disable_plan.add_argument("name")
    dnssec_disable_plan.add_argument("--json", action="store_true")
    dnssec_disable_apply = dnssec_sub.add_parser(
        "disable-apply",
        help="zastosuj wycofanie DNSSEC transakcyjnie; domyślnie dry-run",
    )
    dnssec_disable_apply.add_argument("name")
    dnssec_disable_apply.add_argument(
        "--stage",
        choices=("insecure", "finalize"),
        default="insecure",
        help="insecure: podmiana polityki; finalize: usunięcie DNSSEC",
    )
    dnssec_disable_apply.add_argument(
        "--resolver", action="append", dest="disable_resolvers"
    )
    dnssec_disable_apply.add_argument(
        "--backup-root",
        type=Path,
        default=Path("/var/backups/zonectl-dnssec-disable/backups"),
    )
    dnssec_disable_apply.add_argument(
        "--manifest-directory",
        type=Path,
        default=Path("/var/backups/zonectl-dnssec-disable/manifests"),
    )
    dnssec_disable_apply.add_argument(
        "--root-config", type=Path, default=Path("/etc/bind/named.conf")
    )
    dnssec_disable_apply.add_argument("--commit", action="store_true")
    dnssec_disable_apply.add_argument("--activate", action="store_true")
    dnssec_disable_apply.add_argument(
        "--acknowledge-unsigned", action="store_true"
    )
    dnssec_disable_apply.add_argument("--json", action="store_true")
    dnssec_finalize_serial = dnssec_sub.add_parser(
        "prepare-finalize-serial",
        help="przygotuj nowszy serial SOA przed finalizacją DNSSEC; domyślnie dry-run",
    )
    dnssec_finalize_serial.add_argument("name")
    dnssec_finalize_serial.add_argument(
        "--backup-root",
        type=Path,
        default=Path("/var/backups/zonectl-dnssec-disable/serial-backups"),
    )
    dnssec_finalize_serial.add_argument("--commit", action="store_true")
    dnssec_finalize_serial.add_argument("--json", action="store_true")
    dnssec_withdrawal_backup = dnssec_sub.add_parser(
        "withdrawal-backup",
        help="utwórz zweryfikowany pakiet przed wycofaniem DNSSEC; domyślnie dry-run",
    )
    dnssec_withdrawal_backup.add_argument("name")
    dnssec_withdrawal_backup.add_argument("--server")
    dnssec_withdrawal_backup.add_argument(
        "--resolver", action="append", dest="resolvers"
    )
    dnssec_withdrawal_backup.add_argument(
        "--backup-root",
        type=Path,
        default=Path("/var/backups/zonectl-dnssec-withdrawal"),
    )
    dnssec_withdrawal_backup.add_argument("--commit", action="store_true")
    dnssec_withdrawal_backup.add_argument("--json", action="store_true")

    lifecycle = sub.add_parser(
        "zone",
        help="zarządzaj cyklem życia stref DNS",
    )
    lifecycle_sub = lifecycle.add_subparsers(
        dest="zone_command",
        required=True,
    )
    create_plan = lifecycle_sub.add_parser(
        "create-plan",
        help="pokaż plan utworzenia strefy bez zmian w systemie",
    )
    create_plan.add_argument("name")
    create_plan.add_argument("--primary-ns", required=True)
    create_plan.add_argument("--admin", required=True)
    create_plan.add_argument(
        "--ns",
        action="append",
        required=True,
        dest="nameservers",
    )
    create_plan.add_argument("--ipv4")
    create_plan.add_argument("--ipv6")
    create_plan.add_argument("--www", action="store_true")
    create_plan.add_argument("--group", default="Pozostałe")
    create_plan.add_argument("--groups-config", type=Path, default=DEFAULT_GROUPS)
    create_plan.add_argument("--refresh", type=int, default=3600)
    create_plan.add_argument("--retry", type=int, default=900)
    create_plan.add_argument("--expire", type=int, default=1209600)
    create_plan.add_argument("--minimum", type=int, default=3600)
    create_plan.add_argument(
        "--zone-directory",
        type=Path,
        default=Path("/var/lib/bind/Primary"),
    )
    create_plan.add_argument(
        "--managed-config",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.conf"),
    )
    create_plan.add_argument(
        "--managed-zone-directory",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.d"),
    )
    create_plan.add_argument("--json", action="store_true")
    create = lifecycle_sub.add_parser(
        "create",
        help="utwórz i aktywuj strefę; bez --commit działa jako dry-run",
    )
    create.add_argument("name")
    create.add_argument("--primary-ns", required=True)
    create.add_argument("--admin", required=True)
    create.add_argument(
        "--ns",
        action="append",
        required=True,
        dest="nameservers",
    )
    create.add_argument("--ipv4")
    create.add_argument("--ipv6")
    create.add_argument("--www", action="store_true")
    create.add_argument("--group", default="Pozostałe")
    create.add_argument("--groups-config", type=Path, default=DEFAULT_GROUPS)
    create.add_argument("--refresh", type=int, default=3600)
    create.add_argument("--retry", type=int, default=900)
    create.add_argument("--expire", type=int, default=1209600)
    create.add_argument("--minimum", type=int, default=3600)
    create.add_argument(
        "--zone-directory",
        type=Path,
        default=Path("/var/lib/bind/Primary"),
    )
    create.add_argument(
        "--managed-config",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.conf"),
    )
    create.add_argument(
        "--managed-zone-directory",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.d"),
    )
    create.add_argument(
        "--root-config",
        type=Path,
        default=Path("/etc/bind/named.conf"),
    )
    create.add_argument(
        "--manifest-directory",
        type=Path,
        default=Path("/var/backups/zonectl-zone-create/manifests"),
    )
    create.add_argument(
        "--commit",
        action="store_true",
        help="zapisz pliki, przeładuj BIND i potwierdź strefę",
    )
    create.add_argument("--json", action="store_true")
    disable = lifecycle_sub.add_parser(
        "disable",
        help="odwracalnie wyłącz strefę; bez --commit działa jako dry-run",
    )
    disable.add_argument("name")
    disable.add_argument("--reason", required=True)
    disable.add_argument(
        "--zone-directory",
        type=Path,
        default=Path("/var/lib/bind/Primary"),
    )
    disable.add_argument(
        "--managed-config",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.conf"),
    )
    disable.add_argument(
        "--managed-zone-directory",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.d"),
    )
    disable.add_argument(
        "--disabled-root",
        type=Path,
        default=Path("/var/lib/zonectl/disabled-zones"),
    )
    disable.add_argument(
        "--manifest-directory",
        type=Path,
        default=Path("/var/backups/zonectl-zone-disable/manifests"),
    )
    disable.add_argument(
        "--root-config",
        type=Path,
        default=Path("/etc/bind/named.conf"),
    )
    disable.add_argument("--commit", action="store_true")
    disable.add_argument("--json", action="store_true")
    restore = lifecycle_sub.add_parser(
        "restore",
        help="przywróć wyłączoną strefę; bez --commit działa jako dry-run",
    )
    restore.add_argument("name")
    restore.add_argument(
        "--zone-directory",
        type=Path,
        default=Path("/var/lib/bind/Primary"),
    )
    restore.add_argument(
        "--managed-config",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.conf"),
    )
    restore.add_argument(
        "--managed-zone-directory",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.d"),
    )
    restore.add_argument(
        "--disabled-root",
        type=Path,
        default=Path("/var/lib/zonectl/disabled-zones"),
    )
    restore.add_argument(
        "--manifest-directory",
        type=Path,
        default=Path("/var/backups/zonectl-zone-restore/manifests"),
    )
    restore.add_argument(
        "--root-config",
        type=Path,
        default=Path("/etc/bind/named.conf"),
    )
    restore.add_argument("--commit", action="store_true")
    restore.add_argument("--json", action="store_true")
    quarantine = lifecycle_sub.add_parser(
        "quarantine",
        help="przenieś wyłączoną strefę do pakietu odtworzeniowego",
    )
    quarantine.add_argument("name")
    quarantine.add_argument("--reason", required=True)
    quarantine.add_argument("--confirm")
    quarantine.add_argument(
        "--zone-directory",
        type=Path,
        default=Path("/var/lib/bind/Primary"),
    )
    quarantine.add_argument(
        "--managed-config",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.conf"),
    )
    quarantine.add_argument(
        "--managed-zone-directory",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.d"),
    )
    quarantine.add_argument(
        "--disabled-root",
        type=Path,
        default=Path("/var/lib/zonectl/disabled-zones"),
    )
    quarantine.add_argument(
        "--quarantine-root",
        type=Path,
        default=Path("/var/lib/zonectl/quarantine"),
    )
    quarantine.add_argument("--commit", action="store_true")
    quarantine.add_argument("--json", action="store_true")
    quarantine_restore = lifecycle_sub.add_parser(
        "quarantine-restore",
        help="odtwórz strefę ze wskazanego pakietu kwarantanny",
    )
    quarantine_restore.add_argument("name")
    quarantine_restore.add_argument(
        "--package", type=Path, required=True
    )
    quarantine_restore.add_argument(
        "--zone-directory",
        type=Path,
        default=Path("/var/lib/bind/Primary"),
    )
    quarantine_restore.add_argument(
        "--managed-config",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.conf"),
    )
    quarantine_restore.add_argument(
        "--managed-zone-directory",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.d"),
    )
    quarantine_restore.add_argument(
        "--root-config",
        type=Path,
        default=Path("/etc/bind/named.conf"),
    )
    quarantine_restore.add_argument("--commit", action="store_true")
    quarantine_restore.add_argument("--json", action="store_true")
    inventory = lifecycle_sub.add_parser(
        "inventory",
        help="pokaż wyłączone strefy i pakiety kwarantanny",
    )
    inventory.add_argument(
        "--disabled-root",
        type=Path,
        default=Path("/var/lib/zonectl/disabled-zones"),
    )
    inventory.add_argument(
        "--quarantine-root",
        type=Path,
        default=Path("/var/lib/zonectl/quarantine"),
    )
    inventory.add_argument(
        "--disable-manifest-directory",
        type=Path,
        default=Path("/var/backups/zonectl-zone-disable/manifests"),
    )
    inventory.add_argument("--json", action="store_true")
    retention = lifecycle_sub.add_parser(
        "quarantine-retention",
        help="pokaż odczytowy plan retencji pakietów kwarantanny",
    )
    retention.add_argument(
        "--quarantine-root",
        type=Path,
        default=Path("/var/lib/zonectl/quarantine"),
    )
    retention.add_argument("--retention-days", type=int, default=90)
    retention.add_argument("--json", action="store_true")
    purge = lifecycle_sub.add_parser(
        "quarantine-purge",
        help="trwale usuń jeden pakiet po retencji; domyślnie dry-run",
    )
    purge.add_argument("name")
    purge.add_argument("--package", type=Path, required=True)
    purge.add_argument("--reason", required=True)
    purge.add_argument("--confirm")
    purge.add_argument("--confirm-package")
    purge.add_argument("--retention-days", type=int, default=90)
    purge.add_argument(
        "--quarantine-root", type=Path,
        default=Path("/var/lib/zonectl/quarantine"),
    )
    purge.add_argument(
        "--audit-directory", type=Path,
        default=Path("/var/backups/zonectl-quarantine-purge/manifests"),
    )
    purge.add_argument(
        "--staging-root", type=Path,
        default=Path("/var/lib/zonectl/purge-staging"),
    )
    purge.add_argument("--commit", action="store_true")
    purge.add_argument("--json", action="store_true")
    safety = lifecycle_sub.add_parser(
        "safety",
        help="pokaż profile bezpieczeństwa stref cyklu życia",
    )
    safety.add_argument("name", nargs="?")
    safety.add_argument("--json", action="store_true")
    migration_inventory = lifecycle_sub.add_parser(
        "migration-inventory",
        help="zinwentaryzuj deklaracje BIND przed migracją do ZoneCTL",
    )
    migration_plan = lifecycle_sub.add_parser(
        "migration-plan",
        help="pokaż odczytowy plan migracji pojedynczej strefy",
    )
    migration_plan.add_argument("name")
    for migration_command in (migration_inventory, migration_plan):
        migration_command.add_argument(
            "--root-config", type=Path, default=Path("/etc/bind/named.conf")
        )
        migration_command.add_argument(
            "--local-config",
            type=Path,
            default=Path("/etc/bind/named.conf.local"),
        )
        migration_command.add_argument(
            "--managed-config",
            type=Path,
            default=Path("/etc/bind/zonectl-zones.conf"),
        )
        migration_command.add_argument(
            "--managed-zone-directory",
            type=Path,
            default=Path("/etc/bind/zonectl-zones.d"),
        )
        migration_command.add_argument("--json", action="store_true")
    migration_apply = lifecycle_sub.add_parser(
        "migration-apply",
        help="transakcyjnie migruj jedną deklarację; domyślnie dry-run",
    )
    migration_apply.add_argument("name")
    migration_apply.add_argument("--confirm")
    migration_apply.add_argument("--commit", action="store_true")
    migration_apply.add_argument("--activate", action="store_true")
    migration_apply.add_argument(
        "--backup-root",
        type=Path,
        default=Path("/var/backups/zonectl-zone-migration/backups"),
    )
    migration_apply.add_argument(
        "--manifest-directory",
        type=Path,
        default=Path("/var/backups/zonectl-zone-migration/manifests"),
    )
    for migration_option in (
        ("--root-config", Path("/etc/bind/named.conf")),
        ("--local-config", Path("/etc/bind/named.conf.local")),
        ("--managed-config", Path("/etc/bind/zonectl-zones.conf")),
        ("--managed-zone-directory", Path("/etc/bind/zonectl-zones.d")),
    ):
        migration_apply.add_argument(
            migration_option[0], type=Path, default=migration_option[1]
        )
    migration_apply.add_argument("--json", action="store_true")

    tx = sub.add_parser("transaction", aliases=["tx"], help="bezpieczne transakcje na plikach stref")
    txsub = tx.add_subparsers(dest="tx_command", required=True)
    check = txsub.add_parser("check", help="sprawdź aktywny lub wskazany plik strefy")
    check.add_argument("zone")
    check.add_argument("--source", type=Path)
    check.add_argument("--json", action="store_true")
    apply = txsub.add_parser("apply", help="zwaliduj i atomowo podmień plik strefy")
    apply.add_argument("zone")
    apply.add_argument("--source", type=Path, required=True)
    apply.add_argument("--commit", action="store_true", help="wykonaj zmianę; bez tej opcji działa dry-run")
    apply.add_argument("--json", action="store_true")

    verify = txsub.add_parser("verify", help="zweryfikuj aktualnie załadowaną strefę")
    verify.add_argument("zone")
    verify.add_argument("--json", action="store_true")

    rollback = txsub.add_parser("rollback", help="przywróć wskazany backup")
    rollback.add_argument("zone")
    rollback.add_argument("--backup", type=Path, required=True)
    rollback.add_argument("--commit", action="store_true")
    rollback.add_argument("--json", action="store_true")
    backups = txsub.add_parser("backups", help="pokaż backupy strefy")
    backups.add_argument("zone")
    backups.add_argument("--limit", type=int, default=20)
    history = txsub.add_parser("history", help="pokaż historię transakcji")
    history.add_argument("zone", nargs="?")
    history.add_argument("--limit", type=int, default=50)
    history.add_argument("--json", action="store_true")
    history.add_argument(
        "--events",
        action="store_true",
        help="pokaż surowe zdarzenia audytowe zamiast manifestów",
    )
    show = txsub.add_parser(
        "show",
        help="pokaż pełny wynik wskazanej transakcji",
    )
    show.add_argument("transaction_id")
    show.add_argument("--json", action="store_true")

    legacy = sub.add_parser("legacy", help="uruchom zgodne polecenie silnika 2.2.0")
    legacy.add_argument("arguments", nargs=argparse.REMAINDER)
    return p


def legacy_main(arguments: list[str]) -> int:
    from . import legacy_v220
    old_argv = sys.argv
    try:
        sys.argv = ["zctl"] + arguments
        return int(legacy_v220.main() or 0)
    finally:
        sys.argv = old_argv


def grouped_lines(config: ToolkitConfig, zones):
    groups: dict[str, list[str]] = {}
    for zone in zones:
        groups.setdefault(zone.group, []).append(zone.name)
    ordered = [g for g in config.group_order if g in groups]
    ordered += sorted((g for g in groups if g not in ordered and g != "Pozostałe"), key=str.casefold)
    if "Pozostałe" in groups:
        ordered.append("Pozostałe")
    for group in ordered:
        yield f"[{group}]"
        for name in sorted(groups[group], key=str.casefold):
            yield f"  {name}"


def print_transaction(result: TransactionResult, as_json: bool = False) -> int:
    if as_json:
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    else:
        print("\n".join(transaction_lines(result)))

    return transaction_exit_code(result)


def transaction_main(args, config: ToolkitConfig) -> int:
    engine = TransactionEngine(config)
    try:
        if args.tx_command == "check":
            return print_transaction(engine.validate(args.zone, args.source), args.json)
        if args.tx_command == "apply":
            return print_transaction(engine.apply(args.zone, args.source, args.commit), args.json)
        if args.tx_command == "verify":
            return print_transaction(engine.verify(args.zone), args.json)
        if args.tx_command == "rollback":
            return print_transaction(engine.rollback(args.zone, args.backup, args.commit), args.json)
        if args.tx_command == "backups":
            for path in engine.backups(args.zone, max(1, args.limit)):
                print(path)
            return 0
        if args.tx_command == "history":
            if args.events:
                records = engine.audit.read(
                    args.zone,
                    max(1, args.limit),
                )
            else:
                records = engine.history(
                    args.zone,
                    max(1, args.limit),
                )

            if args.json:
                print(
                    json.dumps(
                        records,
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                for record in records:
                    if args.events:
                        print(
                            f"{record.get('timestamp', '-')}"
                            f"  {record.get('zone', '-'):<30}"
                            f" {record.get('outcome', '-'):<16}"
                            f" {record.get('action', '-')}"
                            f"  user={record.get('user', '-')}"
                        )
                    else:
                        print(
                            f"{record.get('saved_at', '-')}"
                            f"  {record.get('zone', '-'):<30}"
                            f" {record.get('outcome', record.get('status', '-')):<16}"
                            f" {record.get('transaction_id', '-')}"
                        )
            return 0
        if args.tx_command == "show":
            return print_transaction(
                engine.load_transaction(args.transaction_id),
                args.json,
            )
    except (RuntimeError, OSError) as exc:
        print(f"BŁĄD: {exc}", file=sys.stderr)
        return 2
    return 2


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "legacy":
        return legacy_main(args.arguments)
    try:
        config = ToolkitConfig(args.config, args.zones, args.groups).load()
    except RuntimeError as exc:
        print(f"BŁĄD: {exc}", file=sys.stderr)
        return 2
    if args.command in {"transaction", "tx"}:
        return transaction_main(args, config)
    zones = config.zones()
    if args.command == "bind" and args.bind_command in {
        "zone-secondary-plan", "zone-secondary-apply"
    }:
        applying = args.bind_command == "zone-secondary-apply"
        if applying and args.commit != args.activate:
            print("BŁĄD: właściwa zmiana wymaga jednocześnie --commit i --activate.", file=sys.stderr)
            return 2
        if applying and args.commit and (args.confirm or "").rstrip(".").casefold() != args.zone.rstrip(".").casefold():
            print("BŁĄD: --confirm musi odpowiadać pełnej nazwie strefy.", file=sys.stderr)
            return 2
        if applying and args.commit and not (args.reason or "").strip():
            print("BŁĄD: właściwa zmiana wymaga niepustego --reason.", file=sys.stderr)
            return 2
        try:
            zone_secondary_plan = BindZoneSecondaryPlanner(args.root_config).plan(args.zone, args.pairs)
            if applying:
                zone_secondary_result = BindSecondaryTransaction(
                    args.backup_root, args.manifest_directory,
                    root_config=args.root_config,
                ).apply(
                    zone_secondary_plan.transaction_plan(), commit=args.commit,
                    activate=args.activate, reason=args.reason,
                )
        except (BindZoneSecondaryError, OSError) as exc:
            print(f"BŁĄD: {exc}", file=sys.stderr)
            return 2
        if applying:
            if args.json:
                print(json.dumps(asdict(zone_secondary_result), ensure_ascii=False, indent=2))
            else:
                print(f"Transakcja: {zone_secondary_result.transaction_id}")
                print(f"Strefa:     {zone_secondary_plan.zone}")
                print(f"Status:     {zone_secondary_result.status}")
                print(f"Pary były:  {', '.join(zone_secondary_plan.old_pairs) or '-'}")
                print(f"Pary są:    {', '.join(zone_secondary_plan.new_pairs) or '-'}")
                print(f"Ryzyko:     {zone_secondary_plan.impact.risk}")
                print(f"Commit:     {'TAK' if zone_secondary_result.committed else 'NIE'}")
                print(f"Rollback:   {'TAK' if zone_secondary_result.rolled_back else 'NIE'}")
                print("\nEtapy:")
                for step in zone_secondary_result.steps:
                    print(f"[{'OK' if step.ok else 'BŁĄD'}] {step.name}: {step.message}")
            return 0 if zone_secondary_result.status in {"DRY-RUN", "COMMIT"} else 1
        if args.json:
            print(json.dumps(asdict(zone_secondary_plan), ensure_ascii=False, indent=2, default=str))
        else:
            print(f"PLAN PRZYPISANIA SECONDARY — {zone_secondary_plan.zone}")
            print(f"Pary były: {', '.join(zone_secondary_plan.old_pairs) or '-'}")
            print(f"Pary będą: {', '.join(zone_secondary_plan.new_pairs) or '-'}")
            print(f"Ryzyko:    {zone_secondary_plan.impact.risk}")
            print(f"Walidacja: {'OK' if zone_secondary_plan.validation_ok else 'BŁĄD'}")
            print("\n" + (zone_secondary_plan.diff or "Brak zmian."))
            print("\nWynik: DRY-RUN — niczego nie zmieniono")
        return 0 if zone_secondary_plan.validation_ok else 1
    if args.command == "bind" and args.bind_command == "secondary-apply":
        if args.commit != args.activate:
            print(
                "BŁĄD: właściwa zmiana wymaga jednocześnie --commit i --activate.",
                file=sys.stderr,
            )
            return 2
        if args.commit and (args.confirm or "").casefold() != args.name.casefold():
            print(
                "BŁĄD: --confirm musi odpowiadać pełnej nazwie grupy.",
                file=sys.stderr,
            )
            return 2
        if args.commit and not (args.reason or "").strip():
            print("BŁĄD: właściwa zmiana wymaga niepustego --reason.", file=sys.stderr)
            return 2
        try:
            secondary_apply_plan = BindSecondaryPlanner(args.root_config).plan(
                args.name, args.addresses
            )
            secondary_apply_result = BindSecondaryTransaction(
                args.backup_root,
                args.manifest_directory,
                root_config=args.root_config,
            ).apply(
                secondary_apply_plan, commit=args.commit, activate=args.activate,
                reason=args.reason,
            )
        except (BindSecondaryPlanError, OSError) as exc:
            print(f"BŁĄD: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(asdict(secondary_apply_result), ensure_ascii=False, indent=2))
        else:
            print(f"Transakcja: {secondary_apply_result.transaction_id}")
            print(f"Grupa:       {secondary_apply_result.group}")
            print(f"Status:      {secondary_apply_result.status}")
            print(f"Role:        {', '.join(secondary_apply_result.roles)}")
            print(f"Adresy były: {', '.join(secondary_apply_result.old_addresses)}")
            print(f"Adresy są:   {', '.join(secondary_apply_result.new_addresses)}")
            print(f"Strefy:      {len(secondary_apply_result.zones)}")
            print(f"Commit:      {'TAK' if secondary_apply_result.committed else 'NIE'}")
            print(f"Rollback:    {'TAK' if secondary_apply_result.rolled_back else 'NIE'}")
            if secondary_apply_result.backup:
                print(f"Backup:      {secondary_apply_result.backup}")
            if secondary_apply_result.manifest:
                print(f"Manifest:    {secondary_apply_result.manifest}")
            print("\nEtapy:")
            for step in secondary_apply_result.steps:
                print(f"[{'OK' if step.ok else 'BŁĄD'}] {step.name}: {step.message}")
        return 0 if secondary_apply_result.status in {"DRY-RUN", "COMMIT"} else 1
    if args.command == "bind" and args.bind_command == "access-impact":
        try:
            inventory = BindAccessInventoryReader(args.root_config).collect()
            impact_report = BindAccessImpactReporter().build(
                inventory, args.name, args.entries
            )
        except (BindAccessInventoryError, BindAccessImpactError, OSError) as exc:
            print(f"BŁĄD: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(impact_report.to_dict(), ensure_ascii=False, indent=2))
        else:
            print("RAPORT WPŁYWU ACL/SECONDARY — TYLKO ODCZYT")
            print(f"Definicja:    {impact_report.name} ({impact_report.kind})")
            print(f"Źródło:       {impact_report.source}:{impact_report.line}")
            print(f"Ryzyko:       {impact_report.risk}")
            print("Role:         " + (", ".join(impact_report.roles) or "nieużywana"))
            print("Strefy:       " + (", ".join(impact_report.zones) or "-"))
            print("Zależne ACL:  " + (", ".join(impact_report.dependent_definitions) or "-"))
            print("Wpisy obecne: " + (", ".join(impact_report.current_entries) or "-"))
            print("Kandydat:     " + (", ".join(impact_report.candidate_entries) or "-"))
            print("Dodawane:     " + (", ".join(impact_report.added_entries) or "-"))
            print("Usuwane:      " + (", ".join(impact_report.removed_entries) or "-"))
            print("\nUŻYCIA")
            for usage in impact_report.usages:
                location = f"{usage.source}:{usage.line}"
                zone = f" — strefa {usage.zone}" if usage.zone else ""
                print(
                    f"[{usage.role}] {usage.directive} — {location}{zone}"
                    f" — przez {', '.join(usage.via)}"
                )
            if impact_report.blockers:
                print("\nBLOKADY")
                for blocker in impact_report.blockers:
                    print(f"- {blocker}")
            print("\nWynik: raport odczytowy — niczego nie zmieniono")
        return 1 if impact_report.blockers else 0
    if args.command == "bind" and args.bind_command == "secondary-plan":
        try:
            secondary_plan = BindSecondaryPlanner(args.root_config).plan(
                args.name, args.addresses
            )
        except (BindSecondaryPlanError, OSError) as exc:
            print(f"BŁĄD: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(secondary_plan.to_dict(), ensure_ascii=False, indent=2))
        else:
            print("PLAN ZMIANY GRUPY SECONDARY — BEZ ZMIAN W SYSTEMIE")
            print(f"Grupa:       {secondary_plan.name}")
            print(f"Typ:         {secondary_plan.kind}")
            print(f"Role:        {', '.join(secondary_plan.roles)}")
            print(f"Plik:        {secondary_plan.source}")
            print(f"Adresy były: {', '.join(secondary_plan.old_addresses)}")
            print(f"Adresy będą: {', '.join(secondary_plan.new_addresses)}")
            print(f"Strefy ({len(secondary_plan.zones)}):")
            for zone in secondary_plan.zones:
                print(f"  {zone}")
            print(f"Walidacja:   {'OK' if secondary_plan.validation_ok else 'BŁĄD'}")
            print(f"named-checkconf: {secondary_plan.validation_message}")
            if secondary_plan.impact:
                print(f"Ryzyko wpływu: {secondary_plan.impact.risk}")
                print(
                    "Usuwane wpisy: "
                    + (", ".join(secondary_plan.impact.removed_entries) or "-")
                )
            print("\nPlanowany diff:\n")
            print(secondary_plan.diff or "Brak zmian.")
            print("\nWynik: DRY-RUN — niczego nie zmieniono")
        return 0 if secondary_plan.validation_ok else 1
    if args.command == "bind" and args.bind_command == "secondary-health":
        try:
            inventory = BindAccessInventoryReader(args.root_config).collect()
            secondary = BindSecondaryReporter().build(inventory)
        except (BindAccessInventoryError, OSError) as exc:
            print(f"BŁĄD: {exc}", file=sys.stderr)
            return 2
        selected = {item.casefold() for item in (args.pairs or [])}
        known = {pair.name.casefold() for pair in secondary.pairs}
        missing = sorted(selected - known)
        if missing:
            print("BŁĄD: Nieznane pary secondary: " + ", ".join(missing), file=sys.stderr)
            return 2
        health_pairs = tuple(
            health_pair for health_pair in secondary.pairs
            if health_pair.status == "PASS"
            and (not selected or health_pair.name.casefold() in selected)
        )
        gate = BindSecondaryHealthGate()
        health_rows = []
        failed = False
        for health_pair in health_pairs:
            servers = tuple(dict.fromkeys(health_pair.notify_addresses))
            skipped_zones = tuple(
                health_zone for health_zone in health_pair.zones
                if "rpz" in health_zone.casefold()
            )
            auditable_zones = tuple(
                health_zone for health_zone in health_pair.zones
                if health_zone not in skipped_zones
            )
            health_results = gate.check(auditable_zones, servers)
            failed = failed or any(
                health_result.status == "FAIL"
                for health_result in health_results
            )
            health_rows.append(
                (health_pair.name, servers, skipped_zones, health_results)
            )
        if args.json:
            health_payload = [
                {
                    "pair": pair_name,
                    "servers": list(servers),
                    "skipped_zones": list(skipped_zones),
                    "results": [asdict(health_result) for health_result in health_results],
                }
                for pair_name, servers, skipped_zones, health_results in health_rows
            ]
            print(json.dumps(health_payload, ensure_ascii=False, indent=2))
        else:
            print("AUDYT OPERACYJNY SECONDARY — TYLKO ODCZYT")
            for pair_name, servers, skipped_zones, health_results in health_rows:
                print(f"\nPARA {pair_name}")
                print("Serwery: " + (", ".join(servers) or "-"))
                for skipped_zone in skipped_zones:
                    print(f"[SKIP] {skipped_zone} — osobny profil RPZ")
                for health_result in health_results:
                    serials = ", ".join(
                        f"{observation.server}={observation.serial or '-'}"
                        for observation in health_result.observations
                    ) or "-"
                    print(
                        f"[{health_result.status}] {health_result.zone} — "
                        f"primary={health_result.primary_serial or '-'}; "
                        f"secondary: {serials}"
                    )
                    print(f"  {health_result.message}")
            print("\nWynik: audyt odczytowy — niczego nie zmieniono")
        return 1 if failed else 0
    if args.command == "bind" and args.bind_command == "secondary-report":
        try:
            inventory = BindAccessInventoryReader(args.root_config).collect()
            secondary_report = BindSecondaryReporter().build(inventory)
        except (BindAccessInventoryError, OSError) as exc:
            print(f"BŁĄD: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(secondary_report.to_dict(), ensure_ascii=False, indent=2))
        else:
            print("RAPORT GRUP SECONDARY — TYLKO ODCZYT")
            print("\nGRUPY")
            for group in secondary_report.groups:
                print(
                    f"[{','.join(group.roles) or 'nieużywana'}] {group.name} "
                    f"({group.kind}) — {group.source}:{group.line}"
                )
                print("  Adresy: " + (", ".join(group.entries) or "-"))
                print("  Strefy: " + (", ".join(group.zones) or "-"))
                print(f"  Użycia: {group.usage_count}")
            print("\nPARY LOGICZNE")
            for pair in secondary_report.pairs:
                print(f"[{pair.status}] {pair.name}")
                print(
                    "  Notify: "
                    + (", ".join(pair.notify_groups) or "BRAK")
                    + " — "
                    + (", ".join(pair.notify_addresses) or "-")
                )
                print(
                    "  Transfer: "
                    + (", ".join(pair.transfer_groups) or "BRAK")
                    + " — "
                    + (", ".join(pair.transfer_addresses) or "-")
                )
                print("  Strefy: " + (", ".join(pair.zones) or "-"))
        return 0
    if args.command == "bind" and args.bind_command == "acl-apply":
        if args.commit != args.activate:
            print(
                "BŁĄD: właściwa zmiana wymaga jednocześnie --commit i --activate.",
                file=sys.stderr,
            )
            return 2
        if args.commit and (args.confirm or "").casefold() != args.name.casefold():
            print(
                "BŁĄD: --confirm musi odpowiadać pełnej nazwie ACL.",
                file=sys.stderr,
            )
            return 2
        if args.commit and not (args.reason or "").strip():
            print("BŁĄD: właściwa zmiana wymaga niepustego --reason.", file=sys.stderr)
            return 2
        acl_apply_replacements: dict[str, str] = {}
        try:
            if args.entries is not None and (args.replace or args.keep_duplicates):
                raise BindAclPlanError(
                    "--entry nie można łączyć z --replace ani --keep-duplicates"
                )
            for value in args.replace:
                old, new = value.split("=", 1)
                if not old.strip() or not new.strip():
                    raise ValueError
                acl_apply_replacements[old.strip()] = new.strip()
            acl_apply_plan = BindAclPlanner(args.root_config).plan(
                args.name,
                replacements=acl_apply_replacements,
                remove_duplicates=not args.keep_duplicates,
                entries=args.entries,
            )
            acl_apply_result = BindAclTransaction(
                args.backup_root,
                args.manifest_directory,
                root_config=args.root_config,
            ).apply(
                acl_apply_plan, commit=args.commit, activate=args.activate,
                reason=args.reason,
            )
        except (BindAclPlanError, OSError, ValueError) as exc:
            print(f"BŁĄD: {str(exc) or 'nieprawidłowe --replace'}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(asdict(acl_apply_result), ensure_ascii=False, indent=2))
        else:
            print(f"Transakcja: {acl_apply_result.transaction_id}")
            print(f"ACL:         {acl_apply_result.acl}")
            print(f"Status:      {acl_apply_result.status}")
            print(f"Commit:      {'TAK' if acl_apply_result.committed else 'NIE'}")
            print(f"Rollback:    {'TAK' if acl_apply_result.rolled_back else 'NIE'}")
            if acl_apply_result.backup:
                print(f"Backup:      {acl_apply_result.backup}")
            if acl_apply_result.manifest:
                print(f"Manifest:    {acl_apply_result.manifest}")
            print("\nEtapy:")
            for step in acl_apply_result.steps:
                print(f"[{'OK' if step.ok else 'BŁĄD'}] {step.name}: {step.message}")
        return 0 if acl_apply_result.status in {"DRY-RUN", "COMMIT"} else 1
    if args.command == "bind" and args.bind_command == "acl-plan":
        acl_plan_replacements: dict[str, str] = {}
        try:
            if args.entries is not None and (args.replace or args.keep_duplicates):
                raise BindAclPlanError(
                    "--entry nie można łączyć z --replace ani --keep-duplicates"
                )
            for value in args.replace:
                old, new = value.split("=", 1)
                if not old.strip() or not new.strip():
                    raise ValueError
                acl_plan_replacements[old.strip()] = new.strip()
            acl_plan = BindAclPlanner(args.root_config).plan(
                args.name,
                replacements=acl_plan_replacements,
                remove_duplicates=not args.keep_duplicates,
                entries=args.entries,
            )
        except (BindAclPlanError, OSError, ValueError) as exc:
            detail = str(exc) or "--replace wymaga formatu STARY=NOWY"
            print(f"BŁĄD: {detail}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(acl_plan.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(f"PLAN UPORZĄDKOWANIA ACL — BEZ ZMIAN W SYSTEMIE")
            print(f"ACL:         {acl_plan.name}")
            print(f"Plik:        {acl_plan.source}")
            print(f"Walidacja:   {'OK' if acl_plan.validation_ok else 'BŁĄD'}")
            print(f"named-checkconf: {acl_plan.validation_message}")
            if acl_plan.impact:
                print(f"Ryzyko wpływu: {acl_plan.impact.risk}")
                print("Role:        " + (", ".join(acl_plan.impact.roles) or "nieużywana"))
                print("Strefy:      " + (", ".join(acl_plan.impact.zones) or "-"))
                print(
                    "Usuwane:      "
                    + (", ".join(acl_plan.impact.removed_entries) or "-")
                )
                if acl_plan.impact.blockers:
                    print("Blokady wpływu:")
                    for blocker in acl_plan.impact.blockers:
                        print(f"  {blocker}")
            print("\nPlanowany diff:\n")
            print(acl_plan.diff or "Brak zmian.")
            print("\nZamiany:")
            for value in acl_plan.replacements or ("-",):
                print(f"  {value}")
            print("Usunięte duplikaty:")
            for value in acl_plan.removed_duplicates or ("-",):
                print(f"  {value}")
            print("\nWynik: DRY-RUN — niczego nie zmieniono")
        return 0 if acl_plan.validation_ok else 1
    if args.command == "bind" and args.bind_command == "onboarding-report":
        try:
            onboarding_report = BindOnboardingReporter(args.root_config).collect()
        except (
            BindDiscoveryError,
            BindAccessInventoryError,
            ManagedZoneMigrationError,
            OSError,
        ) as exc:
            print(f"BŁĄD: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(onboarding_report.to_dict(), ensure_ascii=False, indent=2))
        else:
            print("GOTOWOŚĆ ŚRODOWISKA BIND — TYLKO ODCZYT")
            print(f"Konfiguracja:       {onboarding_report.root_config}")
            print(f"Pliki konfiguracji: {onboarding_report.config_files}")
            print(f"Strefy:             {onboarding_report.zones}")
            print(f"DNSSEC:             {onboarding_report.dnssec_zones}")
            print("\nKLASYFIKACJA")
            for onboarding_class in onboarding_report.classes:
                print(f"[{onboarding_class.state:<8}] {onboarding_class.count:>3} — {onboarding_class.description}")
            print("\nKONFIGURACJA WSPÓŁDZIELONA")
            print(f"ACL:                {onboarding_report.acl_definitions}")
            print(f"Grupy secondary:    {onboarding_report.secondary_groups}")
            print(f"Integracje RPZ:     {onboarding_report.rpz_integrations}")
            print(f"Tryby RPZ:          {', '.join(onboarding_report.rpz_modes) or '-'}")
            print(f"\nKandydaci:          {onboarding_report.import_candidates}")
            print(f"Zablokowane:        {onboarding_report.blocked}")
            if onboarding_report.blockers:
                print("\nSZCZEGÓŁY BLOKAD")
                for onboarding_blocker in onboarding_report.blockers:
                    print(f"[{onboarding_blocker.category:<9}] {onboarding_blocker.name} — {onboarding_blocker.reason}")
            print(f"Następny krok:      {onboarding_report.next_action}")
            print("\nWynik: raport odczytowy — niczego nie zaimportowano")
        return 0
    if args.command == "bind" and args.bind_command == "environment-report":
        try:
            environment_report = BindEnvironmentReporter(
                args.root_config,
                timer_unit=args.timer_unit,
                service_unit=args.service_unit,
                rpz_max_age=args.rpz_max_age,
            ).collect()
        except (BindDiscoveryError, OSError) as exc:
            print(f"BŁĄD: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(environment_report.to_dict(), ensure_ascii=False, indent=2))
        else:
            print("RAPORT ŚRODOWISKA BIND — TYLKO ODCZYT")
            print(f"Konfiguracja:       {environment_report.root_config}")
            print(f"Pliki konfiguracji: {len(environment_report.config_files)}")
            print(f"Strefy:             {environment_report.zone_count}")
            print(f"Primary:            {environment_report.primary_count}")
            print(f"Secondary:          {environment_report.secondary_count}")
            print(f"DNSSEC:             {environment_report.dnssec_count}")
            print("\nINTEGRACJE RPZ")
            if not environment_report.rpz:
                print("- brak aktywnej strefy response-policy")
            for rpz in environment_report.rpz:
                age = f"{rpz.age_seconds} s" if rpz.age_seconds is not None else "-"
                print(f"[{rpz.health}] {rpz.zone}")
                print(f"  Tryb zarządzania: {rpz.mode}")
                print(f"  Plik:             {rpz.source_file or '-'}")
                print(f"  Wiek:             {age} (limit {rpz.max_age_seconds} s)")
                print(f"  Serial / węzły:   {rpz.serial or '-'} / {rpz.nodes or '-'}")
                print(
                    "  Timer:            "
                    f"{'enabled' if rpz.timer_enabled else 'disabled'}, "
                    f"{'active' if rpz.timer_active else 'inactive'}"
                )
                print(f"  Ostatni przebieg: {rpz.timer_last_trigger or '-'}")
                print(f"  Następny przebieg: {rpz.timer_next_elapse or '-'}")
                print(f"  Wynik usługi:     {rpz.service_result or 'nieznany'}")
                print(f"  Aktualizator:      {rpz.updater_path or '-'}")
                for finding in rpz.findings:
                    print(f"  UWAGA: {finding}")
            for finding in environment_report.findings:
                print(f"UWAGA: {finding}")
            print("\nWynik: raport odczytowy — niczego nie zmieniono")
        return 1 if any(
            rpz_item.health in {"FAILED", "STALE", "DISABLED"}
            for rpz_item in environment_report.rpz
        ) else 0
    if args.command == "bind" and args.bind_command == "rpz-managed-plan":
        try:
            rpz_managed_plan = RpzManagedPlanner(
                args.root_config, zone=args.zone, source_url=args.source_url
            ).plan()
        except (BindDiscoveryError, OSError) as exc:
            print(f"BŁĄD: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(rpz_managed_plan.to_dict(), ensure_ascii=False, indent=2))
        else:
            print("PLAN OPCJONALNEJ INTEGRACJI CERT POLSKA RPZ — TYLKO ODCZYT")
            print(f"Status:       {rpz_managed_plan.status}")
            print(f"Strefa:       {rpz_managed_plan.zone}")
            print(f"Źródło:       {rpz_managed_plan.source_url}")
            print(f"Plik strefy:  {rpz_managed_plan.zone_file}")
            print(f"Deklaracja:   {rpz_managed_plan.declaration_file}")
            print(f"Opcje BIND:   {rpz_managed_plan.options_file or '-'}")
            print(f"Aktualizator: {rpz_managed_plan.updater_file}")
            print(f"Usługa:       {rpz_managed_plan.service_file}")
            print(f"Timer:        {rpz_managed_plan.timer_file}")
            print(f"Backup:       {rpz_managed_plan.backup_root}")
            print("\nKONFLIKTY")
            for conflict in rpz_managed_plan.conflicts or ("-",):
                print(f"- {conflict}")
            print("\nPLANOWANE ETAPY PRZYSZŁEJ TRANSAKCJI")
            for step in rpz_managed_plan.steps:
                print(f"- {step}")
            print(f"\nNastępny krok: {rpz_managed_plan.next_action}")
            print("\nWynik: PLAN — niczego nie zapisano i nie zmieniono BIND")
        return 0 if rpz_managed_plan.status == "READY" else 1
    if args.command == "bind" and args.bind_command == "rpz-managed-dry-run":
        try:
            rpz_dry_run_plan = RpzManagedPlanner(
                args.root_config, zone=args.zone, source_url=args.source_url
            ).plan()
            rpz_dry_run_result = RpzManagedInstallDryRun().execute(rpz_dry_run_plan)
        except (BindDiscoveryError, OSError) as exc:
            print(f"BŁĄD: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(rpz_dry_run_result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print("DRY-RUN ŚWIEŻEJ INSTALACJI CERT POLSKA RPZ")
            print(f"Strefa:       {rpz_dry_run_result.zone}")
            print(f"Status:       {rpz_dry_run_result.status}")
            print(f"Commit:       {'TAK' if rpz_dry_run_result.committed else 'NIE'}")
            print(f"Aktywacja:    {'TAK' if rpz_dry_run_result.activated else 'NIE'}")
            print("\nETAPY")
            for rpz_dry_run_step in rpz_dry_run_result.steps:
                print(f"[{'OK' if rpz_dry_run_step.ok else 'BŁĄD'}] {rpz_dry_run_step.name}: {rpz_dry_run_step.message}")
            if rpz_dry_run_result.candidate_hashes:
                print("\nSUMY KANDYDATÓW")
                for candidate_name, candidate_digest in rpz_dry_run_result.candidate_hashes.items():
                    print(f"- {candidate_name}: {candidate_digest}")
            print(
                "\nWynik: DRY-RUN — nie zapisano plików systemowych, "
                "nie uruchomiono timera i nie zmieniono BIND"
            )
        return 0 if rpz_dry_run_result.status == "DRY-RUN" else 1
    if args.command == "bind" and args.bind_command == "rpz-managed-apply":
        try:
            rpz_apply_plan = RpzManagedPlanner(
                args.root_config, zone=args.zone, source_url=args.source_url
            ).plan()
            rpz_apply_result = RpzManagedInstallTransaction(
                manifest_directory=args.manifest_directory
            ).apply(
                rpz_apply_plan,
                commit=args.commit,
                activate=args.activate,
                confirm=args.confirm,
            )
        except (BindDiscoveryError, OSError) as exc:
            print(f"BŁĄD: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(rpz_apply_result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print("TRANSAKCJA ŚWIEŻEJ INSTALACJI CERT POLSKA RPZ")
            print(f"Transakcja: {rpz_apply_result.transaction_id or '-'}")
            print(f"Strefa:     {rpz_apply_result.zone}")
            print(f"Status:     {rpz_apply_result.status}")
            print(f"Commit:     {'TAK' if rpz_apply_result.committed else 'NIE'}")
            print(f"Aktywacja:  {'TAK' if rpz_apply_result.activated else 'NIE'}")
            print(f"Rollback:   {'TAK' if rpz_apply_result.rolled_back else 'NIE'}")
            if rpz_apply_result.backup:
                print(f"Backup:     {rpz_apply_result.backup}")
            if rpz_apply_result.manifest:
                print(f"Manifest:   {rpz_apply_result.manifest}")
            print("\nETAPY")
            for rpz_apply_step in rpz_apply_result.steps:
                print(f"[{'OK' if rpz_apply_step.ok else 'BŁĄD'}] {rpz_apply_step.name}: {rpz_apply_step.message}")
        if rpz_apply_result.status == "REJECTED":
            return 2
        return 0 if rpz_apply_result.status in {"DRY-RUN", "COMMIT"} else 1
    if args.command == "bind" and args.bind_command == "rpz-external-migration-plan":
        try:
            rpz_migration_plan = RpzExternalMigrationPlanner(args.root_config).plan()
        except (BindDiscoveryError, OSError) as exc:
            print(f"BŁĄD: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(rpz_migration_plan.to_dict(), ensure_ascii=False, indent=2))
        else:
            print("PLAN MIGRACJI RPZ EXTERNAL → MANAGED — TYLKO ODCZYT")
            print(f"Status:          {rpz_migration_plan.status}")
            print(f"Strefa:          {rpz_migration_plan.zone}")
            print(f"Timer EXTERNAL:  {rpz_migration_plan.current_timer or '-'}")
            print(f"Usługa EXTERNAL: {rpz_migration_plan.current_service or '-'}")
            print(
                "Stan timera:     "
                f"{'enabled' if rpz_migration_plan.current_enabled else 'disabled'}, "
                f"{'active' if rpz_migration_plan.current_active else 'inactive'}"
            )
            print("\nINWENTARYZACJA — BEZ WYŚWIETLANIA TREŚCI")
            for migration_artifact in rpz_migration_plan.artifacts:
                print(
                    f"[{migration_artifact.role:<12}] {migration_artifact.path or '-'} — "
                    f"{'OK' if migration_artifact.exists else 'BRAK'}"
                )
                if migration_artifact.exists:
                    print(
                        f"  uid/gid {migration_artifact.owner}/{migration_artifact.group}, {migration_artifact.mode}, "
                        f"SHA-256 {migration_artifact.sha256}"
                    )
            print("\nCELE MANAGED")
            print(f"Aktualizator: {rpz_migration_plan.managed_updater}")
            print(f"Usługa:       {rpz_migration_plan.managed_service}")
            print(f"Timer:        {rpz_migration_plan.managed_timer}")
            print(f"Backup:       {rpz_migration_plan.backup_root}")
            print("\nBLOKADY")
            for migration_blocker in rpz_migration_plan.blockers or ("-",):
                print(f"- {migration_blocker}")
            print("\nPLANOWANE ETAPY")
            for migration_step_name in rpz_migration_plan.steps:
                print(f"- {migration_step_name}")
            print(f"\nNastępny krok: {rpz_migration_plan.next_action}")
            print("\nWynik: PLAN — nie zatrzymano timera i nie zmieniono BIND")
        return 0 if rpz_migration_plan.status == "READY" else 1
    if args.command == "bind" and args.bind_command == "rpz-external-migration-dry-run":
        try:
            rpz_migration_dry_plan = RpzExternalMigrationPlanner(args.root_config).plan()
            rpz_migration_dry_result = RpzExternalMigrationDryRun(
                root_config=args.root_config
            ).execute(rpz_migration_dry_plan)
        except (BindDiscoveryError, OSError) as exc:
            print(f"BŁĄD: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(rpz_migration_dry_result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print("DRY-RUN MIGRACJI RPZ EXTERNAL → MANAGED")
            print(f"Strefa:          {rpz_migration_dry_result.zone}")
            print(f"Status:          {rpz_migration_dry_result.status}")
            print(f"Commit:          {'TAK' if rpz_migration_dry_result.committed else 'NIE'}")
            print(f"Przełączenie:    {'TAK' if rpz_migration_dry_result.timer_switched else 'NIE'}")
            print("\nETAPY")
            for migration_dry_step in rpz_migration_dry_result.steps:
                print(f"[{'OK' if migration_dry_step.ok else 'BŁĄD'}] {migration_dry_step.name}: {migration_dry_step.message}")
            if rpz_migration_dry_result.candidate_hashes:
                print("\nSUMY KANDYDATÓW")
                for migration_name, migration_digest in rpz_migration_dry_result.candidate_hashes.items():
                    print(f"- {migration_name}: {migration_digest}")
            print(
                "\nWynik: DRY-RUN — nie zapisano plików systemowych, "
                "nie zatrzymano timera i nie zmieniono BIND"
            )
        return 0 if rpz_migration_dry_result.status == "DRY-RUN" else 1
    if args.command == "bind" and args.bind_command == "rpz-external-migration-apply":
        try:
            rpz_migration_apply_plan = RpzExternalMigrationPlanner(args.root_config).plan()
            rpz_migration_apply_result = RpzExternalMigrationTransaction(
                args.backup_root,
                args.manifest_directory,
                root_config=args.root_config,
            ).apply(
                rpz_migration_apply_plan,
                commit=args.commit,
                activate=args.activate,
                confirm=args.confirm,
            )
        except (BindDiscoveryError, OSError) as exc:
            print(f"BŁĄD: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(rpz_migration_apply_result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print("TRANSAKCJA MIGRACJI RPZ EXTERNAL → MANAGED")
            print(f"Transakcja:  {rpz_migration_apply_result.transaction_id}")
            print(f"Strefa:      {rpz_migration_apply_result.zone}")
            print(f"Status:      {rpz_migration_apply_result.status}")
            print(f"Commit:      {'TAK' if rpz_migration_apply_result.committed else 'NIE'}")
            print(f"Aktywacja:   {'TAK' if rpz_migration_apply_result.activated else 'NIE'}")
            print(f"Rollback:    {'TAK' if rpz_migration_apply_result.rolled_back else 'NIE'}")
            if rpz_migration_apply_result.backup:
                print(f"Backup:      {rpz_migration_apply_result.backup}")
            if rpz_migration_apply_result.manifest:
                print(f"Manifest:    {rpz_migration_apply_result.manifest}")
            print("\nETAPY")
            for migration_apply_step in rpz_migration_apply_result.steps:
                print(f"[{'OK' if migration_apply_step.ok else 'BŁĄD'}] {migration_apply_step.name}: {migration_apply_step.message}")
        if rpz_migration_apply_result.status == "REJECTED":
            return 2
        return 0 if rpz_migration_apply_result.status in {"DRY-RUN", "COMMIT"} else 1
    if args.command == "bind" and args.bind_command in {"inventory", "audit"}:
        try:
            access_inventory = BindAccessInventoryReader(args.root_config).collect()
        except (BindAccessInventoryError, OSError) as exc:
            print(f"BŁĄD: {exc}", file=sys.stderr)
            return 2
        if args.bind_command == "audit":
            access_audit = BindAccessAuditor().audit(access_inventory)
            if args.json:
                print(json.dumps(access_audit.to_dict(), ensure_ascii=False, indent=2))
            else:
                print("AUDYT ACL I GRUP SECONDARY")
                print(f"Status: {access_audit.status}")
                if not access_audit.findings:
                    print("[OK] Nie wykryto problemów.")
                for access_finding in access_audit.findings:
                    location = (
                        f" — {access_finding.source}:{access_finding.line}"
                        if access_finding.source and access_finding.line else ""
                    )
                    print(
                        f"[{access_finding.severity}] {access_finding.code}: "
                        f"{access_finding.message}{location}"
                    )
                    if access_finding.zones:
                        print("  Strefy: " + ", ".join(access_finding.zones))
            return 1 if access_audit.status == "FAIL" else 0
        if args.json:
            print(json.dumps(access_inventory.to_dict(), ensure_ascii=False, indent=2))
        else:
            print("DEFINICJE ACL I GRUP SECONDARY")
            if not access_inventory.definitions:
                print("- brak")
            for access_definition in access_inventory.definitions:
                print(
                    f"[{access_definition.kind.upper()}] {access_definition.name} — "
                    f"{access_definition.source}:{access_definition.line}"
                )
                for access_entry in access_definition.entries:
                    print(f"  {access_entry}")
            print("\nUŻYCIA")
            if not access_inventory.usages:
                print("- brak")
            for access_usage in access_inventory.usages:
                print(
                    f"[{access_usage.directive}] {access_usage.source}:{access_usage.line} — "
                    + "; ".join(access_usage.values)
                )
        return 0
    if args.command == "dnssec" and args.dnssec_command == "confirm-ds":
        if args.commit != args.acknowledge_published:
            print(
                "BŁĄD: właściwe potwierdzenie wymaga jednocześnie "
                "--commit i --acknowledge-published.",
                file=sys.stderr,
            )
            return 2
        wanted = args.name.strip().rstrip(".").casefold()
        confirm_zone = next(
            (
                item
                for item in zones
                if item.name.rstrip(".").casefold() == wanted
            ),
            None,
        )
        if confirm_zone is None:
            print(f"BŁĄD: Nie znaleziono strefy: {args.name}", file=sys.stderr)
            return 2
        resolvers = tuple(
            args.resolvers or ("1.1.1.1", "8.8.8.8", "9.9.9.9")
        )
        local_server = args.server or config.toolkit.get(
            "local_server", "127.0.0.1"
        )
        confirm_checker = DnssecDsChecker(
            local_server=local_server,
            timeout=int(config.toolkit.get("dig_timeout", "3")),
        )
        confirm_result = DnssecConfirmDsTransaction(
            args.manifest_directory,
            checker=confirm_checker.collect,
        ).apply(
            confirm_zone.name,
            resolvers,
            commit=args.commit,
            acknowledge_published=args.acknowledge_published,
        )
        if args.json:
            print(json.dumps(asdict(confirm_result), ensure_ascii=False, indent=2))
        else:
            print(f"Transakcja: {confirm_result.transaction_id}")
            print(f"Strefa:     {confirm_result.zone}")
            print(f"Status:     {confirm_result.status}")
            print(f"Commit:     {'TAK' if confirm_result.committed else 'NIE'}")
            if confirm_result.manifest:
                print(f"Manifest:   {confirm_result.manifest}")
            print("\nEtapy:")
            for confirm_step in confirm_result.steps:
                print(f"[{'OK' if confirm_step.ok else 'BŁĄD'}] {confirm_step.name}: {confirm_step.message}")
        return 0 if confirm_result.status in {"DRY-RUN", "CONFIRMED"} else 1
    if (
        args.command == "dnssec"
        and args.dnssec_command == "prepare-finalize-serial"
    ):
        wanted = args.name.strip().rstrip(".").casefold()
        display_zone = next(
            (
                zone
                for zone in zones
                if zone.name.rstrip(".").casefold() == wanted
            ),
            None,
        )
        if display_zone is None:
            print(f"BŁĄD: Nie znaleziono strefy: {args.name}", file=sys.stderr)
            return 2
        if display_zone.health_profile.casefold() == "rpz":
            print(
                f"BŁĄD: Przygotowanie seriala jest zablokowane dla RPZ: "
                f"{display_zone.name}",
                file=sys.stderr,
            )
            return 2
        discovered = config.discovered_zone(args.name)
        if discovered is None or discovered.source_file is None:
            print(
                "BŁĄD: Operacja wymaga autodetekcji aktywnego pliku strefy.",
                file=sys.stderr,
            )
            return 2
        finalize_result = DnssecFinalizeSerialTransaction(args.backup_root).apply(
            display_zone.name,
            discovered.source_file,
            commit=args.commit,
        )
        if args.json:
            print(json.dumps(asdict(finalize_result), ensure_ascii=False, indent=2))
        else:
            print(f"Transakcja:       {finalize_result.transaction_id}")
            print(f"Strefa:           {finalize_result.zone}")
            print(f"Status:           {finalize_result.status}")
            print(f"Serial źródłowy:  {finalize_result.previous_serial or '-'}")
            print(f"Serial serwowany: {finalize_result.served_serial or '-'}")
            print(f"Nowy serial:      {finalize_result.new_serial or '-'}")
            print(f"Commit:           {'TAK' if finalize_result.committed else 'NIE'}")
            if finalize_result.backup:
                print(f"Backup:           {finalize_result.backup}")
            print("\nEtapy:")
            for finalize_step in finalize_result.steps:
                print(f"[{'OK' if finalize_step.ok else 'BŁĄD'}] {finalize_step.name}: {finalize_step.message}")
        return 0 if finalize_result.status in {"DRY-RUN", "COMMIT"} else 1
    if args.command == "dnssec" and args.dnssec_command in {
        "disable-plan",
        "disable-apply",
        "withdrawal-backup",
    }:
        wanted = args.name.strip().rstrip(".").casefold()
        display_zone = next(
            (
                zone
                for zone in zones
                if zone.name.rstrip(".").casefold() == wanted
            ),
            None,
        )
        if display_zone is None:
            print(f"BŁĄD: Nie znaleziono strefy: {args.name}", file=sys.stderr)
            return 2
        if display_zone.health_profile.casefold() == "rpz":
            print(
                f"BŁĄD: Wycofanie DNSSEC jest zablokowane dla RPZ: "
                f"{display_zone.name}",
                file=sys.stderr,
            )
            return 2
        discovered = config.discovered_zone(args.name)
        if discovered is None:
            print(
                "BŁĄD: Plan wycofania DNSSEC wymaga autodetekcji deklaracji BIND.",
                file=sys.stderr,
            )
            return 2
        try:
            disable_plan = DnssecDisablePlanner().plan(discovered)
        except (DnssecDisablePlanError, OSError) as exc:
            print(f"BŁĄD: {exc}", file=sys.stderr)
            return 2
        if args.dnssec_command == "disable-apply":
            resolvers = tuple(
                args.disable_resolvers or ("1.1.1.1", "8.8.8.8", "9.9.9.9")
            )
            withdrawal_checker = DnssecWithdrawalChecker(
                timeout=int(config.toolkit.get("dig_timeout", "3")),
            )

            def ds_absent(zone_name: str) -> bool | None:
                outcome = withdrawal_checker.collect(zone_name, resolvers)
                if outcome.status == "READY_FOR_WITHDRAWN":
                    return True
                if outcome.status == "BLOCKED":
                    return False
                return None

            disable_result = DnssecDisableTransaction(
                args.backup_root,
                args.manifest_directory,
                root_config=args.root_config,
                ds_gate=ds_absent,
            ).apply(
                disable_plan,
                stage=args.stage,
                commit=args.commit,
                activate=args.activate,
                acknowledge_unsigned=args.acknowledge_unsigned,
            )
            if args.json:
                print(json.dumps(asdict(disable_result), ensure_ascii=False, indent=2))
            else:
                print(f"Transakcja: {disable_result.transaction_id}")
                print(f"Strefa:     {disable_result.zone}")
                print(f"Etap:       {disable_result.stage}")
                print(f"Status:     {disable_result.status}")
                print(f"Commit:     {'TAK' if disable_result.committed else 'NIE'}")
                if disable_result.kasp_states:
                    print(f"Stany KASP: {', '.join(disable_result.kasp_states)}")
                if disable_result.backup_directory:
                    print(f"Backup:     {disable_result.backup_directory}")
                if disable_result.manifest:
                    print(f"Manifest:   {disable_result.manifest}")
                print("\nEtapy:")
                for disable_step in disable_result.steps:
                    print(
                        f"[{'OK' if disable_step.ok else 'BŁĄD'}] {disable_step.name}: {disable_step.message}"
                    )
            return 0 if disable_result.status in {"DRY-RUN", "COMMIT"} else 1
        if args.dnssec_command == "withdrawal-backup":
            local_server = args.server or config.toolkit.get(
                "local_server", "127.0.0.1"
            )
            timeout = int(config.toolkit.get("dig_timeout", "3"))
            resolvers = tuple(
                args.resolvers or ("1.1.1.1", "8.8.8.8", "9.9.9.9")
            )
            try:
                report_payload = DnssecReporter(
                    local_server=local_server,
                    resolver=resolvers[0],
                    timeout=timeout,
                ).collect(display_zone, disable_plan.key_directory).to_dict()
            except Exception as exc:
                report_payload = {"status": "ERROR", "error": str(exc)}
            try:
                check_payload = DnssecDsChecker(
                    local_server=local_server,
                    timeout=timeout,
                ).collect(disable_plan.zone, resolvers).to_dict()
            except Exception as exc:
                check_payload = {"status": "ERROR", "error": str(exc)}
            withdrawal_backup_result = DnssecWithdrawalBackup(args.backup_root).create(
                disable_plan,
                commit=args.commit,
                dnssec_report=report_payload,
                ds_check=check_payload,
            )
            if args.json:
                print(json.dumps(asdict(withdrawal_backup_result), ensure_ascii=False, indent=2))
            else:
                print(f"Transakcja: {withdrawal_backup_result.transaction_id}")
                print(f"Strefa:     {withdrawal_backup_result.zone}")
                print(f"Status:     {withdrawal_backup_result.status}")
                print(f"Commit:     {'TAK' if withdrawal_backup_result.committed else 'NIE'}")
                if withdrawal_backup_result.package:
                    print(f"Pakiet:     {withdrawal_backup_result.package}")
                if withdrawal_backup_result.manifest:
                    print(f"Manifest:   {withdrawal_backup_result.manifest}")
                print("\nEtapy:")
                for withdrawal_backup_step in withdrawal_backup_result.steps:
                    print(f"[{'OK' if withdrawal_backup_step.ok else 'BŁĄD'}] {withdrawal_backup_step.name}: {withdrawal_backup_step.message}")
            return 0 if withdrawal_backup_result.status in {"DRY-RUN", "BACKUP-CREATED"} else 1
        if args.json:
            print(json.dumps(disable_plan.to_dict(), ensure_ascii=False, indent=2))
        else:
            print("PLAN WYCOFANIA DNSSEC — BEZ ZMIAN W SYSTEMIE")
            print(f"Strefa:          {disable_plan.zone}")
            print(f"Plik strefy:     {disable_plan.zone_file}")
            print(f"Deklaracja:      {disable_plan.declaration_file}")
            print(f"Polityka:        {disable_plan.policy}")
            print(f"Katalog kluczy:  {disable_plan.key_directory or '-'}")
            print(f"Pliki kluczy:    {len(disable_plan.key_files)}")
            print(f"Artefakty BIND:  {len(disable_plan.signing_artifacts)}")
            print("\nKońcowy diff — wolno zastosować dopiero po wycofaniu DS:\n")
            print(disable_plan.unified_diff, end="")
            print("\nObowiązkowe etapy:")
            for action_index, disable_action in enumerate(disable_plan.actions, start=1):
                print(f"{action_index}. {disable_action}")
            print("\nWynik: DRY-RUN — niczego nie zmieniono")
        return 0
    if args.command == "dnssec" and args.dnssec_command in {"enable-plan", "enable"}:
        if args.dnssec_command == "enable" and args.commit != args.activate:
            print(
                "BŁĄD: właściwa zmiana wymaga jednocześnie --commit i --activate.",
                file=sys.stderr,
            )
            return 2
        wanted = args.name.strip().rstrip(".").casefold()
        display_zone = next(
            (
                zone
                for zone in zones
                if zone.name.rstrip(".").casefold() == wanted
            ),
            None,
        )
        if display_zone is None:
            print(f"BŁĄD: Nie znaleziono strefy: {args.name}", file=sys.stderr)
            return 2
        if display_zone.health_profile.casefold() == "rpz":
            print(
                f"BŁĄD: Włączenie DNSSEC jest zablokowane dla RPZ: {display_zone.name}",
                file=sys.stderr,
            )
            return 2
        discovered = config.discovered_zone(args.name)
        if discovered is None:
            print(
                "BŁĄD: Plan DNSSEC wymaga autodetekcji deklaracji strefy BIND.",
                file=sys.stderr,
            )
            return 2
        try:
            enable_plan = DnssecEnablePlanner().plan(
                discovered,
                policy=args.policy,
                key_directory=args.key_directory,
                zone_directory=args.zone_directory,
            )
        except (DnssecEnablePlanError, OSError) as exc:
            print(f"BŁĄD: {exc}", file=sys.stderr)
            return 2
        if args.dnssec_command == "enable":
            enable_result = DnssecEnableTransaction(
                args.backup_root,
                args.manifest_directory,
                root_config=args.root_config,
            ).apply(
                enable_plan,
                commit=args.commit,
                activate=args.activate,
            )
            if args.json:
                print(json.dumps(asdict(enable_result), ensure_ascii=False, indent=2))
            else:
                print(f"Transakcja: {enable_result.transaction_id}")
                print(f"Strefa:     {enable_result.zone}")
                print(f"Status:     {enable_result.status}")
                print(f"Commit:     {'TAK' if enable_result.committed else 'NIE'}")
                print(f"Rollback:   {'TAK' if enable_result.rolled_back else 'NIE'}")
                if enable_result.backup_directory:
                    print(f"Backup:     {enable_result.backup_directory}")
                if enable_result.manifest:
                    print(f"Manifest:   {enable_result.manifest}")
                print("\nEtapy:")
                for enable_step in enable_result.steps:
                    print(f"[{'OK' if enable_step.ok else 'BŁĄD'}] {enable_step.name}: {enable_step.message}")
            return 0 if enable_result.status in {"DRY-RUN", "COMMIT"} else 1
        if args.json:
            print(json.dumps(enable_plan.to_dict(), ensure_ascii=False, indent=2))
        else:
            print("PLAN WŁĄCZENIA DNSSEC — BEZ ZMIAN W SYSTEMIE")
            print(f"Strefa:       {enable_plan.zone}")
            print(f"Plik źródłowy: {enable_plan.source_zone_file}")
            print(f"Plik docelowy: {enable_plan.target_zone_file}")
            print(
                "Migracja pliku: "
                + ("TAK" if enable_plan.migration_required else "NIE")
            )
            print(f"Deklaracja:   {enable_plan.declaration_file}")
            print(f"Polityka:     {enable_plan.policy}")
            print(f"Katalog kluczy: {enable_plan.key_directory}")
            print("\nPlanowany diff:\n")
            print(enable_plan.unified_diff, end="")
            print("\nPlanowane etapy:")
            for enable_action in enable_plan.actions:
                print(f"- {enable_action}")
            print("\nWynik: DRY-RUN — niczego nie zmieniono")
        return 0
    if args.command == "dnssec" and args.dnssec_command == "check-ds":
        wanted = args.name.strip().rstrip(".").casefold()
        ds_check_zone = next(
            (
                item
                for item in zones
                if item.name.rstrip(".").casefold() == wanted
            ),
            None,
        )
        if ds_check_zone is None:
            print(f"BŁĄD: Nie znaleziono strefy: {args.name}", file=sys.stderr)
            return 2
        resolvers = tuple(
            args.resolvers or ("1.1.1.1", "8.8.8.8", "9.9.9.9")
        )
        local_server = args.server or config.toolkit.get(
            "local_server", "127.0.0.1"
        )
        ds_check_result = DnssecDsChecker(
            local_server=local_server,
            timeout=int(config.toolkit.get("dig_timeout", "3")),
        ).collect(ds_check_zone.name, resolvers)
        if args.json:
            print(json.dumps(ds_check_result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(f"KONTROLA DS — {ds_check_result.zone}")
            print(f"Status:             {ds_check_result.status}")
            print(f"Gotowość KASP:      {'TAK' if ds_check_result.kasp_ready else 'NIE'}")
            print("DS oczekiwany:")
            for expected_ds_record in ds_check_result.expected_ds or ("-",):
                print(f"  {expected_ds_record}")
            print("\nResolvery:")
            for resolver_check in ds_check_result.resolver_checks:
                print(f"  [{resolver_check.status:<10}] {resolver_check.resolver}: {resolver_check.message}")
                for resolver_record in resolver_check.records:
                    print(f"    {resolver_record}")
            print("\nSerwery autorytatywne:")
            for authority_check in ds_check_result.authority_checks:
                print(f"  [{authority_check.status:<10}] {authority_check.server}: {authority_check.message}")
            for ds_error in ds_check_result.errors:
                print(f"BŁĄD: {ds_error}")
            print(f"\nNastępny krok: {ds_check_result.next_action}")
        return 1 if ds_check_result.status == "FAIL" else 0
    if args.command == "dnssec" and args.dnssec_command == "withdrawal-check":
        wanted = args.name.strip().rstrip(".").casefold()
        withdrawal_check_zone = next(
            (
                item
                for item in zones
                if item.name.rstrip(".").casefold() == wanted
            ),
            None,
        )
        if withdrawal_check_zone is None:
            print(f"BŁĄD: Nie znaleziono strefy: {args.name}", file=sys.stderr)
            return 2
        resolvers = tuple(
            args.resolvers or ("1.1.1.1", "8.8.8.8", "9.9.9.9")
        )
        withdrawal_check_result = DnssecWithdrawalChecker(
            timeout=int(config.toolkit.get("dig_timeout", "3")),
        ).collect(withdrawal_check_zone.name, resolvers)
        if args.json:
            print(json.dumps(withdrawal_check_result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(f"KONTROLA WYCOFANIA DS — {withdrawal_check_result.zone}")
            print(f"Status:  {withdrawal_check_result.status}")
            print("\nResolvery:")
            for withdrawal_resolver_check in withdrawal_check_result.resolver_checks:
                print(f"  [{withdrawal_resolver_check.status:<11}] {withdrawal_resolver_check.resolver}: {withdrawal_resolver_check.message}")
                for withdrawal_record in withdrawal_resolver_check.records:
                    print(f"    {withdrawal_record}")
            for withdrawal_error in withdrawal_check_result.errors:
                print(f"BŁĄD: {withdrawal_error}")
            print(f"\nNastępny krok: {withdrawal_check_result.next_action}")
        return 0 if withdrawal_check_result.status == "READY_FOR_WITHDRAWN" else 1
    if args.command == "dnssec" and args.dnssec_command == "withdrawal-confirm":
        wanted = args.name.strip().rstrip(".").casefold()
        withdrawal_confirm_zone = next(
            (
                item
                for item in zones
                if item.name.rstrip(".").casefold() == wanted
            ),
            None,
        )
        if withdrawal_confirm_zone is None:
            print(f"BŁĄD: Nie znaleziono strefy: {args.name}", file=sys.stderr)
            return 2
        resolvers = tuple(
            args.resolvers or ("1.1.1.1", "8.8.8.8", "9.9.9.9")
        )
        withdrawal_confirm_checker = DnssecWithdrawalChecker(
            timeout=int(config.toolkit.get("dig_timeout", "3")),
        )
        withdrawal_confirm_result = DnssecWithdrawalConfirmTransaction(
            args.manifest_directory,
            checker=withdrawal_confirm_checker.collect,
        ).apply(
            withdrawal_confirm_zone.name,
            resolvers,
            commit=args.commit,
            acknowledge_withdrawn=args.acknowledge_withdrawn,
        )
        if args.json:
            print(json.dumps(asdict(withdrawal_confirm_result), ensure_ascii=False, indent=2))
        else:
            print(f"Transakcja: {withdrawal_confirm_result.transaction_id}")
            print(f"Strefa:     {withdrawal_confirm_result.zone}")
            print(f"Status:     {withdrawal_confirm_result.status}")
            print(f"Commit:     {'TAK' if withdrawal_confirm_result.committed else 'NIE'}")
            if withdrawal_confirm_result.manifest:
                print(f"Manifest:   {withdrawal_confirm_result.manifest}")
            print("\nEtapy:")
            for withdrawal_confirm_step in withdrawal_confirm_result.steps:
                print(f"[{'OK' if withdrawal_confirm_step.ok else 'BŁĄD'}] {withdrawal_confirm_step.name}: {withdrawal_confirm_step.message}")
        return 0 if withdrawal_confirm_result.status in {"DRY-RUN", "WITHDRAWN"} else 1
    if args.command == "dnssec" and args.dnssec_command == "report":
        wanted = args.name.strip().rstrip(".").casefold()
        matches = [
            zone
            for zone in zones
            if zone.name.rstrip(".").casefold() == wanted
        ]
        if not matches:
            print(f"BŁĄD: Nie znaleziono strefy: {args.name}", file=sys.stderr)
            return 2

        report_zone = matches[0]
        local_server = args.server or config.toolkit.get(
            "local_server", "127.0.0.1"
        )
        key_directory = report_zone.key_directory
        if key_directory is None:
            configured_directory = config.toolkit.get(
                "dnssec_key_directory", "/var/lib/bind/keys"
            ).strip()
            key_directory = (
                Path(configured_directory)
                if configured_directory
                else None
            )

        dnssec_report = DnssecReporter(
            local_server=local_server,
            resolver=args.resolver,
            timeout=int(config.toolkit.get("dig_timeout", "3")),
        ).collect(report_zone, key_directory)

        if args.json:
            print(json.dumps(dnssec_report.to_dict(), ensure_ascii=False, indent=2))
        else:
            def yes_no(value: bool | None) -> str:
                if value is True:
                    return "TAK"
                if value is False:
                    return "NIE"
                return "NIEZNANY"

            print(f"DNSSEC REPORT — {dnssec_report.zone}")
            print(f"Status:             {dnssec_report.status}")
            print(f"Skonfigurowany:     {yes_no(dnssec_report.configured)}")
            print(f"dnssec-policy:      {dnssec_report.dnssec_policy or '-'}")
            print(f"inline-signing:     {yes_no(dnssec_report.inline_signing)}")
            print(f"Strefa załadowana:  {yes_no(dnssec_report.loaded)}")
            print(f"Podpisywanie BIND:  {yes_no(dnssec_report.signing)}")
            if dnssec_report.rndc_status:
                print("Stan KASP z rndc:")
                for rndc_line in dnssec_report.rndc_status:
                    print(f"  {rndc_line}")
            print(f"Katalog kluczy:     {dnssec_report.key_directory or '-'}")
            print(f"Pliki kluczy:       {len(dnssec_report.key_files)}")
            for key_path in dnssec_report.key_files:
                print(f"  {key_path}")
            print(f"DNSKEY:             {len(dnssec_report.dnskey_records)}")
            for dnskey_record in dnssec_report.dnskey_records:
                print(f"  {dnskey_record}")
            print(f"RRSIG DNSKEY:       {len(dnssec_report.rrsig_records)}")
            print("DS obliczony lokalnie:")
            for calculated_record in dnssec_report.calculated_ds or ("-",):
                print(f"  {calculated_record}")
            print("DS widoczny publicznie:")
            for parent_record in dnssec_report.parent_ds_records or ("-",):
                print(f"  {parent_record}")
            print(f"Zgodność DS:        {yes_no(dnssec_report.parent_ds_matches)}")
            for report_warning in dnssec_report.warnings:
                print(f"OSTRZEŻENIE: {report_warning}")
            for report_error in dnssec_report.errors:
                print(f"BŁĄD: {report_error}")
            guidance = build_dnssec_guidance(dnssec_report)
            print("\nWSKAZÓWKI OPERATORA")
            print(f"Etap:               {guidance.stage}")
            print(f"Stan:               {guidance.title}")
            print(f"Postęp:             {guidance.progress}")
            if guidance.not_before:
                print(f"Najwcześniej:       {guidance.not_before}")
            print(f"Następny krok:      {guidance.next_action}")
            print(
                "Publikacja DS:      "
                + (
                    "DOZWOLONA"
                    if guidance.ds_publication_allowed
                    else "JESZCZE ZABLOKOWANA"
                )
            )

        return 1 if dnssec_report.status == "FAIL" else 0
    if args.command == "zone":
        if args.zone_command == "migration-apply":
            if args.commit != args.activate:
                print(
                    "BŁĄD: właściwa migracja wymaga jednocześnie --commit i --activate.",
                    file=sys.stderr,
                )
                return 2
            wanted = args.name.strip().rstrip(".").casefold()
            if args.commit and (args.confirm or "").strip().rstrip(".").casefold() != wanted:
                print(
                    "BŁĄD: --confirm musi odpowiadać pełnej nazwie strefy.",
                    file=sys.stderr,
                )
                return 2
            migration_planner = ManagedZoneMigrationPlanner(
                root_config=args.root_config,
                local_config=args.local_config,
                managed_config=args.managed_config,
                managed_zone_directory=args.managed_zone_directory,
            )
            try:
                migration_apply_plan = migration_planner.plan(wanted)
                migration_apply_result = ManagedZoneMigrationTransaction(
                    args.backup_root,
                    args.manifest_directory,
                    root_config=args.root_config,
                ).apply(migration_apply_plan, commit=args.commit, activate=args.activate)
            except (ManagedZoneMigrationError, OSError) as exc:
                print(f"BŁĄD: {exc}", file=sys.stderr)
                return 2
            if args.json:
                print(json.dumps(asdict(migration_apply_result), ensure_ascii=False, indent=2))
            else:
                print(f"Transakcja: {migration_apply_result.transaction_id}")
                print(f"Strefa:     {migration_apply_result.zone}")
                print(f"Status:     {migration_apply_result.status}")
                print(f"Commit:     {'TAK' if migration_apply_result.committed else 'NIE'}")
                print(f"Rollback:   {'TAK' if migration_apply_result.rolled_back else 'NIE'}")
                if migration_apply_result.backup_directory:
                    print(f"Backup:     {migration_apply_result.backup_directory}")
                if migration_apply_result.manifest:
                    print(f"Manifest:   {migration_apply_result.manifest}")
                print("\nEtapy:")
                for migration_apply_step in migration_apply_result.steps:
                    print(f"[{'OK' if migration_apply_step.ok else 'BŁĄD'}] {migration_apply_step.name}: {migration_apply_step.message}")
            return 0 if migration_apply_result.status in {"DRY-RUN", "COMMIT"} else 1
        if args.zone_command in {"migration-inventory", "migration-plan"}:
            migration_query_planner = ManagedZoneMigrationPlanner(
                root_config=args.root_config,
                local_config=args.local_config,
                managed_config=args.managed_config,
                managed_zone_directory=args.managed_zone_directory,
            )
            try:
                if args.zone_command == "migration-inventory":
                    migration_items = migration_query_planner.inventory()
                    if args.json:
                        print(json.dumps(
                            [migration_item.to_dict() for migration_item in migration_items],
                            ensure_ascii=False,
                            indent=2,
                        ))
                    elif not migration_items:
                        print("Nie znaleziono aktywnych deklaracji stref BIND.")
                    else:
                        print(f"{'STAN':<20} {'STREFA':<32} {'TYP':<12} DEKLARACJA")
                        for migration_item in migration_items:
                            print(
                                f"{migration_item.state:<20} {migration_item.name:<32} "
                                f"{migration_item.zone_type:<12} {migration_item.config_file}"
                            )
                            print(f"  {migration_item.reason}")
                    return 0

                migration_plan = migration_query_planner.plan(args.name)
                if args.json:
                    print(json.dumps(migration_plan.to_dict(), ensure_ascii=False, indent=2))
                else:
                    print(f"PLAN MIGRACJI STREFY — BEZ ZMIAN W SYSTEMIE")
                    print(f"Strefa:       {migration_plan.zone}")
                    print(f"Źródło:       {migration_plan.source_config}")
                    print(f"Deklaracja:   {migration_plan.declaration_file}")
                    print(f"Indeks:       {migration_plan.managed_config}")
                    print("\nPlanowane diffy:\n")
                    print(migration_plan.source_diff, end="")
                    print(migration_plan.declaration_diff, end="")
                    print(migration_plan.managed_diff, end="")
                    print("\nPlanowane etapy:")
                    for migration_action in migration_plan.actions:
                        print(f"- {migration_action}")
                    print("\nWynik: DRY-RUN — niczego nie zmieniono")
                return 0
            except (ManagedZoneMigrationError, OSError) as exc:
                print(f"BŁĄD: {exc}", file=sys.stderr)
                return 2
        if args.zone_command == "safety":
            selected_zones = zones
            if args.name:
                wanted = args.name.strip().rstrip(".").casefold()
                selected_zones = [
                    safety_zone
                    for safety_zone in zones
                    if safety_zone.name.rstrip(".").casefold() == wanted
                ]
                if not selected_zones:
                    print(f"BŁĄD: Nie znaleziono strefy: {args.name}", file=sys.stderr)
                    return 2
            safety_payload = [
                {
                    "zone": safety_zone.name,
                    "health_profile": safety_zone.health_profile,
                    "dnssec_policy": safety_zone.dnssec_policy,
                    "inline_signing": safety_zone.inline_signing,
                    "lifecycle_allowed": not (
                        safety_zone.health_profile.casefold() == "rpz"
                        or safety_zone.dnssec_policy
                        or safety_zone.inline_signing
                    ),
                }
                for safety_zone in selected_zones
            ]
            if args.json:
                print(json.dumps(safety_payload, ensure_ascii=False, indent=2))
            else:
                print(
                    f"{'STREFA':<32} {'PROFIL':<14} {'DNSSEC-POLICY':<18} "
                    "INLINE  CYKL ŻYCIA"
                )
                for safety_row in safety_payload:
                    print(
                        f"{safety_row['zone']:<32} {safety_row['health_profile']:<14} "
                        f"{(safety_row['dnssec_policy'] or '-'):<18} "
                        f"{('TAK' if safety_row['inline_signing'] else 'NIE'):<7} "
                        f"{'DOZWOLONY' if safety_row['lifecycle_allowed'] else 'BLOKADA'}"
                    )
            return 0
        if args.zone_command == "inventory":
            inventory_records = ZoneInventory(
                disabled_root=args.disabled_root,
                quarantine_root=args.quarantine_root,
                disable_manifest_directory=args.disable_manifest_directory,
            ).records()
            if args.json:
                print(
                    json.dumps(
                        [inventory_record.to_dict() for inventory_record in inventory_records],
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            elif not inventory_records:
                print("Brak wyłączonych i skarantannowanych stref.")
            else:
                print(
                    f"{'STAN':<13} {'STREFA':<32} {'DATA':<25} "
                    "OPERATOR  PRZYCZYNA"
                )
                for inventory_record in inventory_records:
                    print(
                        f"{inventory_record.state:<13} {inventory_record.zone:<32} "
                        f"{inventory_record.timestamp:<25} {inventory_record.operator:<9} "
                        f"{inventory_record.reason}"
                    )
                    print(f"  {inventory_record.location}")
            return 0
        if args.zone_command == "quarantine-retention":
            try:
                retention_records = QuarantineRetentionAuditor(
                    quarantine_root=args.quarantine_root,
                    retention_days=args.retention_days,
                ).records()
            except ValueError as exc:
                print(f"BŁĄD: {exc}", file=sys.stderr)
                return 2
            if args.json:
                print(json.dumps([retention_record.to_dict() for retention_record in retention_records], ensure_ascii=False, indent=2))
            else:
                print("PLAN RETENCJI KWARANTANNY — TYLKO ODCZYT")
                print(f"Okres retencji: {format_days_pl(args.retention_days)}")
                if not retention_records:
                    print("Brak pakietów kwarantanny.")
                for retention_record in retention_records:
                    age = "-" if retention_record.age_days is None else str(retention_record.age_days)
                    print(f"[{retention_record.state:<8}] {retention_record.zone} — wiek {age} dni")
                    print(f"  {retention_record.reason}")
                    print(f"  {retention_record.package}")
                print("Wynik: raport odczytowy — niczego nie usunięto")
            return 0
        if args.zone_command == "quarantine-purge":
            transaction = QuarantinePurgeTransaction(
                quarantine_root=args.quarantine_root,
                audit_directory=args.audit_directory,
                staging_root=args.staging_root,
                retention_days=args.retention_days,
            )
            try:
                plan = transaction.plan(args.name, args.package, reason=args.reason)
            except (QuarantinePurgeError, ValueError) as exc:
                print(f"BŁĄD: {exc}", file=sys.stderr)
                return 2
            result = transaction.apply(
                plan,
                commit=args.commit,
                confirmation=args.confirm,
                package_confirmation=args.confirm_package,
            )
            if args.json:
                print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
            else:
                print(f"Transakcja: {result.transaction_id}")
                print(f"Strefa:     {result.zone}")
                print(f"Pakiet:     {result.package}")
                print(f"Status:     {result.status}")
                print(f"Commit:     {'TAK' if result.committed else 'NIE'}")
                if result.manifest:
                    print(f"Manifest:   {result.manifest}")
                print("\nEtapy:")
                for step in result.steps:
                    print(f"[{'OK' if step.ok else 'BŁĄD'}] {step.name}: {step.message}")
            return 0 if result.status in {"DRY-RUN", "PURGED"} else 2
        if args.zone_command in {
            "disable",
            "restore",
            "quarantine",
            "quarantine-restore",
        }:
            try:
                ZoneLifecyclePlanner.ensure_lifecycle_allowed(
                    args.name, zones, args.zone_command
                )
            except ZoneLifecycleError as exc:
                print(f"BŁĄD: {exc}", file=sys.stderr)
                return 2
        if args.zone_command == "quarantine-restore":
            name = args.name.strip().rstrip(".").casefold()
            try:
                plan = QuarantineRestoreTransaction.plan(
                    name,
                    package_directory=args.package,
                    zone_file=args.zone_directory / name,
                    active_declaration=(
                        args.managed_zone_directory / f"{name}.conf"
                    ),
                    managed_index=args.managed_config,
                    root_config=args.root_config,
                )
                result = QuarantineRestoreTransaction().apply(
                    plan, commit=args.commit
                )
            except (QuarantineRestoreError, OSError, json.JSONDecodeError) as exc:
                print(f"BŁĄD: {exc}", file=sys.stderr)
                return 2
            if args.json:
                print(
                    json.dumps(
                        asdict(result), ensure_ascii=False, indent=2
                    )
                )
            else:
                print(f"Transakcja: {result.transaction_id}")
                print(f"Strefa:     {result.zone}")
                print(f"Status:     {result.status}")
                print(f"Pakiet:     {result.package_directory}")
                print(f"Commit:     {'TAK' if result.committed else 'NIE'}")
                print(f"Rollback:   {'TAK' if result.rolled_back else 'NIE'}")
                print("\nEtapy:")
                for step in result.steps:
                    marker = "OK" if step.ok else "BŁĄD"
                    print(f"[{marker}] {step.name}: {step.message}")
            return (
                0
                if result.ok
                and result.status in {"DRY-RUN", "RESTORED"}
                else 2
            )
        if args.zone_command == "quarantine":
            name = args.name.strip().rstrip(".").casefold()
            active_declaration = (
                args.managed_zone_directory / f"{name}.conf"
            )
            try:
                plan = ZoneQuarantineTransaction.plan(
                    name,
                    zone_file=args.zone_directory / name,
                    archived_declaration=(
                        args.disabled_root / name / f"{name}.conf"
                    ),
                    active_declaration=active_declaration,
                    managed_index=args.managed_config,
                    quarantine_root=args.quarantine_root,
                    reason=args.reason,
                )
                result = ZoneQuarantineTransaction().apply(
                    plan,
                    commit=args.commit,
                    confirmation=args.confirm,
                )
            except (ZoneQuarantineError, OSError) as exc:
                print(f"BŁĄD: {exc}", file=sys.stderr)
                return 2
            if args.json:
                print(
                    json.dumps(
                        asdict(result), ensure_ascii=False, indent=2
                    )
                )
            else:
                print(f"Transakcja: {result.transaction_id}")
                print(f"Strefa:     {result.zone}")
                print(f"Status:     {result.status}")
                print(f"Przyczyna:  {result.reason}")
                print(f"Commit:     {'TAK' if result.committed else 'NIE'}")
                if result.package_directory:
                    print(f"Pakiet:     {result.package_directory}")
                print("\nEtapy:")
                for step in result.steps:
                    marker = "OK" if step.ok else "BŁĄD"
                    print(f"[{marker}] {step.name}: {step.message}")
            return (
                0
                if result.ok
                and result.status in {"DRY-RUN", "QUARANTINED"}
                else 2
            )
        if args.zone_command == "restore":
            name = args.name.strip().rstrip(".").casefold()
            try:
                plan = ZoneRestoreTransaction.plan(
                    name,
                    zone_file=args.zone_directory / name,
                    declaration_file=(
                        args.managed_zone_directory / f"{name}.conf"
                    ),
                    managed_index=args.managed_config,
                    disabled_root=args.disabled_root,
                    root_config=args.root_config,
                )
                result = ZoneRestoreTransaction(
                    args.manifest_directory,
                ).apply(plan, commit=args.commit)
            except (ZoneRestoreError, OSError) as exc:
                print(f"BŁĄD: {exc}", file=sys.stderr)
                return 2
            if args.json:
                print(
                    json.dumps(
                        asdict(result), ensure_ascii=False, indent=2
                    )
                )
            else:
                print(f"Transakcja: {result.transaction_id}")
                print(f"Strefa:     {result.zone}")
                print(f"Status:     {result.status}")
                print(f"Commit:     {'TAK' if result.committed else 'NIE'}")
                print(f"Rollback:   {'TAK' if result.rolled_back else 'NIE'}")
                if result.manifest:
                    print(f"Manifest:   {result.manifest}")
                print("\nEtapy:")
                for step in result.steps:
                    marker = "OK" if step.ok else "BŁĄD"
                    print(f"[{marker}] {step.name}: {step.message}")
            return (
                0
                if result.ok
                and result.status in {"DRY-RUN", "RESTORED"}
                else 2
            )
        if args.zone_command == "disable":
            name = args.name.strip().rstrip(".").casefold()
            try:
                plan = ZoneDisableTransaction.plan(
                    name,
                    zone_file=args.zone_directory / name,
                    declaration_file=(
                        args.managed_zone_directory / f"{name}.conf"
                    ),
                    managed_index=args.managed_config,
                    root_config=args.root_config,
                    disabled_root=args.disabled_root,
                    reason=args.reason,
                )
                result = ZoneDisableTransaction(
                    args.manifest_directory,
                ).apply(plan, commit=args.commit)
            except (ZoneDisableError, OSError) as exc:
                print(f"BŁĄD: {exc}", file=sys.stderr)
                return 2
            if args.json:
                print(
                    json.dumps(
                        asdict(result), ensure_ascii=False, indent=2
                    )
                )
            else:
                print(f"Transakcja: {result.transaction_id}")
                print(f"Strefa:     {result.zone}")
                print(f"Status:     {result.status}")
                print(f"Przyczyna:  {result.reason}")
                print(f"Commit:     {'TAK' if result.committed else 'NIE'}")
                print(f"Rollback:   {'TAK' if result.rolled_back else 'NIE'}")
                if result.manifest:
                    print(f"Manifest:   {result.manifest}")
                print("\nEtapy:")
                for step in result.steps:
                    marker = "OK" if step.ok else "BŁĄD"
                    print(f"[{marker}] {step.name}: {step.message}")
            return (
                0
                if result.ok
                and result.status in {"DRY-RUN", "DISABLED"}
                else 2
            )
        try:
            plan = ZoneLifecyclePlanner(zones).plan_create(
                ZoneCreateRequest(
                    name=args.name,
                    primary_ns=args.primary_ns,
                    admin=args.admin,
                    nameservers=tuple(args.nameservers),
                    zone_directory=args.zone_directory,
                    managed_config=args.managed_config,
                    managed_zone_directory=args.managed_zone_directory,
                    apex_ipv4=args.ipv4,
                    apex_ipv6=args.ipv6,
                    add_www=args.www,
                    group=args.group,
                    groups_config=args.groups_config,
                    refresh=args.refresh,
                    retry=args.retry,
                    expire=args.expire,
                    negative_ttl=args.minimum,
                )
            )
        except ZoneLifecycleError as exc:
            print(f"BŁĄD: {exc}", file=sys.stderr)
            return 2
        if args.zone_command == "create":
            result = ZoneCreateTransaction(
                args.manifest_directory,
                root_config=args.root_config,
            ).apply(
                plan,
                commit=args.commit,
                activate=args.commit,
            )
            if args.json:
                print(
                    json.dumps(
                        asdict(result),
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                print(f"Transakcja: {result.transaction_id}")
                print(f"Strefa:     {result.zone}")
                print(f"Status:     {result.status}")
                print(f"Commit:     {'TAK' if result.committed else 'NIE'}")
                print(f"Rollback:   {'TAK' if result.rolled_back else 'NIE'}")
                if result.manifest:
                    print(f"Manifest:   {result.manifest}")
                print("\nEtapy:")
                for step in result.steps:
                    marker = "OK" if step.ok else "BŁĄD"
                    print(f"[{marker}] {step.name}: {step.message}")
            return (
                0
                if result.ok and result.status in {"DRY-RUN", "COMMIT"}
                else 2
            )
        if args.json:
            print(
                json.dumps(
                    plan.to_dict(),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print("PLAN UTWORZENIA STREFY — BEZ ZMIAN W SYSTEMIE")
            print(f"Strefa:       {plan.zone_name}")
            print(f"Plik:         {plan.zone_file}")
            print(f"Konfiguracja: {plan.managed_config}")
            print(f"Deklaracja:   {plan.zone_declaration_file}")
            print(f"Serial:       {plan.serial}")
            print("\nPlik strefy:\n")
            print(plan.zone_text, end="")
            print("\nDeklaracja BIND:\n")
            print(plan.bind_declaration, end="")
            print("\nPlanowane etapy:")
            for action in plan.actions:
                print(f"- {action}")
        return 0
    if args.command == "domains":
        if args.grouped:
            print("\n".join(grouped_lines(config, zones)))
        else:
            for zone in zones:
                print(zone.name)
        return 0
    if args.command == "groups":
        print("\n".join(grouped_lines(config, zones)))
        return 0
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("BŁĄD: TUI wymaga interaktywnego terminala. Użyj: zctl domains", file=sys.stderr)
        return 2
    CursesApp(
        zones,
        BindService(config),
        config.group_order,
        config=config,
    ).run()
    return 0


def deprecated_main(argv: list[str] | None = None) -> int:
    print(
        "UWAGA: polecenie 'elkman-dns' jest przestarzałe; użyj 'zctl'.",
        file=sys.stderr,
    )
    return main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
