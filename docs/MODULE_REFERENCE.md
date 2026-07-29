# Dokumentacja modułów, klas i funkcji

> Wygenerowano automatycznie: `2026-07-29T18:21:02+02:00`.

Dokument jest wynikiem analizy AST aktualnego kodu w katalogu `src/`.
Pokazuje deklaracje, a nie pełną semantykę implementacji.

## `src/elkman_dns/__init__.py`

elkman DNS Toolkit.

Brak publicznych deklaracji klas lub funkcji.

## `src/elkman_dns/cli.py`

Brak docstringa modułu.

**Najważniejsze importy:**

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

### `def parser() -> argparse.ArgumentParser`

Lokalizacja: linia `15`.

Brak docstringa.

### `def legacy_main(arguments: list[str]) -> int`

Lokalizacja: linia `61`.

Brak docstringa.

### `def grouped_lines(config: ToolkitConfig, zones)`

Lokalizacja: linia `71`.

Brak docstringa.

### `def print_transaction(result: TransactionResult, as_json: bool = False) -> int`

Lokalizacja: linia `85`.

Brak docstringa.

### `def transaction_main(args, config: ToolkitConfig) -> int`

Lokalizacja: linia `110`.

Brak docstringa.

### `def main(argv: list[str] | None = None) -> int`

Lokalizacja: linia `139`.

Brak docstringa.

## `src/elkman_dns/core/__init__.py`

Core services for elkman DNS Toolkit.

Brak publicznych deklaracji klas lub funkcji.

## `src/elkman_dns/core/audit.py`

Brak docstringa modułu.

**Najważniejsze importy:**

- `__future__: annotations`
- `json`
- `os`
- `pwd`
- `socket`
- `dataclasses: asdict, dataclass`
- `datetime: datetime, timezone`
- `pathlib: Path`
- `typing: Any`

### `class AuditEvent`

Lokalizacja: linia `14`.

Brak docstringa.

### `class AuditLog`

Lokalizacja: linia `26`.

Brak docstringa.

**Metody:**

- `def __init__(self, path: Path)` — linia 27, prywatna; brak docstringa.
- `def identity() -> tuple[str, int]` — linia 31, publiczna; brak docstringa.
- `def append(self, transaction_id: str, zone: str, action: str, outcome: str, **details: Any) -> None` — linia 40, publiczna; brak docstringa.
- `def read(self, zone: str | None = None, limit: int = 50) -> list[dict[str, Any]]` — linia 63, publiczna; brak docstringa.

## `src/elkman_dns/core/bind.py`

Brak docstringa modułu.

**Najważniejsze importy:**

- `__future__: annotations`
- `config: ToolkitConfig`
- `models: Health, Zone, ZoneStatus`
- `runner: run`
- `zone_parser: DNSRecord, ZoneRecordParser`

### `class BindService`

Lokalizacja: linia `9`.

Read-only BIND status service used by the Sprint 1 dashboard.

**Metody:**

- `def __init__(self, config: ToolkitConfig)` — linia 12, prywatna; brak docstringa.
- `def serial(self, server: str, zone: str) -> str | None` — linia 20, publiczna; brak docstringa.
- `def dnssec_enabled(self, zone: str) -> bool | None` — linia 30, publiczna; brak docstringa.
- `def zone_records(self, zone: Zone) -> tuple[list[str], str | None]` — linia 38, publiczna; zwraca kanoniczną listę rekordów z aktywnego pliku strefy.
- `def parsed_zone_records(self, zone: Zone) -> tuple[list[DNSRecord], str | None]` — linia 84, publiczna; zwraca rekordy strefy przekształcone do modelu dnsrecord.
- `def quick_status(self, zone: Zone) -> ZoneStatus` — linia 112, publiczna; brak docstringa.

## `src/elkman_dns/core/bind_config.py`

Brak docstringa modułu.

**Najważniejsze importy:**

- `__future__: annotations`
- `re`
- `pathlib: Path`
- `models: Zone`

### `class BindConfigError(RuntimeError)`

Lokalizacja: linia `9`.

Błąd odczytu lub analizy konfiguracji BIND.

### `class BindConfigDiscovery`

Lokalizacja: linia `13`.

Odczytuje strefy bezpośrednio z konfiguracji BIND.

**Metody:**

- `def __init__(self, root: Path = Path('/etc/bind/named.conf.local'))` — linia 50, prywatna; brak docstringa.
- `def zones(self) -> list[Zone]` — linia 54, publiczna; zwróć wszystkie strefy znalezione w konfiguracji bind.
- `def _read_file(self, path: Path, discovered: dict[str, Zone]) -> None` — linia 63, prywatna; brak docstringa.
- `def _resolve_include(parent_file: Path, raw_path: str) -> Path` — linia 101, prywatna; brak docstringa.
- `def _zone_blocks(self, text: str, source: Path)` — linia 109, prywatna; brak docstringa.
- `def _matching_brace(text: str, opening: int) -> int | None` — linia 147, prywatna; brak docstringa.
- `def _zone_from_block(self, name: str, block: str, source: Path) -> Zone` — linia 177, prywatna; brak docstringa.
- `def _group_for(name: str, source: Path, block: str) -> str` — linia 242, prywatna; brak docstringa.
- `def _strip_comments(text: str) -> str` — linia 266, prywatna; usuń komentarze //, # i /* ...

## `src/elkman_dns/core/config.py`

Brak docstringa modułu.

**Najważniejsze importy:**

- `__future__: annotations`
- `configparser`
- `pathlib: Path`
- `discovery: BindConfigDiscovery, BindDiscoveryError, DEFAULT_NAMED_CONF, ZoneConfig`
- `models: Zone`

### `def _yes(value: str | None, default: bool) -> bool`

Lokalizacja: linia `20`.

Brak docstringa.

### `def _unquote(value: str) -> str`

Lokalizacja: linia `33`.

Brak docstringa.

### `def load_groups_yaml(path: Path) -> tuple[list[str], dict[str, str]]`

Lokalizacja: linia `46`.

Odczytaj uproszczony format groups.yaml bez PyYAML.

### `class ToolkitConfig`

Lokalizacja: linia `120`.

Konfiguracja elkman DNS Toolkit.

**Metody:**

