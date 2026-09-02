# Architektura

> Wygenerowano z importów AST: `2026-08-18T12:59:46+02:00`.

## `src/elkman_dns/__init__.py`

Zgodna nazwa historyczna; nowy kod powinien używać pakietu zonectl.

**Importy:**

- `__future__: annotations`
- `zonectl: __path__, __version__`

## `src/zonectl/__init__.py`

ZoneCTL — Transactional DNS Management Toolkit.

## `src/zonectl/cli.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `argparse`
- `json`
- `sys`
- `dataclasses: asdict`
- `pathlib: Path`
- `: __version__`
- `core.bind: BindService`
- `core.bind_access_inventory: BindAccessInventoryError, BindAccessInventoryReader`
- `core.bind_access_audit: BindAccessAuditor`
- `core.bind_environment_report: BindEnvironmentReporter`
- `core.rpz_managed_plan: RpzManagedPlanner`
- `core.rpz_managed_install: RpzManagedInstallDryRun, RpzManagedInstallTransaction`
- `core.rpz_external_migration_plan: RpzExternalMigrationPlanner`
- `core.rpz_external_migration_dry_run: RpzExternalMigrationDryRun`
- `core.rpz_external_migration_transaction: RpzExternalMigrationTransaction`
- `core.bind_onboarding_report: BindOnboardingReporter`
- `core.discovery: BindDiscoveryError`
- `core.bind_acl_plan: BindAclPlanError, BindAclPlanner`
- `core.bind_acl_transaction: BindAclTransaction`
- `core.bind_secondary_report: BindSecondaryReporter`
- `core.bind_secondary_plan: BindSecondaryPlanError, BindSecondaryPlanner`
- `core.bind_secondary_transaction: BindSecondaryTransaction`
- `core.bind_zone_secondary: BindZoneSecondaryError, BindZoneSecondaryPlanner`
- `core.config: DEFAULT_CONFIG, DEFAULT_GROUPS, DEFAULT_ZONES, ToolkitConfig`
- `core.dnssec_enable_plan: DnssecEnablePlanError, DnssecEnablePlanner`
- `core.dnssec_enable_transaction: DnssecEnableTransaction`
- `core.dnssec_disable_transaction: DnssecDisableTransaction`
- `core.dnssec_finalize_serial: DnssecFinalizeSerialTransaction`
- `core.dnssec_disable_plan: DnssecDisablePlanError, DnssecDisablePlanner`
- `core.dnssec_withdrawal_backup: DnssecWithdrawalBackup`
- `core.dnssec_withdrawal_check: DnssecWithdrawalChecker`
- `core.dnssec_withdrawal_confirm: DnssecWithdrawalConfirmTransaction`
- `core.dnssec_ds_check: DnssecDsChecker`
- `core.dnssec_confirm_ds: DnssecConfirmDsTransaction`
- `core.dnssec_guidance: build_dnssec_guidance`
- `core.dnssec_report: DnssecReporter`
- `core.transaction: TransactionEngine, TransactionResult`
- `core.zone_create_transaction: ZoneCreateTransaction`
- `core.zone_disable_transaction: ZoneDisableError, ZoneDisableTransaction`
- `core.zone_restore_transaction: ZoneRestoreError, ZoneRestoreTransaction`
- `core.zone_quarantine: ZoneQuarantineError, ZoneQuarantineTransaction`
- `core.zone_quarantine_restore: QuarantineRestoreError, QuarantineRestoreTransaction`
- `core.zone_lifecycle: ZoneCreateRequest, ZoneLifecycleError, ZoneLifecyclePlanner`
- `core.zone_inventory: ZoneInventory`
- `core.managed_zone_migration: ManagedZoneMigrationError, ManagedZoneMigrationPlanner`
- `core.managed_zone_migration_transaction: ManagedZoneMigrationTransaction`
- `presentation: transaction_exit_code, transaction_lines`
- `ui.curses_app: CursesApp`

## `src/zonectl/core/__init__.py`

Core services for ZoneCTL.

## `src/zonectl/core/git_history.py`

Opcjonalne, lokalne repozytorium dodatkowej historii plików stref. Moduł jest
domyślnie wyłączony, uruchamia Git bez powłoki i hooków, wymusza prywatny
katalog bez `remote`, kopiuje atomowo tylko plik strefy wybrany przez
`ToolkitConfig` i odrzuca profil RPZ. Snapshot nie uczestniczy w rollbacku i
nie zastępuje backupu transakcyjnego ani backupu hosta.

