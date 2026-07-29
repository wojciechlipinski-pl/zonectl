# Architektura

> Wygenerowano z importów AST: `2026-07-29T18:37:27+02:00`.

## `src/elkman_dns/__init__.py`

elkman DNS Toolkit.

## `src/elkman_dns/cli.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `argparse`
- `json`
- `sys`
- `pathlib: Path`
- `: __version__`
- `core.bind: BindService`
- `core.config: DEFAULT_CONFIG, DEFAULT_GROUPS, DEFAULT_ZONES, ToolkitConfig`
- `core.transaction: TransactionEngine, TransactionResult`
- `ui.curses_app: CursesApp`

## `src/elkman_dns/core/__init__.py`

Core services for elkman DNS Toolkit.

## `src/elkman_dns/core/audit.py`

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

## `src/elkman_dns/core/bind.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `config: ToolkitConfig`
- `models: Health, Zone, ZoneStatus`
- `runner: run`
- `zone_parser: DNSRecord, ZoneRecordParser`

## `src/elkman_dns/core/bind_config.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `re`
- `pathlib: Path`
- `models: Zone`

## `src/elkman_dns/core/config.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `configparser`
- `pathlib: Path`
- `discovery: BindConfigDiscovery, BindDiscoveryError, DEFAULT_NAMED_CONF, ZoneConfig`
- `models: Zone`

## `src/elkman_dns/core/discovery.py`

Automatyczne wykrywanie stref i plików źródłowych BIND.

**Importy:**

- `__future__: annotations`
- `os`
- `re`
- `dataclasses: dataclass`
- `pathlib: Path`

## `src/elkman_dns/core/models.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `dataclasses: dataclass`
- `enum: Enum`
- `pathlib: Path`

## `src/elkman_dns/core/runner.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `subprocess`
- `dataclasses: dataclass`

## `src/elkman_dns/core/soa_serial.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `re`
- `dataclasses: dataclass, replace`
- `datetime: date`
- `zone_document: RawLine, RecordNode, ZoneDocument`
- `zone_parser: DNSRecord`

## `src/elkman_dns/core/transaction.py`

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
- `datetime: datetime`
- `pathlib: Path`
- `audit: AuditLog`
- `config: ToolkitConfig`
- `models: Zone`
- `runner: CommandResult, run`

## `src/elkman_dns/core/zone_document.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `dataclasses: dataclass, field`
- `pathlib: Path`
- `typing: Iterable`
- `zone_parser: DNSRecord`

## `src/elkman_dns/core/zone_document_adapter.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `dataclasses: dataclass`
- `zone_document: RecordNode, ZoneDocument`
- `zone_model: ChangeKind, ZoneModel`

## `src/elkman_dns/core/zone_edit_session.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `dataclasses: dataclass`
- `datetime: date`
- `pathlib: Path`
- `typing: Callable, Protocol`
- `models: Zone`
- `soa_serial: SoaSerialChange, SoaSerialError, bump_document_soa_serial`
- `transaction: TransactionResult`
- `zone_document: ZoneDocument`
- `zone_document_adapter: ZoneDocumentAdapter`
- `zone_file_parser: ZoneFileParser`
- `zone_model: ZoneModel`
- `zone_writer: ZoneWriter`

## `src/elkman_dns/core/zone_file_parser.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `dataclasses: dataclass`
- `pathlib: Path`
- `zone_document: BlankLine, Comment, Directive, RawLine, RecordNode, ZoneDocument`
- `zone_parser: DNSRecord`

## `src/elkman_dns/core/zone_model.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `dataclasses: dataclass`
- `enum: Enum`
- `typing: Iterable`
- `zone_parser: DNSRecord`

## `src/elkman_dns/core/zone_parser.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `dataclasses: dataclass`

## `src/elkman_dns/core/zone_serializer.py`

Serializacja modelu strefy DNS do pliku kandydata.

**Importy:**

- `__future__: annotations`
- `os`
- `tempfile`
- `pathlib: Path`
- `typing: Iterable, Protocol`
- `zone_parser: DNSRecord`

## `src/elkman_dns/core/zone_writer.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `os`
- `tempfile`
- `pathlib: Path`
- `zone_document: BlankLine, Comment, Directive, RawLine, RecordNode, ZoneDocument, ZoneNode`
- `zone_parser: DNSRecord`

## `src/elkman_dns/legacy_v220.py`

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

## `src/elkman_dns/ui/__init__.py`

Terminal UI for elkman DNS Toolkit.

## `src/elkman_dns/ui/credits.py`

Dyskretny podpis twórców projektu w głównym widoku TUI.

**Importy:**

- `__future__: annotations`
- `curses`

## `src/elkman_dns/ui/curses_app.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `elkman_dns.ui.credits: draw_project_credits`
- `elkman_dns.core.zone_model: ChangeKind, ZoneChange, ZoneModel`
- `elkman_dns.ui.dialogs: CursesDialogs`
- `elkman_dns.ui.records.editor: RecordEditor`
- `elkman_dns.ui.records.new_record: NewRecordDialog`
- `elkman_dns.ui.records.renderer: RecordRenderer`
- `curses`
- `queue`
- `threading`
- `concurrent.futures: ThreadPoolExecutor, as_completed`
- `dataclasses: dataclass`
- `: __version__`
- `core.bind: BindService`
- `core.config: ToolkitConfig`
- `core.models: Health, Zone, ZoneStatus`
- `core.transaction: TransactionEngine, TransactionResult`
- `core.zone_edit_session: ZoneEditSession, ZoneEditSessionError`

## `src/elkman_dns/ui/dialogs.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `curses`

## `src/elkman_dns/ui/records/__init__.py`

Widoki i komponenty obsługi rekordów DNS.

**Importy:**

- `editor: RecordEditor`
- `renderer: RecordRenderer`
- `new_record: NewRecordDialog, RECORD_TYPES`
- `controller: RecordController`

## `src/elkman_dns/ui/records/controller.py`

Stan, sortowanie i filtrowanie widoku rekordów DNS.

**Importy:**

- `__future__: annotations`
- `collections.abc: Sequence`
- `elkman_dns.core.zone_model: ZoneModel, ZoneRecordView`

## `src/elkman_dns/ui/records/editor.py`

Formularz edycji rekordów DNS w interfejsie curses.

**Importy:**

- `__future__: annotations`
- `typing: Any`
- `curses`
- `core.models: Zone`
- `core.zone_parser: DNSRecord`

## `src/elkman_dns/ui/records/keybindings.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `dataclasses: dataclass`
- `typing: Sequence`

## `src/elkman_dns/ui/records/new_record.py`

Interaktywny kreator nowych rekordów DNS.

**Importy:**

- `__future__: annotations`
- `collections.abc: Iterable`
- `ipaddress: IPv4Address, IPv6Address`
- `curses`
- `core.models: Zone`
- `core.zone_parser: DNSRecord`

## `src/elkman_dns/ui/records/renderer.py`

Brak docstringa.

**Importy:**

- `__future__: annotations`
- `curses`
- `collections.abc: Sequence`
- `elkman_dns.core.zone_model: ChangeKind, ZoneRecordView`
- `elkman_dns.ui.records.keybindings: render_footer`