- `def __init__(self, config_path: Path = DEFAULT_CONFIG, zones_path: Path = DEFAULT_ZONES, groups_path: Path = DEFAULT_GROUPS)` — linia 134, prywatna; brak docstringa.
- `def load(self) -> 'ToolkitConfig'` — linia 153, publiczna; brak docstringa.
- `def toolkit(self) -> configparser.SectionProxy` — linia 186, publiczna; brak docstringa.
- `def auto_discover_zones(self) -> bool` — linia 190, publiczna; brak docstringa.
- `def bind_config_path(self) -> Path` — linia 197, publiczna; brak docstringa.
- `def _normalise_zone_name(name: str) -> str` — linia 206, prywatna; brak docstringa.
- `def _discover_bind_zones(self) -> None` — linia 209, prywatna; brak docstringa.
- `def discovered_zone(self, name: str) -> ZoneConfig | None` — linia 226, publiczna; brak docstringa.
- `def _zone_override(self, name: str) -> configparser.SectionProxy | None` — linia 234, prywatna; brak docstringa.
- `def _group_for(self, name: str, override: configparser.SectionProxy | None) -> str` — linia 246, prywatna; brak docstringa.
- `def _zone_from_discovery(self, discovered: ZoneConfig) -> Zone | None` — linia 262, prywatna; brak docstringa.
- `def _zones_from_discovery(self) -> list[Zone]` — linia 317, prywatna; brak docstringa.
- `def _zones_from_legacy_config(self) -> list[Zone]` — linia 331, prywatna; tryb zgodności ze starym zones.conf.
- `def zones(self) -> list[Zone]` — linia 396, publiczna; brak docstringa.

## `src/elkman_dns/core/discovery.py`

Automatyczne wykrywanie stref i plików źródłowych BIND.

**Najważniejsze importy:**

- `__future__: annotations`
- `os`
- `re`
- `dataclasses: dataclass`
- `pathlib: Path`

### `class BindDiscoveryError(RuntimeError)`

Lokalizacja: linia `14`.

Błąd odczytu lub interpretacji konfiguracji BIND.

### `class ZoneConfig`

Lokalizacja: linia `19`.

Konfiguracja pojedynczej strefy wykryta z konfiguracji BIND.

**Metody:**

- `def is_primary(self) -> bool` — linia 42, publiczna; brak docstringa.
- `def is_secondary(self) -> bool` — linia 46, publiczna; brak docstringa.
- `def dnssec_enabled(self) -> bool` — linia 50, publiczna; brak docstringa.
- `def editable(self) -> bool` — linia 54, publiczna; brak docstringa.
- `def is_managed_signed_file(self) -> bool` — linia 64, publiczna; brak docstringa.
- `def requires_freeze(self) -> bool` — linia 72, publiczna; journal aktywnej strefy oznacza, że zwykła atomowa podmiana pliku może być niewystarczająca.
- `def save_mode(self) -> str` — linia 83, publiczna; brak docstringa.

### `class DiscoveryResult`

Lokalizacja: linia `106`.

Wynik przejścia przez konfigurację BIND.

**Metody:**

- `def zone(self, name: str) -> ZoneConfig` — linia 113, publiczna; brak docstringa.

### `class _ConfigSource`

Lokalizacja: linia `137`.

Brak docstringa.

### `class BindConfigDiscovery`

Lokalizacja: linia `142`.

Czyta konfigurację BIND, rozwija include i wykrywa strefy.

**Metody:**

- `def __init__(self, root_config: Path = DEFAULT_NAMED_CONF) -> None` — linia 181, prywatna; brak docstringa.
- `def discover(self) -> DiscoveryResult` — linia 187, publiczna; brak docstringa.
- `def _load_config_tree(self, path: Path, sources: list[_ConfigSource], visited: set[Path], stack: list[Path]) -> None` — linia 217, prywatna; brak docstringa.
- `def _parse_zones(self, source: _ConfigSource) -> list[ZoneConfig]` — linia 273, prywatna; brak docstringa.
- `def _zone_from_block(self, name: str, body: str, config_file: Path) -> ZoneConfig` — linia 321, prywatna; brak docstringa.
- `def _match_value(pattern: re.Pattern[str], text: str, default: str | None) -> str | None` — linia 429, prywatna; brak docstringa.
- `def _resolve_config_path(raw_path: str, parent: Path) -> Path` — linia 442, prywatna; brak docstringa.
- `def _resolve_zone_path(raw_path: str, config_parent: Path) -> Path` — linia 454, prywatna; brak docstringa.
- `def _find_block_end(text: str, opening: int, source_path: Path) -> int` — linia 470, prywatna; brak docstringa.
- `def _strip_comments(text: str) -> str` — linia 509, prywatna; usuwa komentarze //, # i /* ...

## `src/elkman_dns/core/models.py`

Brak docstringa modułu.

**Najważniejsze importy:**

- `__future__: annotations`
- `dataclasses: dataclass`
- `enum: Enum`
- `pathlib: Path`

### `class Health(str, Enum)`

Lokalizacja: linia `8`.

Brak docstringa.

### `class Zone`

Lokalizacja: linia `16`.

Brak docstringa.

### `class ZoneStatus`

Lokalizacja: linia `28`.

Brak docstringa.

## `src/elkman_dns/core/runner.py`

Brak docstringa modułu.

**Najważniejsze importy:**

- `__future__: annotations`
- `subprocess`
- `dataclasses: dataclass`

### `class CommandResult`

Lokalizacja: linia `8`.

Brak docstringa.

### `def run(command: list[str], timeout: int = 10) -> CommandResult`

Lokalizacja: linia `14`.

Brak docstringa.

## `src/elkman_dns/core/soa_serial.py`

Brak docstringa modułu.

**Najważniejsze importy:**

- `__future__: annotations`
- `re`
- `dataclasses: dataclass, replace`
- `datetime: date`
- `zone_document: RawLine, RecordNode, ZoneDocument`
- `zone_parser: DNSRecord`

### `class SoaSerialError(RuntimeError)`

Lokalizacja: linia `11`.

Błąd odczytu lub aktualizacji serialu SOA.

### `class SoaSerialChange`

Lokalizacja: linia `16`.

Brak docstringa.