## `src/zonectl/core/audit.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `json`
- `os`
- `pwd`
- `socket`
- `dataclasses: asdict, dataclass`
- `datetime: datetime, timezone`
- `pathlib: Path`
- `typing: Any`

## `src/zonectl/core/bind.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `time`
- `config: ToolkitConfig`
- `models: Health, Zone, ZoneStatus`
- `runner: run`
- `zone_parser: DNSRecord, ZoneRecordParser`

## `src/zonectl/core/bind_access_audit.py`

Safety audit for BIND ACLs and secondary server groups.

**Importy:**

- `__future__: annotations`
- `ipaddress`
- `collections: Counter`
- `dataclasses: asdict, dataclass`
- `pathlib: Path`
- `bind_access_inventory: BindAccessInventory, BindListDefinition`

## `src/zonectl/core/bind_access_inventory.py`

Read-only inventory of BIND ACLs and named secondary server groups.

**Importy:**

- `__future__: annotations`
- `re`
- `dataclasses: asdict, dataclass`
- `pathlib: Path`
- `discovery: BindConfigDiscovery, BindDiscoveryError`

## `src/zonectl/core/bind_acl_plan.py`

Read-only, validated cleanup plan for one BIND ACL.

**Importy:**

- `__future__: annotations`
- `difflib`
- `ipaddress`
- `re`
- `shutil`
- `tempfile`
- `dataclasses: asdict, dataclass`
- `pathlib: Path`
- `bind_access_inventory: BindAccessInventoryReader`
- `runner: run`
- `discovery: BindConfigDiscovery`

## `src/zonectl/core/bind_acl_transaction.py`

Transactional application of a validated BIND ACL plan.

**Importy:**

- `__future__: annotations`
- `json`
- `os`
- `shutil`
- `tempfile`
- `uuid`
- `dataclasses: asdict, dataclass, field`
- `datetime: datetime, timezone`
- `pathlib: Path`
- `typing: Callable`
- `bind_acl_plan: BindAclPlan`
- `runner: run`

## `src/zonectl/core/bind_bootstrap.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `json`
- `os`
- `stat`
- `tempfile`
- `uuid`
- `dataclasses: asdict, dataclass, field`
- `datetime: datetime, timezone`
- `pathlib: Path`
- `typing: Callable`
- `runner: run`

## `src/zonectl/core/bind_config.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `re`
- `pathlib: Path`
- `models: Zone`

## `src/zonectl/core/bind_environment_report.py`

Odczytowa autodetekcja środowiska BIND i integracji RPZ.

**Importy:**

- `__future__: annotations`
- `re`
- `time`
- `dataclasses: asdict, dataclass`
- `pathlib: Path`
- `typing: Callable`
- `discovery: BindConfigDiscovery, BindDiscoveryError, ZoneConfig`
- `runner: CommandResult, run`

## `src/zonectl/core/bind_onboarding_report.py`

Odczytowy raport gotowości istniejącego BIND do importu przez ZoneCTL.

**Importy:**

- `__future__: annotations`
- `dataclasses: asdict, dataclass`
- `pathlib: Path`
- `bind_access_inventory: BindAccessInventoryReader`
- `bind_environment_report: BindEnvironmentReporter`
- `managed_zone_migration: ManagedZoneMigrationPlanner`

## `src/zonectl/core/bind_secondary_plan.py`

Read-only validated plan for changing one BIND secondary group.

**Importy:**

- `__future__: annotations`
- `difflib`
- `ipaddress`
- `re`
- `shutil`
- `tempfile`
- `dataclasses: asdict, dataclass`
- `pathlib: Path`
- `bind_access_inventory: BindAccessInventoryReader`
- `bind_secondary_report: BindSecondaryReporter`
- `discovery: BindConfigDiscovery`
- `runner: run`

## `src/zonectl/core/bind_secondary_report.py`

Read-only impact report for BIND secondary/notify groups.

**Importy:**

- `__future__: annotations`
- `re`
- `dataclasses: asdict, dataclass`
- `bind_access_inventory: BindAccessInventory`

## `src/zonectl/core/bind_secondary_transaction.py`

Transactional application of a validated BIND secondary-group plan.

**Importy:**

- `__future__: annotations`
- `json`
- `os`
- `shutil`
- `tempfile`
- `uuid`
- `dataclasses: asdict, dataclass, field`
- `datetime: datetime, timezone`
- `pathlib: Path`
- `typing: Callable`
- `bind_secondary_plan: BindSecondaryPlan`
- `runner: run`

## `src/zonectl/core/bind_zone_secondary.py`

Plan assignment of one primary zone to logical secondary groups.

**Importy:**

- `__future__: annotations`
- `difflib`
- `re`
- `dataclasses: dataclass`
- `pathlib: Path`
- `bind_access_inventory: BindAccessInventoryReader`
- `bind_secondary_plan: BindSecondaryPlan, BindSecondaryPlanner`
- `bind_secondary_report: BindSecondaryReporter`
- `discovery: BindConfigDiscovery, BindDiscoveryError`
- `managed_zone_migration: ManagedZoneMigrationPlanner`

## `src/zonectl/core/bulk_operations.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `re`
- `shlex`
- `dataclasses: dataclass, replace`
- `enum: Enum`
- `record_filter: RecordFilter, RecordFilterError`
- `record_validation: validate_record`
- `zone_model: ZoneModel, ZoneRecordView`
- `zone_parser: DNSRecord`

## `src/zonectl/core/config.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `configparser`
- `pathlib: Path`
- `discovery: BindConfigDiscovery, BindDiscoveryError, DEFAULT_NAMED_CONF, ZoneConfig`
- `models: Zone`
- `paths: DEFAULT_CONFIG, DEFAULT_GROUPS, DEFAULT_ZONES`

## `src/zonectl/core/discovery.py`

Automatyczne wykrywanie stref i plików źródłowych BIND.

**Importy:**

- `__future__: annotations`
- `os`
- `re`
- `dataclasses: dataclass`
- `pathlib: Path`

## `src/zonectl/core/dnssec_confirm_ds.py`

Controlled acknowledgement of a published DS record in BIND KASP.

**Importy:**

- `__future__: annotations`
- `json`
- `os`
- `re`
- `tempfile`
- `uuid`
- `dataclasses: asdict, dataclass, field`
- `datetime: datetime, timezone`
- `pathlib: Path`
- `typing: Callable`
- `dnssec_ds_check: DnssecDsCheck`
- `runner: CommandResult, run`

## `src/zonectl/core/dnssec_disable_plan.py`

Side-effect-free plan for safely withdrawing DNSSEC from a BIND zone.

**Importy:**

- `__future__: annotations`
- `re`
- `dataclasses: asdict, dataclass`
- `pathlib: Path`
- `discovery: ZoneConfig`
- `dnssec_enable_plan: DnssecEnablePlanner`

## `src/zonectl/core/dnssec_disable_transaction.py`

Transakcyjne wycofanie DNSSEC — dwa etapy. BIND nie pozwala po prostu usunąć ``dnssec-policy``: dokumentacja wymaga przejścia przez wbudowaną politykę ``insecure``, bo w przeciwnym razie strefa zostanie ponownie podpisana. Stąd dwa etapy: **Etap ``insecure``** — podmienia ``dnssec-policy default`` na ``dnssec-policy insecure``, zostawiając ``inline-signing``. Bramką jest zniknięcie DS ze wszystkich kontrolowanych resolverów, czyli dokładnie ten sam warunek, który przepuszcza ``withdrawal-confirm``. Dopiero ta zmiana przestawia cel KASP z ``omnipresent`` na ``hidden`` i uruchamia uporządkowane wycofywanie kluczy. **Etap ``finalize``** — usuwa ``dnssec-policy``, ``inline-signing`` i ``key-directory``. Bramką jest potwierdzenie z KASP, że **wszystkie** klucze mają ``goal``, ``dnskey`` i ``ds`` w stanie ``hidden``. Ta bramka jest osiągalna wyłącznie po etapie pierwszym. W obu etapach brak ``--commit`` oznacza dry-run, każde niepowodzenie walidacji powoduje pełny rollback deklaracji z backupu, a klucze i pakiet odtworzeniowy pozostają nietknięte.

**Importy:**

- `__future__: annotations`
- `json`
- `os`
- `re`
- `shutil`
- `tempfile`
- `uuid`
- `dataclasses: asdict, dataclass, field`
- `datetime: datetime, timezone`
- `pathlib: Path`
- `typing: Callable`
- `dnssec_disable_plan: DnssecDisablePlan`
- `runner: run`

## `src/zonectl/core/dnssec_ds_check.py`

Read-only verification of DNSSEC delegation and authoritative servers.

**Importy:**