### `def next_soa_serial(current: int, *, today: date | None = None) -> int`

Lokalizacja: linia `33`.

Wylicza kolejny serial w formacie RRRRMMDDNN.

### `def _replace_record_serial(record: DNSRecord, new_serial: int) -> DNSRecord`

Lokalizacja: linia `72`.

Brak docstringa.

### `def bump_document_soa_serial(document: ZoneDocument, *, today: date | None = None) -> SoaSerialChange`

Lokalizacja: linia `100`.

Podbija serial pierwszego rekordu SOA w ZoneDocument.

## `src/elkman_dns/core/transaction.py`

Brak docstringa modułu.

**Najważniejsze importy:**

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

### `class StepResult`

Lokalizacja: linia `23`.

Brak docstringa.

### `class TransactionResult`

Lokalizacja: linia `33`.

Brak docstringa.

**Metody:**

- `def ok(self) -> bool` — linia 43, publiczna; brak docstringa.

### `class ZoneLock`

Lokalizacja: linia `47`.

Brak docstringa.

**Metody:**

- `def __init__(self, path: Path)` — linia 48, prywatna; brak docstringa.
- `def __enter__(self)` — linia 52, prywatna; brak docstringa.
- `def __exit__(self, exc_type, exc, tb)` — linia 66, prywatna; brak docstringa.

### `class TransactionEngine`

Lokalizacja: linia `76`.

Atomic zone-file replacement with validation, backup, reload and rollback.

**Metody:**

- `def __init__(self, config: ToolkitConfig)` — linia 79, prywatna; brak docstringa.
- `def find_zone(self, name: str) -> Zone` — linia 90, publiczna; brak docstringa.
- `def _safe_zone_name(name: str) -> str` — linia 98, prywatna; brak docstringa.
- `def _digest(path: Path) -> str` — linia 102, prywatna; brak docstringa.
- `def _step_command(self, name: str, command: list[str], timeout: int | None = None) -> StepResult` — linia 109, prywatna; brak docstringa.
- `def _zone_validation(self, zone: Zone, candidate: Path) -> StepResult` — linia 114, prywatna; brak docstringa.
- `def _config_validation(self) -> StepResult` — linia 117, prywatna; brak docstringa.
- `def _zone_serial(self, zone: Zone, candidate: Path) -> str | None` — linia 120, prywatna; brak docstringa.
- `def _serial(self, zone: str) -> str | None` — linia 130, prywatna; brak docstringa.
- `def _loaded_serial(self, zone: str) -> str | None` — linia 137, prywatna; brak docstringa.
- `def _verify_loaded_zone(self, zone: Zone, expected_serial: str) -> tuple[StepResult, str | None, str | None]` — linia 146, prywatna; brak docstringa.
- `def validate(self, zone_name: str, source: Path | None = None) -> TransactionResult` — linia 166, publiczna; brak docstringa.
- `def verify(self, zone_name: str) -> TransactionResult` — linia 184, publiczna; brak docstringa.
- `def apply(self, zone_name: str, source: Path, commit: bool = False) -> TransactionResult` — linia 277, publiczna; brak docstringa.
- `def rollback(self, zone_name: str, backup: Path, commit: bool = False) -> TransactionResult` — linia 379, publiczna; brak docstringa.
- `def backups(self, zone_name: str, limit: int = 20) -> list[Path]` — linia 404, publiczna; brak docstringa.
- `def _new_id(self, zone: str) -> str` — linia 411, prywatna; brak docstringa.
- `def _backup(self, zone: Zone, target: Path, txid: str) -> Path` — linia 415, prywatna; brak docstringa.
- `def _atomic_install(source: Path, target: Path) -> None` — linia 436, prywatna; brak docstringa.
- `def _rollback(self, zone: Zone, target: Path, backup: Path) -> StepResult` — linia 463, prywatna; brak docstringa.
- `def _save_manifest(self, result: TransactionResult, extra: dict) -> None` — linia 473, prywatna; brak docstringa.
- `def _finish(self, result: TransactionResult, outcome: str, **extra) -> TransactionResult` — linia 480, prywatna; brak docstringa.

## `src/elkman_dns/core/zone_document.py`

Brak docstringa modułu.

**Najważniejsze importy:**

- `__future__: annotations`
- `dataclasses: dataclass, field`
- `pathlib: Path`
- `typing: Iterable`
- `zone_parser: DNSRecord`

### `class ZoneNode`

Lokalizacja: linia `10`.

Element źródłowego dokumentu strefy.

### `class BlankLine(ZoneNode)`

Lokalizacja: linia `15`.

Brak docstringa.

### `class Comment(ZoneNode)`

Lokalizacja: linia `20`.

Brak docstringa.

**Metody:**

- `def text(self) -> str` — linia 24, publiczna; brak docstringa.

### `class Directive(ZoneNode)`

Lokalizacja: linia `29`.

Brak docstringa.

### `class RecordNode(ZoneNode)`

Lokalizacja: linia `36`.

Brak docstringa.

### `class RawLine(ZoneNode)`

Lokalizacja: linia `44`.

Linia zachowana bez interpretacji.

### `class ZoneDocument`

Lokalizacja: linia `58`.

Brak docstringa.

**Metody:**

- `def records(self) -> list[DNSRecord]` — linia 64, publiczna; brak docstringa.
- `def iter_record_nodes(self) -> Iterable[RecordNode]` — linia 71, publiczna; brak docstringa.
- `def find_record(self, record: DNSRecord) -> RecordNode | None` — linia 76, publiczna; brak docstringa.

## `src/elkman_dns/core/zone_document_adapter.py`

Brak docstringa modułu.

**Najważniejsze importy:**

- `__future__: annotations`
- `dataclasses: dataclass`
- `zone_document: RecordNode, ZoneDocument`
- `zone_model: ChangeKind, ZoneModel`

### `class ZoneDocumentAdapterError(RuntimeError)`

Lokalizacja: linia `9`.

Błąd synchronizacji ZoneModel z ZoneDocument.

### `class _NodeBinding`

Lokalizacja: linia `14`.

Brak docstringa.

### `class ZoneDocumentAdapter`

Lokalizacja: linia `19`.

Łączy bufor edycji ZoneModel z bezstratnym ZoneDocument.

**Metody:**