- `__future__: annotations`
- `re`
- `dataclasses: asdict, dataclass`
- `typing: Callable`
- `dnssec_report: _answer_rdata, dnskey_to_ds`
- `runner: CommandResult, run`

## `src/zonectl/core/dnssec_enable_plan.py`

Pozbawiony skutków ubocznych plan włączenia DNSSEC w BIND.

**Importy:**

- `__future__: annotations`
- `difflib`
- `re`
- `dataclasses: asdict, dataclass`
- `pathlib: Path`
- `discovery: ZoneConfig`

## `src/zonectl/core/dnssec_enable_transaction.py`

Transakcyjne zastosowanie planu włączenia DNSSEC.

**Importy:**

- `__future__: annotations`
- `json`
- `os`
- `shutil`
- `tempfile`
- `uuid`
- `dataclasses: asdict, dataclass, field`
- `datetime: datetime, timezone`
- `pathlib: Path`
- `typing: Callable`
- `dnssec_enable_plan: DnssecEnablePlan`
- `runner: run`

## `src/zonectl/core/dnssec_finalize_serial.py`

Safe SOA preparation before DNSSEC withdrawal finalization.

**Importy:**

- `__future__: annotations`
- `os`
- `re`
- `shutil`
- `tempfile`
- `uuid`
- `dataclasses: dataclass, field`
- `datetime: date, datetime`
- `pathlib: Path`
- `typing: Callable`
- `runner: run`
- `soa_serial: bump_document_soa_serial`
- `zone_file_parser: ZoneFileParser`
- `zone_writer: ZoneWriter`

## `src/zonectl/core/dnssec_guidance.py`

Operator guidance derived from the read-only DNSSEC report.

**Importy:**

- `__future__: annotations`
- `re`
- `dataclasses: asdict, dataclass`
- `email.utils: parsedate_to_datetime`
- `typing: TYPE_CHECKING`

## `src/zonectl/core/dnssec_onboarding_audit.py`

Zbiorczy, odczytowy audyt gotowości deklaracji DNSSEC do importu.

**Importy:**

- `__future__: annotations`
- `dataclasses: asdict, dataclass`
- `pathlib: Path`
- `typing: Callable`
- `dnssec_ds_check: DnssecDsChecker`
- `dnssec_report: DnssecReporter`
- `models: Zone`

## `src/zonectl/core/dnssec_report.py`

Odczytowy raport konfiguracji i stanu DNSSEC strefy.

**Importy:**

- `__future__: annotations`
- `base64`
- `hashlib`
- `re`
- `dataclasses: asdict, dataclass`
- `pathlib: Path`
- `typing: Callable`
- `dnssec_guidance: build_dnssec_guidance`
- `models: Zone`
- `runner: CommandResult, run`

## `src/zonectl/core/dnssec_withdrawal_backup.py`

Verified recovery package created before DNSSEC withdrawal.

**Importy:**

- `__future__: annotations`
- `hashlib`
- `json`
- `os`
- `shutil`
- `tempfile`
- `uuid`
- `dataclasses: asdict, dataclass, field`
- `datetime: datetime, timezone`
- `pathlib: Path`
- `dnssec_disable_plan: DnssecDisablePlan`

## `src/zonectl/core/dnssec_withdrawal_check.py`

Read-only confirmation that DS has disappeared everywhere before withdrawal. This is the mirror image of :mod:`dnssec_ds_check`: instead of waiting for a DS record to *appear* at every resolver, it waits for the DS record to *disappear* at every resolver before allowing the operator to run ``rndc dnssec -checkds withdrawn``. As long as any checked resolver still returns a DS record, the result is ``BLOCKED`` and no follow-up command should touch KASP or the registrar.

**Importy:**

- `__future__: annotations`
- `subprocess`
- `dataclasses: asdict, dataclass, field`
- `typing: Callable, Sequence`

## `src/zonectl/core/dnssec_withdrawal_confirm.py`

Guarded confirmation of DNSSEC withdrawal. This is the write-side counterpart to :mod:`dnssec_withdrawal_check`. It is the only place in ZoneCTL allowed to run ``rndc dnssec -checkds withdrawn``, and it refuses to do so unless: 1. the caller passed ``--commit`` (otherwise it is a pure dry-run), and 2. the caller passed the explicit ``--acknowledge-withdrawn`` flag, and 3. a *freshly run* :class:`DnssecWithdrawalChecker` reports ``READY_FOR_WITHDRAWN`` at the moment of the call. Any of those failing leaves BIND, KASP, and the zone completely untouched and returns ``BLOCKED`` with the reason. A successful run writes a manifest recording the DS check that authorized it, so the decision is auditable after the fact.

**Importy:**

- `__future__: annotations`
- `json`
- `os`
- `subprocess`
- `uuid`
- `dataclasses: asdict, dataclass, field`
- `datetime: datetime, timezone`
- `pathlib: Path`
- `typing: Callable, Sequence`
- `dnssec_withdrawal_check: DnssecWithdrawalCheckResult`

## `src/zonectl/core/edit_lock.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `fcntl`
- `getpass`
- `json`
- `os`
- `re`
- `socket`
- `uuid`
- `datetime: datetime, timezone`
- `pathlib: Path`
- `typing: TextIO`

## `src/zonectl/core/managed_zone_migration.py`

Read-only inventory and plans for migrating legacy BIND declarations.

**Importy:**

- `__future__: annotations`
- `difflib`
- `re`
- `dataclasses: asdict, dataclass`
- `pathlib: Path`
- `discovery: BindConfigDiscovery, BindDiscoveryError, ZoneConfig`
- `zone_lifecycle: ZoneLifecycleError, normalize_zone_name`

## `src/zonectl/core/managed_zone_migration_transaction.py`

Transactional migration of one legacy BIND zone declaration.

**Importy:**

- `__future__: annotations`
- `json`
- `os`
- `shutil`
- `tempfile`
- `uuid`
- `dataclasses: asdict, dataclass, field`
- `datetime: datetime, timezone`
- `pathlib: Path`
- `typing: Callable`
- `managed_zone_migration: ManagedZoneMigrationPlan`
- `runner: run`

## `src/zonectl/core/models.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `dataclasses: dataclass`
- `enum: Enum`
- `pathlib: Path`

## `src/zonectl/core/multi_zone_session.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `collections.abc: Callable, Iterable`
- `dataclasses: dataclass, field`
- `models: Zone`
- `zone_edit_session: ZoneEditSession, ZoneSaveResult`

## `src/zonectl/core/paths.py`

Centralne ścieżki systemowe ZoneCTL. Ten moduł jest jedynym źródłem domyślnych ścieżek używanych przez kod Pythona. Na tym etapie zachowujemy dotychczasowe katalogi systemowe. Ich migracja do przestrzeni nazw ZoneCTL zostanie wykonana osobno, z backupem i możliwością wycofania.

**Importy:**

- `pathlib: Path`

## `src/zonectl/core/record_filter.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `re`
- `shlex`
- `dataclasses: dataclass`
- `typing: Iterable`
- `zone_model: ChangeKind, ZoneRecordView`

## `src/zonectl/core/record_validation.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `base64`
- `binascii`
- `ipaddress`
- `re`
- `shlex`
- `dataclasses: dataclass`
- `enum: Enum`
- `typing: Iterable`
- `zone_parser: DNSRecord`

## `src/zonectl/core/rpz_external_migration_dry_run.py`

Isolated dry-run for migration of an EXTERNAL RPZ integration.

**Importy:**

- `__future__: annotations`
- `hashlib`
- `tempfile`
- `dataclasses: asdict, dataclass, field`
- `pathlib: Path`
- `typing: Callable`
- `rpz_external_migration_plan: RpzExternalMigrationPlan`
- `runner: CommandResult, run`

## `src/zonectl/core/rpz_external_migration_plan.py`

Read-only migration plan from an external RPZ updater to ZoneCTL MANAGED.

**Importy:**

- `__future__: annotations`
- `hashlib`
- `stat`
- `dataclasses: asdict, dataclass`
- `pathlib: Path`
- `typing: Callable`
- `bind_environment_report: BindEnvironmentReporter, RpzEnvironment`
- `runner: CommandResult, run`

## `src/zonectl/core/rpz_external_migration_transaction.py`

Guarded transaction migrating an external RPZ updater to MANAGED mode.

**Importy:**

- `__future__: annotations`
- `hashlib`
- `json`
- `os`
- `shutil`
- `tempfile`
- `time`
- `uuid`
- `dataclasses: asdict, dataclass, field`
- `datetime: datetime, timezone`
- `pathlib: Path`
- `typing: Callable`
- `rpz_external_migration_dry_run: RpzExternalMigrationDryRun`
- `rpz_external_migration_plan: RpzExternalMigrationPlan`
- `runner: CommandResult, run`

## `src/zonectl/core/rpz_managed_install.py`

Isolated dry-run for a fresh optional CERT Polska RPZ installation.