- `def __init__(self, document: ZoneDocument, model: ZoneModel) -> None` — linia 31, prywatna; brak docstringa.
- `def _bind_existing_records(self) -> None` — linia 44, prywatna; brak docstringa.
- `def apply(self) -> ZoneDocument` — linia 71, publiczna; nanieś bieżące zmiany modelu na dokument.
- `def _apply_add(self, identifier: int, record) -> None` — linia 117, prywatna; brak docstringa.
- `def _remove_abandoned_added_nodes(self, active_identifiers: set[int]) -> None` — linia 140, prywatna; brak docstringa.
- `def discard(self) -> ZoneDocument` — linia 158, publiczna; przywróć dokument do stanu sprzed zmian modelu.

## `src/elkman_dns/core/zone_edit_session.py`

Brak docstringa modułu.

**Najważniejsze importy:**

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

### `class TransactionEngineProtocol(Protocol)`

Lokalizacja: linia `22`.

Brak docstringa.

**Metody:**

- `def apply(self, zone_name: str, source: Path, commit: bool = False) -> TransactionResult` — linia 23, publiczna; brak docstringa.

### `class ZoneEditSessionError(RuntimeError)`

Lokalizacja: linia `32`.

Błąd sesji edycji strefy.

### `class ZoneSaveResult`

Lokalizacja: linia `37`.

Brak docstringa.

**Metody:**

- `def committed(self) -> bool` — linia 42, publiczna; brak docstringa.
- `def ok(self) -> bool` — linia 46, publiczna; brak docstringa.
- `def status(self) -> str` — linia 50, publiczna; brak docstringa.

### `class ZoneEditSession`

Lokalizacja: linia `54`.

Pełna sesja edycji źródłowego pliku strefy.

**Metody:**

- `def __init__(self, zone: Zone, engine: TransactionEngineProtocol, *, writer: ZoneWriter | None = None, candidate_directory: Path | None = None, auto_bump_serial: bool = True, today_provider: Callable[[], date] = date.today) -> None` — linia 68, prywatna; brak docstringa.
- `def source_path(self) -> Path` — linia 100, publiczna; brak docstringa.
- `def dirty(self) -> bool` — linia 109, publiczna; brak docstringa.
- `def change_count(self) -> int` — linia 113, publiczna; brak docstringa.
- `def _load(self) -> None` — linia 116, prywatna; brak docstringa.
- `def _prepare_document(self) -> None` — linia 137, prywatna; brak docstringa.
- `def render_candidate(self) -> str` — linia 162, publiczna; wygeneruj tekst kandydata bez tworzenia pliku.
- `def create_candidate(self) -> Path` — linia 169, publiczna; utwórz bezpieczny plik tymczasowy z bieżącymi zmianami.
- `def save(self, *, commit: bool = False, remove_candidate: bool = True) -> ZoneSaveResult` — linia 186, publiczna; waliduj albo zapisz zmiany przez transactionengine.
- `def discard(self) -> None` — linia 227, publiczna; porzuć wszystkie niezapisane zmiany.
- `def reload(self) -> None` — linia 235, publiczna; ponownie odczytaj aktywny plik strefy.

## `src/elkman_dns/core/zone_file_parser.py`

Brak docstringa modułu.

**Najważniejsze importy:**

- `__future__: annotations`
- `dataclasses: dataclass`
- `pathlib: Path`
- `zone_document: BlankLine, Comment, Directive, RawLine, RecordNode, ZoneDocument`
- `zone_parser: DNSRecord`

### `class ZoneFileParseError(RuntimeError)`

Lokalizacja: linia `17`.

Błąd odczytu źródłowego pliku strefy.

### `class _Token`

Lokalizacja: linia `22`.

Brak docstringa.

### `class ZoneFileParser`

Lokalizacja: linia `28`.

Zachowujący formatowanie parser źródłowego pliku strefy.

**Metody:**

- `def parse_file(cls, path: Path) -> ZoneDocument` — linia 100, publiczna; brak docstringa.
- `def parse_text(cls, text: str) -> ZoneDocument` — linia 120, publiczna; brak docstringa.
- `def _parse_directive(cls, raw_line: str) -> Directive | None` — linia 199, prywatna; brak docstringa.
- `def _parse_record_line(cls, raw_line: str, previous_owner: str | None) -> tuple[DNSRecord, bool] | None` — linia 223, prywatna; brak docstringa.
- `def _is_ttl(value: str) -> bool` — linia 314, prywatna; brak docstringa.
- `def _is_record_type(cls, value: str) -> bool` — linia 326, prywatna; brak docstringa.
- `def _normalise_class(value: str) -> str` — linia 337, prywatna; brak docstringa.
- `def _remove_comment(line: str) -> str` — linia 346, prywatna; usuń komentarz rozpoczynający się średnikiem poza cudzysłowem.
- `def _tokenise(line: str) -> list[_Token]` — linia 372, prywatna; podziel linię według białych znaków, zachowując tekst w cudzysłowach.
- `def _parenthesis_delta(line: str) -> int` — linia 425, prywatna; policz nawiasy poza cudzysłowami.

## `src/elkman_dns/core/zone_model.py`

Brak docstringa modułu.

**Najważniejsze importy:**

- `__future__: annotations`
- `dataclasses: dataclass`
- `enum: Enum`
- `typing: Iterable`
- `zone_parser: DNSRecord`

### `class ChangeKind(str, Enum)`

Lokalizacja: linia `10`.

Brak docstringa.

### `class ZoneChange`

Lokalizacja: linia `17`.

Brak docstringa.

**Metody:**

- `def record(self) -> DNSRecord` — linia 23, publiczna; brak docstringa.

### `class ZoneRecordView`

Lokalizacja: linia `34`.

Rekord prezentowany w edytorze wraz ze stanem zmiany.

**Metody:**

- `def deleted(self) -> bool` — linia 42, publiczna; brak docstringa.
- `def marker(self) -> str` — linia 46, publiczna; brak docstringa.

### `class _RecordEntry`

Lokalizacja: linia `56`.

Brak docstringa.

### `class ZoneModel`

Lokalizacja: linia `62`.

Bufor edycji rekordów pojedynczej strefy.

**Metody:**