**Importy:**

- `__future__: annotations`
- `hashlib`
- `json`
- `os`
- `re`
- `shutil`
- `tempfile`
- `time`
- `uuid`
- `dataclasses: asdict, dataclass, field`
- `datetime: datetime, timezone`
- `pathlib: Path`
- `typing: Callable`
- `urllib.request: urlopen`
- `bind_config: BindConfigDiscovery`
- `rpz_managed_plan: RpzManagedPlan`
- `runner: CommandResult, run`

## `src/zonectl/core/rpz_managed_plan.py`

Read-only plan for an optional ZoneCTL-managed CERT Polska RPZ.

**Importy:**

- `__future__: annotations`
- `dataclasses: asdict, dataclass`
- `pathlib: Path`
- `re`
- `bind_environment_report: BindEnvironmentReporter`

## `src/zonectl/core/runner.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `subprocess`
- `dataclasses: dataclass`

## `src/zonectl/core/soa_serial.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `re`
- `dataclasses: dataclass, replace`
- `datetime: date`
- `zone_document: RawLine, RecordNode, ZoneDocument`
- `zone_parser: DNSRecord`

## `src/zonectl/core/transaction.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `fcntl`
- `hashlib`
- `json`
- `os`
- `shutil`
- `stat`
- `tempfile`
- `time`
- `uuid`
- `dataclasses: asdict, dataclass, field`
- `datetime: datetime, timezone`
- `pathlib: Path`
- `audit: AuditLog`
- `config: ToolkitConfig`
- `models: Zone`
- `paths: AUDIT_LOG, LOCK_DIR, STATE_DIR, TRANSACTION_BACKUP_DIR, TRANSACTION_DIR`
- `runner: CommandResult, run`

## `src/zonectl/core/zone_create_transaction.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `json`
- `os`
- `tempfile`
- `time`
- `uuid`
- `dataclasses: asdict, dataclass, field`
- `datetime: datetime, timezone`
- `pathlib: Path`
- `typing: Callable`
- `runner: run`
- `zone_lifecycle: ZoneCreatePlan`

## `src/zonectl/core/zone_disable_transaction.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `json`
- `getpass`
- `os`
- `tempfile`
- `time`
- `uuid`
- `dataclasses: asdict, dataclass, field`
- `datetime: datetime, timezone`
- `pathlib: Path`
- `typing: Callable`
- `runner: run`

## `src/zonectl/core/zone_document.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `dataclasses: dataclass, field`
- `pathlib: Path`
- `typing: Iterable`
- `zone_parser: DNSRecord`

## `src/zonectl/core/zone_document_adapter.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `dataclasses: dataclass`
- `zone_document: RecordNode, ZoneDocument`
- `zone_model: ChangeKind, ZoneModel`

## `src/zonectl/core/zone_edit_session.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `difflib`
- `os`
- `tempfile`
- `uuid`
- `dataclasses: dataclass`
- `datetime: date, datetime`
- `pathlib: Path`
- `typing: Callable, Protocol`
- `models: Zone`
- `edit_lock: ZoneEditLock`
- `paths: CHANGE_EXPORT_DIR`
- `soa_serial: SoaSerialChange, SoaSerialError, bump_document_soa_serial`
- `transaction: TransactionResult`
- `zone_document: ZoneDocument`
- `zone_document_adapter: ZoneDocumentAdapter`
- `zone_file_parser: ZoneFileParser`
- `zone_model: ZoneModel`
- `zone_writer: ZoneWriter`

## `src/zonectl/core/zone_file_parser.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `dataclasses: dataclass`
- `pathlib: Path`
- `zone_document: BlankLine, Comment, Directive, RawLine, RecordNode, ZoneDocument`
- `zone_parser: DNSRecord`

## `src/zonectl/core/zone_inventory.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `json`
- `dataclasses: asdict, dataclass`
- `datetime: datetime, timezone`
- `pathlib: Path`

## `src/zonectl/core/zone_lifecycle.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `ipaddress`
- `re`
- `dataclasses: asdict, dataclass`
- `datetime: date`
- `pathlib: Path`
- `typing: Iterable`
- `models: Zone`

## `src/zonectl/core/zone_model.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `dataclasses: dataclass`
- `enum: Enum`
- `typing: Iterable`
- `zone_parser: DNSRecord`

## `src/zonectl/core/zone_parser.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `dataclasses: dataclass`

## `src/zonectl/core/zone_quarantine.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `getpass`
- `hashlib`
- `json`
- `os`
- `tempfile`
- `uuid`
- `dataclasses: dataclass, field`
- `datetime: datetime, timezone`
- `pathlib: Path`

## `src/zonectl/core/zone_quarantine_restore.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `hashlib`
- `json`
- `os`
- `tempfile`
- `time`
- `uuid`
- `dataclasses: dataclass, field`
- `datetime: datetime`
- `pathlib: Path`
- `typing: Callable`
- `runner: run`

## `src/zonectl/core/zone_restore_transaction.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `json`
- `os`
- `tempfile`
- `time`
- `uuid`
- `dataclasses: asdict, dataclass, field`
- `datetime: datetime, timezone`
- `pathlib: Path`
- `typing: Callable`
- `runner: run`

## `src/zonectl/core/zone_serializer.py`

Serializacja modelu strefy DNS do pliku kandydata.

**Importy:**

- `__future__: annotations`
- `os`
- `tempfile`
- `pathlib: Path`
- `typing: Iterable, Protocol`
- `zone_parser: DNSRecord`

## `src/zonectl/core/zone_writer.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `os`
- `tempfile`
- `pathlib: Path`
- `zone_document: BlankLine, Comment, Directive, RawLine, RecordNode, ZoneDocument, ZoneNode`
- `zone_parser: DNSRecord`

## `src/zonectl/legacy_v220.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `argparse`
- `configparser`
- `datetime`
- `json`
- `re`
- `tempfile`
- `os`
- `shutil`
- `subprocess`
- `sys`
- `tarfile`
- `time`
- `concurrent.futures: ThreadPoolExecutor, as_completed`
- `pathlib: Path`
- `core.paths: BACKUP_DIR, DEFAULT_CONFIG, DEFAULT_ZONES, DNSSEC_DS_DIR`

## `src/zonectl/presentation.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `core.transaction: TransactionResult`

## `src/zonectl/ui/__init__.py`

Terminal UI for ZoneCTL.

## `src/zonectl/ui/about_view.py`

Treść ekranu F1 prezentującego projekt i jego autorstwo.

**Importy:**

- `__future__: annotations`
- `dataclasses: dataclass`

## `src/zonectl/ui/bind_onboarding_view.py`

Prezentacja raportu pierwszego uruchomienia w TUI.

**Importy:**

- `__future__: annotations`
- `dataclasses: dataclass`
- `core.bind_onboarding_report: BindOnboardingReport`

## `src/zonectl/ui/credits.py`

Dyskretny podpis twórców projektu w głównym widoku TUI.

**Importy:**

- `__future__: annotations`
- `curses`

## `src/zonectl/ui/curses_app.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `zonectl.ui.credits: draw_project_credits`
- `zonectl.core.zone_model: ChangeKind, ZoneChange, ZoneModel`
- `zonectl.ui.dialogs: CursesDialogs`
- `zonectl.ui.function_keys: decode_function_key`
- `zonectl.ui.records.editor: RecordEditor`
- `zonectl.ui.records.new_record: NewRecordDialog`
- `zonectl.ui.records.controller: natural_name_key`
- `zonectl.ui.records.renderer: RecordRenderer`
- `zonectl.ui.zone_create_dialog: ZoneCreateDialog`
- `zonectl.ui.dnssec_status_view: DnssecStatusView`
- `zonectl.ui.rpz_status_view: RpzStatusView`
- `zonectl.ui.bind_onboarding_view: BindOnboardingView`
- `zonectl.ui.about_view: AboutView`
- `zonectl.ui.zone_details_view: ZoneDetailsView`
- `curses`
- `queue`
- `threading`
- `textwrap`
- `concurrent.futures: ThreadPoolExecutor, as_completed`
- `dataclasses: dataclass`
- `pathlib: Path`
- `: __version__`
- `core.bind: BindService`
- `core.bind_access_inventory: BindAccessInventoryError, BindAccessInventoryReader`
- `core.bind_acl_plan: BindAclPlanError, BindAclPlanner`
- `core.bind_acl_transaction: BindAclTransaction`
- `core.bind_environment_report: BindEnvironmentReporter`
- `core.bind_onboarding_report: BindOnboardingReporter`
- `core.bind_secondary_plan: BindSecondaryPlanError, BindSecondaryPlanner`
- `core.bind_secondary_report: BindSecondaryReporter`
- `core.bind_secondary_transaction: BindSecondaryTransaction`
- `core.bind_zone_secondary: BindZoneSecondaryError, BindZoneSecondaryPlanner`
- `core.bulk_operations: BulkOperation, BulkOperationError`
- `core.config: ToolkitConfig`
- `core.dnssec_ds_check: DnssecDsChecker`
- `core.dnssec_confirm_ds: DnssecConfirmDsTransaction`
- `core.dnssec_disable_plan: DnssecDisablePlanner`
- `core.dnssec_disable_transaction: DnssecDisableTransaction`
- `core.dnssec_enable_plan: DnssecEnablePlanner`
- `core.dnssec_enable_transaction: DnssecEnableTransaction`
- `core.dnssec_report: DnssecReporter`
- `core.dnssec_onboarding_audit: DnssecOnboardingAuditor`
- `core.dnssec_withdrawal_backup: DnssecWithdrawalBackup`
- `core.managed_zone_migration: ManagedZoneMigrationError, ManagedZoneMigrationPlanner`
- `core.managed_zone_migration_transaction: ManagedZoneMigrationStep, ManagedZoneMigrationTransaction`
- `core.edit_lock: ZoneEditLockedError`
- `core.models: Health, Zone, ZoneStatus`
- `core.multi_zone_session: MultiZoneEditSession, MultiZoneSessionError`
- `core.paths: EDIT_LOCK_DIR`