- `def __init__(self, zone_name: str, records: Iterable[DNSRecord]) -> None` — linia 70, prywatna; brak docstringa.
- `def _allocate_identifier(self) -> int` — linia 89, prywatna; brak docstringa.
- `def _visible_entries(self) -> list[_RecordEntry]` — linia 94, prywatna; brak docstringa.
- `def _entry_at(self, index: int) -> _RecordEntry` — linia 101, prywatna; brak docstringa.
- `def records(self) -> tuple[DNSRecord, ...]` — linia 112, publiczna; brak docstringa.
- `def original_records(self) -> tuple[DNSRecord, ...]` — linia 120, publiczna; brak docstringa.
- `def record_views(self) -> tuple[ZoneRecordView, ...]` — linia 128, publiczna; zwraca rekordy widoczne w edytorze, również usuwane.
- `def pending_changes(self) -> tuple[ZoneChange, ...]` — linia 166, publiczna; brak docstringa.
- `def dirty(self) -> bool` — linia 208, publiczna; brak docstringa.
- `def change_count(self) -> int` — linia 212, publiczna; brak docstringa.
- `def add(self, record: DNSRecord) -> int` — linia 215, publiczna; brak docstringa.
- `def _entry_by_identifier(self, identifier: int) -> _RecordEntry` — linia 226, prywatna; brak docstringa.
- `def replace_by_identifier(self, identifier: int, record: DNSRecord) -> DNSRecord` — linia 235, publiczna; brak docstringa.
- `def delete_by_identifier(self, identifier: int) -> DNSRecord` — linia 251, publiczna; brak docstringa.
- `def replace(self, index: int, record: DNSRecord) -> DNSRecord` — linia 267, publiczna; brak docstringa.
- `def delete(self, index: int) -> DNSRecord` — linia 284, publiczna; brak docstringa.
- `def discard(self) -> None` — linia 303, publiczna; brak docstringa.
- `def accept(self) -> None` — linia 315, publiczna; uznaje aktualny stan za nowy stan bazowy.

## `src/elkman_dns/core/zone_parser.py`

Brak docstringa modułu.

**Najważniejsze importy:**

- `__future__: annotations`
- `dataclasses: dataclass`

### `class DNSRecord`

Lokalizacja: linia `7`.

Brak docstringa.

**Metody:**

- `def relative_owner(self, zone_name: str) -> str` — linia 15, publiczna; brak docstringa.

### `class ZoneRecordParser`

Lokalizacja: linia `30`.

Parser kanonicznego wyjścia `named-checkzone -D`.

**Metody:**

- `def parse_output(cls, output: str) -> list[DNSRecord]` — linia 39, publiczna; brak docstringa.
- `def parse_line(line: str) -> DNSRecord | None` — linia 67, publiczna; oczekiwany format kanoniczny: owner ttl class type rdata rdata pozostaje tekstem, dzięki czemu zachowujemy składnię rekordów txt, soa, mx, srv, caa i innych typów.

## `src/elkman_dns/core/zone_serializer.py`

Serializacja modelu strefy DNS do pliku kandydata.

**Najważniejsze importy:**

- `__future__: annotations`
- `os`
- `tempfile`
- `pathlib: Path`
- `typing: Iterable, Protocol`
- `zone_parser: DNSRecord`

### `class ZoneSerializationError(RuntimeError)`

Lokalizacja: linia `13`.

Błąd podczas serializacji strefy DNS.

### `class ZoneModelProtocol(Protocol)`

Lokalizacja: linia `17`.

Brak docstringa.

**Metody:**

- `def records(self) -> Iterable[DNSRecord]` — linia 19, publiczna; brak docstringa.

### `class ZoneSerializer`

Lokalizacja: linia `23`.

Serializuje rekordy DNS do tekstowego pliku strefy.

**Metody:**

- `def __init__(self, record_separator: str = '\n', final_newline: bool = True) -> None` — linia 35, prywatna; brak docstringa.
- `def _is_deleted(record: DNSRecord) -> bool` — linia 44, prywatna; obsługuje kilka wariantów modelu rekordów.
- `def _normalise_owner(owner: str | None) -> str` — linia 90, prywatna; brak docstringa.
- `def _normalise_class(record_class: str | None) -> str` — linia 96, prywatna; brak docstringa.
- `def _record_owner(record: DNSRecord) -> str` — linia 102, prywatna; brak docstringa.
- `def _record_type(record: DNSRecord) -> str` — linia 118, prywatna; brak docstringa.
- `def _record_rdata(record: DNSRecord) -> str` — linia 134, prywatna; brak docstringa.
- `def _record_ttl(record: DNSRecord) -> int | None` — linia 153, prywatna; brak docstringa.
- `def _record_class(record: DNSRecord) -> str` — linia 174, prywatna; brak docstringa.
- `def render_record(self, record: DNSRecord) -> str` — linia 189, publiczna; brak docstringa.
- `def render_records(self, records: Iterable[DNSRecord]) -> str` — linia 216, publiczna; brak docstringa.
- `def render_model(self, model: ZoneModelProtocol) -> str` — linia 235, publiczna; brak docstringa.
- `def write_candidate(self, model: ZoneModelProtocol, directory: Path | None = None, prefix: str = 'elkman-zone-', suffix: str = '.zone') -> Path` — linia 248, publiczna; brak docstringa.

## `src/elkman_dns/core/zone_writer.py`

Brak docstringa modułu.

**Najważniejsze importy:**

- `__future__: annotations`
- `os`
- `tempfile`
- `pathlib: Path`
- `zone_document: BlankLine, Comment, Directive, RawLine, RecordNode, ZoneDocument, ZoneNode`
- `zone_parser: DNSRecord`

### `class ZoneWriteError(RuntimeError)`

Lokalizacja: linia `19`.

Błąd podczas generowania lub zapisywania dokumentu strefy.

### `class ZoneWriter`

Lokalizacja: linia `23`.

Bezstratny zapis źródłowego dokumentu strefy.

**Metody:**

- `def __init__(self, field_separator: str = '\t') -> None` — linia 35, prywatna; brak docstringa.
- `def render_document(self, document: ZoneDocument) -> str` — linia 41, publiczna; brak docstringa.
- `def render_node(self, node: ZoneNode) -> str | None` — linia 62, publiczna; brak docstringa.
- `def render_record(self, record: DNSRecord) -> str` — linia 90, publiczna; brak docstringa.
- `def write_candidate(self, document: ZoneDocument, directory: Path | None = None, prefix: str = 'elkman-zone-', suffix: str = '.zone') -> Path` — linia 129, publiczna; brak docstringa.

## `src/elkman_dns/legacy_v220.py`

Brak docstringa modułu.

**Najważniejsze importy:**

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

### `def c(text, code, enabled = True)`

Lokalizacja: linia `24`.

Brak docstringa.

### `def run(cmd, timeout = 30)`

Lokalizacja: linia `26`.

Brak docstringa.

### `def yes(value, default = False)`

Lokalizacja: linia `32`.

Brak docstringa.

### `def require_root(name)`

Lokalizacja: linia `39`.

Brak docstringa.

### `def load_config(config_path, zones_path)`

Lokalizacja: linia `42`.

Brak docstringa.

### `def zone_items(zones)`

Lokalizacja: linia `50`.

Brak docstringa.

### `def sync_zone_items(zones)`

Lokalizacja: linia `55`.

Brak docstringa.

### `def selected(zones, requested)`

Lokalizacja: linia `59`.

Brak docstringa.

### `def dig_lines(server, name, rtype, timeout = 3, dnssec = False)`

Lokalizacja: linia `66`.

Brak docstringa.

### `def dig_serial(server, zone, timeout)`

Lokalizacja: linia `72`.

Brak docstringa.

### `def authoritative_servers(zone, timeout = 3)`

Lokalizacja: linia `77`.

Brak docstringa.

### `def parent_ds(zone, timeout = 3)`

Lokalizacja: linia `78`.

Brak docstringa.

### `def local_dnskeys(server, zone, timeout = 3)`

Lokalizacja: linia `79`.

Brak docstringa.

### `def has_rrsig(server, zone, rtype = 'A', timeout = 3)`

Lokalizacja: linia `81`.

Brak docstringa.

### `def delv_validate(zone, server = None, timeout = 15)`

Lokalizacja: linia `94`.

Brak docstringa.

### `def validation_targets(cfg)`

Lokalizacja: linia `104`.

Zwróć walidatory DNSSEC używane do ustalenia wyniku konsensusu.

### `def dnssec_validation_consensus(cfg, zone, timeout = 15)`

Lokalizacja: linia `118`.

Brak docstringa.

### `def cmd_check(cfg, zones, args)`

Lokalizacja: linia `140`.

Brak docstringa.

### `def cmd_sync(cfg, zones, args)`

Lokalizacja: linia `156`.

Brak docstringa.

### `def cmd_notify(cfg, zones, args)`

Lokalizacja: linia `178`.

Brak docstringa.

### `def cmd_reload(cfg, zones, args)`

Lokalizacja: linia `187`.

Brak docstringa.

### `def cmd_backup(cfg, zones, args)`

Lokalizacja: linia `199`.

Brak docstringa.

### `def dnssec_zone_result(cfg, zones, zone)`

Lokalizacja: linia `214`.

Brak docstringa.

### `def cmd_dnssec_status(cfg, zones, args)`

Lokalizacja: linia `236`.

Brak docstringa.

### `def explain_dnssec_result(r, no_color = False)`

Lokalizacja: linia `251`.

Brak docstringa.

### `def cmd_dnssec_check(cfg, zones, args)`

Lokalizacja: linia `279`.

Brak docstringa.

### `def cmd_dnssec_report(cfg, zones, args)`

Lokalizacja: linia `304`.

Brak docstringa.

### `def cmd_health(cfg, zones, args)`

Lokalizacja: linia `313`.

Brak docstringa.

### `def cmd_doctor(cfg, zones, args)`

Lokalizacja: linia `327`.

Brak docstringa.

### `def confirm(question, default = False)`

Lokalizacja: linia `348`.

Brak docstringa.

### `def update_ini_zone(zones_path, zone, new_path = None, dnssec = None)`

Lokalizacja: linia `356`.

Brak docstringa.

### `def find_zone_config(zone, bind_dir = Path('/etc/bind'))`

Lokalizacja: linia `380`.

Znajdź aktywny plik zawierający deklarację zone.

### `def zone_block_bounds(text, start)`

Lokalizacja: linia `415`.

Brak docstringa.

### `def patch_zone_declaration(path, text, start, old_file, new_file, key_dir)`

Lokalizacja: linia `434`.

Brak docstringa.

### `def generate_ds(server, zone, timeout = 5)`

Lokalizacja: linia `451`.

Brak docstringa.

### `def cmd_dnssec_enable(cfg, zones, args)`

Lokalizacja: linia `469`.

Brak docstringa.

### `def tui_select(stdscr, title, items, status_lines = None)`

Lokalizacja: linia `543`.

Brak docstringa.

### `def human_age(path)`

Lokalizacja: linia `572`.

Brak docstringa.

### `def latest_backup(cfg)`

Lokalizacja: linia `581`.

Brak docstringa.

### `def zone_quick_status(cfg, zones, zone)`

Lokalizacja: linia `587`.

Brak docstringa.

### `def domain_status_lines(cfg, zones, zone, quick = None)`

Lokalizacja: linia `605`.

Brak docstringa.

### `def cmd_zone_serial(cfg, zones, args)`

Lokalizacja: linia `619`.

Brak docstringa.

### `def cmd_zone_edit(cfg, zones, args)`

Lokalizacja: linia `642`.

Brak docstringa.

### `def cmd_zone_report(cfg, zones, args)`

Lokalizacja: linia `656`.

Brak docstringa.

### `def cmd_backups(cfg, zones, args)`

Lokalizacja: linia `667`.

Brak docstringa.

### `def domain_menu(cfg, zones, args, zone)`

Lokalizacja: linia `675`.

Brak docstringa.

### `def cmd_domains(cfg, zones, args)`

Lokalizacja: linia `697`.

Brak docstringa.

### `def cmd_menu(cfg, zones, args)`

Lokalizacja: linia `721`.

Brak docstringa.

### `def cmd_update(cfg, zones, args)`

Lokalizacja: linia `739`.

Brak docstringa.

### `def parser()`

Lokalizacja: linia `745`.