## `src/zonectl/ui/dialogs.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `curses`
- `collections.abc: Callable`

## `src/zonectl/ui/dnssec_status_view.py`

Presentation model for the read-only DNSSEC TUI screen.

**Importy:**

- `__future__: annotations`
- `dataclasses: dataclass`
- `re`
- `core.dnssec_ds_check: DnssecDsCheck`
- `core.dnssec_guidance: build_dnssec_guidance`
- `core.dnssec_report: DnssecReport`

## `src/zonectl/ui/form_style.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `curses`

## `src/zonectl/ui/function_keys.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `curses`

## `src/zonectl/ui/records/__init__.py`

Widoki i komponenty obsługi rekordów DNS.

**Importy:**

- `editor: RecordEditor`
- `renderer: RecordRenderer`
- `new_record: NewRecordDialog, RECORD_TYPES`
- `controller: RecordController`

## `src/zonectl/ui/records/controller.py`

Stan, sortowanie i filtrowanie widoku rekordów DNS.

**Importy:**

- `__future__: annotations`
- `collections.abc: Sequence`
- `re`
- `zonectl.core.zone_model: ZoneModel, ZoneRecordView`

## `src/zonectl/ui/records/editor.py`

Formularz edycji rekordów DNS w interfejsie curses.

**Importy:**

- `__future__: annotations`
- `typing: Any`
- `curses`
- `core.models: Zone`
- `core.record_validation: SUPPORTED_RECORD_TYPES, validate_rdata`
- `core.zone_parser: DNSRecord`
- `function_keys: decode_function_key`
- `form_style: active_field_attr, field_marker`

## `src/zonectl/ui/records/keybindings.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `dataclasses: dataclass`
- `typing: Sequence`

## `src/zonectl/ui/records/new_record.py`

Interaktywny kreator nowych rekordów DNS.

**Importy:**

- `__future__: annotations`
- `collections.abc: Iterable`
- `ipaddress: IPv4Address, IPv6Address`
- `curses`
- `core.models: Zone`
- `core.record_validation: SUPPORTED_RECORD_TYPES, validate_rdata`
- `core.zone_parser: DNSRecord`
- `form_style: active_field_attr, field_marker`

## `src/zonectl/ui/records/renderer.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `curses`
- `collections.abc: Sequence`
- `zonectl.core.zone_model: ChangeKind, ZoneRecordView`
- `zonectl.ui.records.keybindings: RECORD_VIEW_BINDINGS, render_footer`

## `src/zonectl/ui/rpz_status_view.py`

Model prezentacyjny panelu stanu integracji RPZ.

**Importy:**

- `__future__: annotations`
- `dataclasses: dataclass`
- `core.bind_environment_report: RpzEnvironment`

## `src/zonectl/ui/zone_create_dialog.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `curses`
- `dataclasses: dataclass`
- `function_keys: decode_function_key`
- `form_style: active_field_attr, field_marker`

## `src/zonectl/ui/zone_details_view.py`

Model prezentacyjny stałego panelu szczegółów strefy.

**Importy:**

- `__future__: annotations`
- `dataclasses: dataclass`
- `core.models: Zone, ZoneStatus`