Brak docstringa.

### `def main()`

Lokalizacja: linia `766`.

Brak docstringa.

## `src/elkman_dns/ui/__init__.py`

Terminal UI for elkman DNS Toolkit.

Brak publicznych deklaracji klas lub funkcji.

## `src/elkman_dns/ui/credits.py`

Dyskretny podpis twórców projektu w głównym widoku TUI.

**Najważniejsze importy:**

- `__future__: annotations`
- `curses`

### `def _safe_addnstr(window: curses.window, row: int, column: int, text: str, width: int, attributes: int = curses.A_NORMAL) -> None`

Lokalizacja: linia `20`.

Rysuje tekst bez przerywania pracy przy małym terminalu.

### `def draw_project_credits(window: curses.window) -> None`

Lokalizacja: linia `44`.

Wyświetla dane twórców w prawym dolnym rogu głównego widoku.

## `src/elkman_dns/ui/curses_app.py`

Brak docstringa modułu.

**Najważniejsze importy:**

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

### `class Row`

Lokalizacja: linia `28`.

Brak docstringa.

### `class CursesApp`

Lokalizacja: linia `35`.

Brak docstringa.

**Metody:**

- `def __init__(self, zones: list[Zone], bind: BindService, group_order: list[str] | None = None, *, config: ToolkitConfig | None = None)` — linia 38, prywatna; brak docstringa.
- `def run(self) -> None` — linia 66, publiczna; brak docstringa.
- `def _main(self, stdscr: curses.window) -> None` — linia 69, prywatna; brak docstringa.
- `def _init_colors(self) -> None` — linia 101, prywatna; brak docstringa.
- `def _color(self, health: Health) -> int` — linia 111, prywatna; brak docstringa.
- `def _symbol(health: Health) -> str` — linia 122, prywatna; brak docstringa.
- `def _start_refresh(self, force: bool = False) -> None` — linia 125, prywatna; brak docstringa.
- `def _refresh_worker(self) -> None` — linia 133, prywatna; brak docstringa.
- `def _consume_results(self) -> bool` — linia 147, prywatna; brak docstringa.
- `def _zone_key(self, zone: Zone)` — linia 158, prywatna; brak docstringa.
- `def _ordered_groups(self, groups: dict[str, list[Zone]]) -> list[str]` — linia 175, prywatna; brak docstringa.
- `def _rebuild_rows(self, keep_zone: str | None = None) -> None` — linia 182, prywatna; brak docstringa.
- `def _selected_zone_name(self) -> str | None` — linia 206, prywatna; brak docstringa.
- `def _draw(self, win: curses.window) -> None` — linia 211, prywatna; brak docstringa.
- `def _activate(self, win: curses.window) -> None` — linia 255, prywatna; brak docstringa.
- `def _search(self, stdscr: curses.window) -> None` — linia 268, prywatna; filtruje domeny na głównej liście.
- `def _records_view(self, win: curses.window, zone: Zone) -> None` — linia 284, prywatna; wyświetla i edytuje źródłowy dokument strefy.
- `def _message_view(self, win: curses.window, *, title: str, lines: list[str], error: bool = False) -> None` — linia 789, prywatna; wyświetla prosty modalny komunikat.
- `def _get_key(win: curses.window) -> int` — linia 847, prywatna; odczytuje klawisz i rozpoznaje f2 wysyłane jako esc [ 12 ~.
- `def _transaction_result_view(self, win: curses.window, result: TransactionResult) -> None` — linia 890, prywatna; wyświetla wynik zapisu lub rollbacku transakcji.
- `def _pending_changes_view(self, win: curses.window, session: ZoneEditSession, model: ZoneModel, zone: Zone) -> None` — linia 933, prywatna; wyświetla oczekujące zmiany w rekordach strefy.
- `def _domain_view(self, win: curses.window, zone: Zone) -> None` — linia 1130, prywatna; wyświetla szczegóły wybranej strefy.
- `def _serial_ok(zone: Zone, status: ZoneStatus) -> bool` — linia 1399, prywatna; brak docstringa.
- `def _bool_text(value: bool | None) -> str` — linia 1409, prywatna; brak docstringa.

## `src/elkman_dns/ui/dialogs.py`

Brak docstringa modułu.

**Najważniejsze importy:**

- `__future__: annotations`
- `curses`

### `class CursesDialogs`

Lokalizacja: linia `6`.

Wspólne dialogi tekstowe interfejsu curses.

**Metody:**

- `def normalize_query(value: str) -> str` — linia 10, publiczna; normalizuje frazę wyszukiwania.
- `def text_input(win: curses.window, prompt: str, *, initial: str = '', row: int | None = None) -> str | None` — linia 29, publiczna; wyświetla jednowierszowy dialog tekstowy.
- `def search(cls, win: curses.window, *, prompt: str = ' Szukaj: ', initial: str = '', row: int | None = None) -> str | None` — linia 131, publiczna; brak docstringa.
- `def confirm(win: curses.window, message: str, *, row: int | None = None) -> bool` — linia 152, publiczna; wyświetla potwierdzenie [t/n].

## `src/elkman_dns/ui/records/__init__.py`

Widoki i komponenty obsługi rekordów DNS.

**Najważniejsze importy:**

- `editor: RecordEditor`
- `renderer: RecordRenderer`
- `new_record: NewRecordDialog, RECORD_TYPES`
- `controller: RecordController`

Brak publicznych deklaracji klas lub funkcji.

## `src/elkman_dns/ui/records/controller.py`

Stan, sortowanie i filtrowanie widoku rekordów DNS.

**Najważniejsze importy:**

- `__future__: annotations`
- `collections.abc: Sequence`
- `elkman_dns.core.zone_model: ZoneModel, ZoneRecordView`

### `class RecordController`

Lokalizacja: linia `10`.

Zarządza prezentacją rekordów bez zależności od curses.

**Metody:**

- `def __init__(self, model: ZoneModel, zone_name: str) -> None` — linia 19, prywatna; brak docstringa.
- `def sort_name(self) -> str` — linia 33, publiczna; brak docstringa.
- `def cycle_sort(self) -> None` — linia 36, publiczna; brak docstringa.
- `def set_search(self, value: str) -> None` — linia 44, publiczna; brak docstringa.
- `def clear_search(self) -> None` — linia 49, publiczna; brak docstringa.
- `def _name_key(self, view: ZoneRecordView) -> tuple[str, str, str, int]` — linia 54, prywatna; brak docstringa.
- `def _type_key(self, view: ZoneRecordView) -> tuple[str, str, str, int]` — linia 67, prywatna; brak docstringa.
- `def _ttl_key(self, view: ZoneRecordView) -> tuple[bool, int, str, str, int]` — linia 80, prywatna; brak docstringa.
- `def ordered_views(self) -> list[ZoneRecordView]` — linia 94, publiczna; brak docstringa.
- `def clamp_selection(self, views: Sequence[ZoneRecordView], visible_rows: int) -> None` — linia 140, publiczna; brak docstringa.
- `def move(self, delta: int, views: Sequence[ZoneRecordView]) -> None` — linia 167, publiczna; brak docstringa.
- `def current(self, views: Sequence[ZoneRecordView]) -> ZoneRecordView | None` — linia 181, publiczna; brak docstringa.
- `def select_identifier(self, views: Sequence[ZoneRecordView], identifier: int) -> bool` — linia 193, publiczna; brak docstringa.

## `src/elkman_dns/ui/records/editor.py`

Formularz edycji rekordów DNS w interfejsie curses.

**Najważniejsze importy:**

- `__future__: annotations`
- `typing: Any`
- `curses`
- `core.models: Zone`
- `core.zone_parser: DNSRecord`

### `class RecordEditor`

Lokalizacja: linia `13`.

Obsługuje formularz edycji pojedynczego rekordu DNS.

**Metody:**

- `def __init__(self, error_attr: int = curses.A_BOLD) -> None` — linia 16, prywatna; brak docstringa.
- `def _get_key(win: curses.window) -> int` — linia 21, prywatna; odczytuje klawisz i rozpoznaje f2 wysyłane jako esc [ 12 ~.
- `def _edit_line(self, win: curses.window, row: int, column: int, initial_value: str, max_width: int) -> str | None` — linia 60, prywatna; prosty edytor pojedynczej linii dla formularzy curses.
- `def create_record_dialog(self, win: curses.window, zone: Zone) -> DNSRecord | None` — linia 182, publiczna; tworzy nowy rekord, wykorzystując formularz edycji.
- `def edit_record_dialog(self, win: curses.window, record, zone: Zone)` — linia 203, publiczna; edytuje rekord w pamięci.

## `src/elkman_dns/ui/records/keybindings.py`

Brak docstringa modułu.

**Najważniejsze importy:**

- `__future__: annotations`
- `dataclasses: dataclass`
- `typing: Sequence`

### `class KeyBinding`

Lokalizacja: linia `8`.

Brak docstringa.

**Metody:**

- `def render(self) -> str` — linia 12, publiczna; brak docstringa.

### `def render_footer(bindings: Sequence[KeyBinding] = RECORD_VIEW_BINDINGS) -> str`

Lokalizacja: linia `31`.

Brak docstringa.

## `src/elkman_dns/ui/records/new_record.py`

Interaktywny kreator nowych rekordów DNS.

**Najważniejsze importy:**

- `__future__: annotations`
- `collections.abc: Iterable`
- `ipaddress: IPv4Address, IPv6Address`
- `curses`
- `core.models: Zone`
- `core.zone_parser: DNSRecord`

### `class NewRecordDialog`

Lokalizacja: linia `35`.

Tworzy rekord DNS bez modyfikowania pliku strefy.

**Metody:**

- `def __init__(self, error_attr: int = curses.A_BOLD) -> None` — linia 43, prywatna; brak docstringa.
- `def default_ttl(zone_name: str, records: Iterable[DNSRecord]) -> int` — linia 50, publiczna; pobiera ttl z głównego rekordu soa strefy.
- `def absolute_owner(owner: str, zone_name: str) -> str` — linia 80, publiczna; brak docstringa.
- `def validate_hostname(value: str) -> bool` — linia 96, publiczna; brak docstringa.
- `def validate_rdata(cls, rtype: str, rdata: str) -> str | None` — linia 120, publiczna; brak docstringa.
- `def build_record(cls, zone_name: str, owner: str, rtype: str, ttl_text: str, rdata: str) -> tuple[DNSRecord | None, str]` — linia 227, publiczna; brak docstringa.
- `def _put(win: curses.window, row: int, column: int, text: str, attr: int = curses.A_NORMAL) -> None` — linia 277, prywatna; brak docstringa.
- `def _type_window(type_index: int, maximum: int = 9) -> tuple[int, int]` — linia 309, prywatna; brak docstringa.
- `def create_record_dialog(self, win: curses.window, zone: Zone, records: Iterable[DNSRecord]) -> DNSRecord | None` — linia 320, publiczna; brak docstringa.

## `src/elkman_dns/ui/records/renderer.py`

Brak docstringa modułu.

**Najważniejsze importy:**

- `__future__: annotations`
- `curses`
- `collections.abc: Sequence`
- `elkman_dns.core.zone_model: ChangeKind, ZoneRecordView`
- `elkman_dns.ui.records.keybindings: render_footer`

### `class RecordRenderer`

Lokalizacja: linia `10`.

Renderuje ekran rekordów DNS bez obsługi klawiatury.

**Metody:**

- `def visible_rows(cls, height: int) -> int` — linia 17, publiczna; brak docstringa.
- `def summary_text(*, visible_count: int, total_count: int, sort_name: str, change_count: int, search_query: str = '') -> str` — linia 21, publiczna; brak docstringa.
- `def footer_text() -> str` — linia 41, publiczna; brak docstringa.
- `def _put(win: curses.window, row: int, column: int, text: str, attr: int = curses.A_NORMAL) -> None` — linia 45, prywatna; brak docstringa.
- `def _change_attr(view: ZoneRecordView) -> int` — linia 74, prywatna; brak docstringa.
- `def draw(cls, win: curses.window, *, zone_name: str, records: Sequence[ZoneRecordView], total_count: int, selected: int, offset: int, sort_name: str, change_count: int, search_query: str = '', error: str | None = None, error_attr: int = curses.A_BOLD) -> None` — linia 87, publiczna; brak docstringa.
