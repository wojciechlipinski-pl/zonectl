# Dokumentacja modułów

> Wygenerowano z AST: `2026-07-31T14:08:34+02:00`.

## `src/elkman_dns/__init__.py`

Zgodna nazwa historyczna; nowy kod powinien używać pakietu zonectl.

Brak klas i funkcji na poziomie modułu.

## `src/zonectl/__init__.py`

ZoneCTL — Transactional DNS Management Toolkit.

Brak klas i funkcji na poziomie modułu.

## `src/zonectl/cli.py`

Brak docstringa.

### `def parser`

Linia: `39`

Brak docstringa.

### `def legacy_main`

Linia: `347`

Brak docstringa.

### `def grouped_lines`

Linia: `357`

Brak docstringa.

### `def print_transaction`

Linia: `371`

Brak docstringa.

### `def transaction_main`

Linia: `381`

Brak docstringa.

### `def main`

Linia: `445`

Brak docstringa.

### `def deprecated_main`

Linia: `826`

Brak docstringa.

## `src/zonectl/core/__init__.py`

Core services for ZoneCTL.

Brak klas i funkcji na poziomie modułu.

## `src/zonectl/core/audit.py`

Brak docstringa.

### `class AuditEvent`

Linia: `14`

Brak docstringa.

### `class AuditLog`

Linia: `26`

Brak docstringa.

**Metody:**

- `__init__` — linia 27; brak docstringa.
- `identity` — linia 31; brak docstringa.
- `append` — linia 40; brak docstringa.
- `read` — linia 63; brak docstringa.

## `src/zonectl/core/bind.py`

Brak docstringa.

### `class BindService`

Linia: `11`

Read-only BIND status service used by the Sprint 1 dashboard.

**Metody:**

- `__init__` — linia 14; brak docstringa.
- `serial` — linia 22; brak docstringa.
- `dnssec_enabled` — linia 32; brak docstringa.
- `rpz_status` — linia 39; brak docstringa.
- `zone_records` — linia 91; zwraca kanoniczną listę rekordów z aktywnego pliku strefy.
- `parsed_zone_records` — linia 137; zwraca rekordy strefy przekształcone do modelu dnsrecord.
- `quick_status` — linia 165; brak docstringa.

## `src/zonectl/core/bind_bootstrap.py`

Brak docstringa.

### `class BindBootstrapPlan`

Linia: `17`

Brak docstringa.

**Metody:**

- `actions` — linia 26; brak docstringa.

### `class BindBootstrapStep`

Linia: `44`

Brak docstringa.

### `class BindBootstrapResult`

Linia: `51`

Brak docstringa.

**Metody:**

- `ok` — linia 61; brak docstringa.

### `class BindBootstrapError`

Linia: `68`

Błąd planowania bezpiecznego fragmentu konfiguracji BIND.

### `class BindBootstrapTransaction`

Linia: `72`

Instaluje zarządzany include ZoneCTL z walidacją i rollbackiem.

**Metody:**

- `__init__` — linia 75; brak docstringa.
- `plan` — linia 87; brak docstringa.
- `apply` — linia 126; brak docstringa.
- `_save_manifest` — linia 258; brak docstringa.
- `_atomic_write` — linia 277; brak docstringa.
- `_validate_config` — linia 299; brak docstringa.

## `src/zonectl/core/bind_config.py`

Brak docstringa.

### `class BindConfigError`

Linia: `9`

Błąd odczytu lub analizy konfiguracji BIND.

### `class BindConfigDiscovery`

Linia: `13`

Odczytuje strefy bezpośrednio z konfiguracji BIND. Obsługuje: - zone "example.org" { ... }; - rekurencyjne dyrektywy include; - konfigurację w named.conf.local; - przyszłą strukturę zones.d; - wykrywanie pliku strefy, DNSSEC, notify, dns2 i HE.

**Metody:**

- `__init__` — linia 50; brak docstringa.
- `zones` — linia 54; zwróć wszystkie strefy znalezione w konfiguracji bind.
- `_read_file` — linia 63; brak docstringa.
- `_resolve_include` — linia 101; brak docstringa.
- `_zone_blocks` — linia 109; brak docstringa.
- `_matching_brace` — linia 147; brak docstringa.
- `_zone_from_block` — linia 177; brak docstringa.
- `_group_for` — linia 242; brak docstringa.
- `_strip_comments` — linia 266; usuń komentarze //, # i /* ... */ bez niszczenia tekstu znajdującego się wewnątrz cudzysłowów.

## `src/zonectl/core/bulk_operations.py`

Brak docstringa.

### `class BulkOperationError`

Linia: `14`

Nieprawidłowa lub niemożliwa operacja masowa.

### `class BulkAction`

Linia: `18`

Brak docstringa.

### `class BulkMatch`

Linia: `24`

Brak docstringa.

### `class BulkOperation`

Linia: `31`

Brak docstringa.

**Metody:**

- `parse` — linia 43; brak docstringa.
- `selected` — linia 111; brak docstringa.
- `_replacement` — linia 125; brak docstringa.
- `matches` — linia 150; brak docstringa.
- `proposed_records` — linia 167; brak docstringa.
- `apply` — linia 183; brak docstringa.

## `src/zonectl/core/config.py`

Brak docstringa.

### `def _yes`

Linia: `16`

Brak docstringa.

### `def _unquote`

Linia: `29`

Brak docstringa.

### `def load_groups_yaml`

Linia: `42`

Odczytaj uproszczony format groups.yaml bez PyYAML.

### `class ToolkitConfig`

Linia: `116`

Konfiguracja ZoneCTL. Konfiguracja BIND jest źródłem prawdy dla: - nazw stref, - typów stref, - aktywnych plików źródłowych. zones.conf może nadpisywać wyłącznie ustawienia Toolkitu, np. grupę, obsługę serwerów wtórnych i widoczność strefy.

**Metody:**

- `__init__` — linia 130; brak docstringa.
- `load` — linia 149; brak docstringa.
- `toolkit` — linia 182; brak docstringa.
- `auto_discover_zones` — linia 186; brak docstringa.
- `read_only` — linia 193; blokuje operacje zapisujące, pozostawiając diagnostykę i odczyt.
- `bind_config_path` — linia 198; brak docstringa.
- `_normalise_zone_name` — linia 207; brak docstringa.
- `_discover_bind_zones` — linia 210; brak docstringa.
- `discovered_zone` — linia 227; brak docstringa.
- `_zone_override` — linia 235; brak docstringa.
- `_group_for` — linia 247; brak docstringa.
- `_zone_from_discovery` — linia 263; brak docstringa.
- `_zones_from_discovery` — linia 330; brak docstringa.
- `_zones_from_legacy_config` — linia 344; tryb zgodności ze starym zones.conf. używany wyłącznie, gdy auto_discover_zones = no.
- `zones` — linia 422; brak docstringa.

## `src/zonectl/core/discovery.py`

Automatyczne wykrywanie stref i plików źródłowych BIND.

### `class BindDiscoveryError`

Linia: `14`

Błąd odczytu lub interpretacji konfiguracji BIND.

### `class ZoneConfig`

Linia: `19`

Konfiguracja pojedynczej strefy wykryta z konfiguracji BIND.

**Metody:**

- `is_primary` — linia 42; brak docstringa.
- `is_secondary` — linia 46; brak docstringa.
- `dnssec_enabled` — linia 50; brak docstringa.
- `editable` — linia 54; brak docstringa.
- `is_managed_signed_file` — linia 64; brak docstringa.
- `requires_freeze` — linia 72; journal aktywnej strefy oznacza, że zwykła atomowa podmiana pliku może być niewystarczająca. sama obecność .signed.jnl nie powoduje ustawienia tej flagi, ponieważ jest to journal podpisanej strony inline-signing.
- `save_mode` — linia 83; brak docstringa.

### `class DiscoveryResult`

Linia: `106`

Wynik przejścia przez konfigurację BIND.

**Metody:**

- `zone` — linia 113; brak docstringa.

### `class _ConfigSource`

Linia: `137`

Brak docstringa.

### `class BindConfigDiscovery`

Linia: `142`

Czyta konfigurację BIND, rozwija include i wykrywa strefy.

**Metody:**

- `__init__` — linia 181; brak docstringa.
- `discover` — linia 187; brak docstringa.
- `_load_config_tree` — linia 217; brak docstringa.
- `_parse_zones` — linia 273; brak docstringa.
- `_zone_from_block` — linia 321; brak docstringa.
- `_match_value` — linia 429; brak docstringa.
- `_resolve_config_path` — linia 442; brak docstringa.
- `_resolve_zone_path` — linia 454; brak docstringa.
- `_find_block_end` — linia 470; brak docstringa.
- `_strip_comments` — linia 509; usuwa komentarze //, # i /* ... */, ale zachowuje tekst wewnątrz cudzysłowów.

## `src/zonectl/core/edit_lock.py`

Brak docstringa.

### `class ZoneEditLockedError`

Linia: `15`

Strefa jest już otwarta w innej sesji edycyjnej.

**Metody:**

- `__init__` — linia 18; brak docstringa.

### `class ZoneEditLock`

Linia: `33`

Międzyprocesowa blokada wyłącznej sesji edycji strefy.

**Metody:**

- `__init__` — linia 36; brak docstringa.
- `acquired` — linia 49; brak docstringa.
- `_metadata` — linia 52; brak docstringa.
- `_read_owner` — linia 67; brak docstringa.
- `acquire` — linia 75; brak docstringa.
- `release` — linia 120; brak docstringa.
- `__enter__` — linia 135; brak docstringa.
- `__exit__` — linia 138; brak docstringa.

## `src/zonectl/core/models.py`

Brak docstringa.

### `class Health`

Linia: `8`

Brak docstringa.

### `class Zone`

Linia: `16`

Brak docstringa.

### `class ZoneStatus`

Linia: `32`

Brak docstringa.

## `src/zonectl/core/multi_zone_session.py`

Brak docstringa.

### `class MultiZoneSessionError`

Linia: `10`

Błąd koordynacji sesji obejmującej wiele stref.

### `class MultiZoneSaveResult`

Linia: `15`

Wynik walidacji lub zapisu zestawu stref.

**Metody:**

- `ok` — linia 23; brak docstringa.

### `class MultiZoneEditSession`

Linia: `27`

Przechowuj niezależne sesje edycji wielu stref. Każda strefa zachowuje własną blokadę, kandydat, backup i manifest transakcji. Przed pierwszym COMMIT wszystkie zmienione strefy są walidowane w trybie dry-run.

**Metody:**

- `__init__` — linia 36; brak docstringa.
- `open_zone_names` — linia 46; brak docstringa.
- `dirty_zone_names` — linia 50; brak docstringa.
- `open` — linia 57; otwórz strefę lub zwróć już istniejącą sesję roboczą.
- `close_zone` — linia 71; zamknij jedną strefę, opcjonalnie porzucając jej zmiany.
- `validate_all` — linia 90; zweryfikuj wszystkie zmienione strefy bez commit.
- `save_all` — linia 101; zweryfikuj wszystkie strefy, a potem zapisuj je kolejno. po pierwszym nieudanym commit dalsze strefy nie są zapisywane. wynik nie udaje atomowości pomiędzy niezależnymi strefami.
- `close` — linia 121; zamknij wszystkie sesje i zwolnij ich blokady.
- `__enter__` — linia 131; brak docstringa.
- `__exit__` — linia 134; brak docstringa.

## `src/zonectl/core/paths.py`

Centralne ścieżki systemowe ZoneCTL. Ten moduł jest jedynym źródłem domyślnych ścieżek używanych przez kod Pythona. Na tym etapie zachowujemy dotychczasowe katalogi systemowe. Ich migracja do przestrzeni nazw ZoneCTL zostanie wykonana osobno, z backupem i możliwością wycofania.

Brak klas i funkcji na poziomie modułu.

## `src/zonectl/core/record_filter.py`

Brak docstringa.

### `class RecordFilterError`

Linia: `11`

Nieprawidłowe wyrażenie filtrowania rekordów.

### `class FilterTerm`

Linia: `43`

Brak docstringa.

### `def _status`

Linia: `51`

Brak docstringa.

### `class RecordFilter`

Linia: `60`

Skompilowany filtr rekordów. Oddzielone spacjami warunki są łączone operatorem AND. Zwykły tekst zachowuje dotychczasowe wyszukiwanie we wszystkich widocznych polach.

**Metody:**

- `__init__` — linia 68; brak docstringa.
- `_parse` — linia 73; brak docstringa.
- `_text_value` — linia 172; brak docstringa.
- `_match_ttl` — linia 191; brak docstringa.
- `_match_term` — linia 214; brak docstringa.
- `matches` — linia 259; brak docstringa.
- `apply` — linia 269; brak docstringa.

## `src/zonectl/core/record_validation.py`

Brak docstringa.

### `class ValidationSeverity`

Linia: `15`

Brak docstringa.

### `class ValidationIssue`

Linia: `22`

Brak docstringa.

**Metody:**

- `key` — linia 29; brak docstringa.

### `def is_valid_dns_name`

Linia: `57`

Brak docstringa.

### `def _integer`

Linia: `78`

Brak docstringa.

### `def _hex_error`

Linia: `93`

Brak docstringa.

### `def validate_rdata`

Linia: `102`

Brak docstringa.

### `def validate_record`

Linia: `278`

Brak docstringa.

### `def _absolute_name`

Linia: `313`

Brak docstringa.

### `def _target`

Linia: `325`

Brak docstringa.

### `def validate_zone`

Linia: `337`

Brak docstringa.

## `src/zonectl/core/runner.py`

Brak docstringa.

### `class CommandResult`

Linia: `8`

Brak docstringa.

### `def run`

Linia: `14`

Brak docstringa.

## `src/zonectl/core/soa_serial.py`

Brak docstringa.

### `class SoaSerialError`

Linia: `11`

Błąd odczytu lub aktualizacji serialu SOA.

### `class SoaSerialChange`

Linia: `16`

Brak docstringa.

### `def next_soa_serial`

Linia: `33`

Wylicza kolejny serial w formacie RRRRMMDDNN. Jeżeli aktualny serial jest starszy niż dzisiejszy: RRRRMMDD01 Jeżeli jest dzisiejszy albo większy: aktualny + 1 Druga reguła gwarantuje monotoniczność również wtedy, gdy w strefie znajduje się serial z przyszłą datą lub niestandardowy wysoki serial.

### `def _replace_record_serial`

Linia: `72`

Brak docstringa.

### `def bump_document_soa_serial`

Linia: `100`

Podbija serial pierwszego rekordu SOA w ZoneDocument. Obsługiwane są: - wielowierszowe SOA zachowane jako RawLine, - jednowierszowe SOA zapisane jako RecordNode. Komentarze i wcięcia wielowierszowego SOA pozostają bez zmian.

## `src/zonectl/core/transaction.py`

Brak docstringa.

### `class StepResult`

Linia: `30`

Brak docstringa.

### `class TransactionResult`

Linia: `40`

Brak docstringa.

**Metody:**

- `ok` — linia 51; brak docstringa.

### `class ZoneLock`

Linia: `55`

Brak docstringa.

**Metody:**

- `__init__` — linia 56; brak docstringa.
- `__enter__` — linia 60; brak docstringa.
- `__exit__` — linia 74; brak docstringa.

### `class TransactionEngine`

Linia: `84`

Atomic zone-file replacement with validation, backup, reload and rollback.

**Metody:**

- `__init__` — linia 87; brak docstringa.
- `find_zone` — linia 130; brak docstringa.
- `_safe_zone_name` — linia 138; brak docstringa.
- `_digest` — linia 142; brak docstringa.
- `_step_command` — linia 149; brak docstringa.
- `_zone_validation` — linia 154; brak docstringa.
- `_config_validation` — linia 157; brak docstringa.
- `_zone_serial` — linia 160; brak docstringa.
- `_serial` — linia 170; brak docstringa.
- `_loaded_serial` — linia 177; brak docstringa.
- `_verify_loaded_zone` — linia 186; brak docstringa.
- `validate` — linia 206; brak docstringa.
- `verify` — linia 224; brak docstringa.
- `apply` — linia 317; brak docstringa.
- `rollback` — linia 453; brak docstringa.
- `backups` — linia 491; brak docstringa.
- `history` — linia 498; odczytaj ostatnie manifesty transakcji.
- `load_transaction` — linia 549; odtwórz wynik transakcji z manifestu.
- `_new_id` — linia 615; brak docstringa.
- `_backup` — linia 619; brak docstringa.
- `_atomic_install` — linia 640; brak docstringa.
- `_rollback` — linia 667; brak docstringa.
- `_save_manifest` — linia 677; brak docstringa.
- `_finish` — linia 689; brak docstringa.

## `src/zonectl/core/zone_create_transaction.py`

Brak docstringa.

### `class ZoneCreateStep`

Linia: `18`

Brak docstringa.

### `class ZoneCreateResult`

Linia: `25`

Brak docstringa.

**Metody:**

- `ok` — linia 35; brak docstringa.

### `class ZoneCreateTransaction`

Linia: `44`

Atomowo zastosuj plan utworzenia strefy z rollbackiem.

**Metody:**

- `__init__` — linia 47; brak docstringa.
- `apply` — linia 66; brak docstringa.
- `_finish` — linia 259; brak docstringa.
- `_atomic_write` — linia 294; brak docstringa.
- `_validate_zone` — linia 319; brak docstringa.
- `_validate_config` — linia 330; brak docstringa.
- `_activate_bind` — linia 341; brak docstringa.
- `_verify_loaded` — linia 351; brak docstringa.

## `src/zonectl/core/zone_disable_transaction.py`

Brak docstringa.

### `class ZoneDisablePlan`

Linia: `18`

Brak docstringa.

### `class ZoneDisableStep`

Linia: `31`

Brak docstringa.

### `class ZoneDisableResult`

Linia: `38`

Brak docstringa.

**Metody:**

- `ok` — linia 49; brak docstringa.

### `class ZoneDisableError`

Linia: `57`

Nie można bezpiecznie zaplanować wyłączenia strefy.

### `class ZoneDisableTransaction`

Linia: `61`

Odwracalnie usuwa strefę z aktywnej konfiguracji BIND.

**Metody:**

- `__init__` — linia 64; brak docstringa.
- `plan` — linia 80; brak docstringa.
- `apply` — linia 125; brak docstringa.
- `_save` — linia 250; brak docstringa.
- `_atomic_write` — linia 265; brak docstringa.
- `_validate_config` — linia 283; brak docstringa.
- `_activate_bind` — linia 292; brak docstringa.
- `_verify_unavailable` — linia 301; brak docstringa.

## `src/zonectl/core/zone_document.py`

Brak docstringa.

### `class ZoneNode`

Linia: `10`

Element źródłowego dokumentu strefy.

### `class BlankLine`

Linia: `15`

Brak docstringa.

### `class Comment`

Linia: `20`

Brak docstringa.

**Metody:**

- `text` — linia 24; brak docstringa.

### `class Directive`

Linia: `29`

Brak docstringa.

### `class RecordNode`

Linia: `36`

Brak docstringa.

### `class RawLine`

Linia: `44`

Linia zachowana bez interpretacji. Używana m.in. dla: - rekordów wielowierszowych, - nieobsługiwanej składni, - linii kontynuacji.

### `class ZoneDocument`

Linia: `58`

Brak docstringa.

**Metody:**

- `records` — linia 64; brak docstringa.
- `iter_record_nodes` — linia 71; brak docstringa.
- `find_record` — linia 76; brak docstringa.

## `src/zonectl/core/zone_document_adapter.py`

Brak docstringa.

### `class ZoneDocumentAdapterError`

Linia: `9`

Błąd synchronizacji ZoneModel z ZoneDocument.

### `class _NodeBinding`

Linia: `14`

Brak docstringa.

### `class ZoneDocumentAdapter`

Linia: `19`

Łączy bufor edycji ZoneModel z bezstratnym ZoneDocument. ZoneModel nadal obsługuje logikę zmian dla UI, natomiast adapter nanosi te zmiany na węzły dokumentu przed użyciem ZoneWriter. Istniejące rekordy są wiązane z RecordNode według ich kolejności podczas tworzenia adaptera. Dzięki temu poprawnie obsługiwane są również identyczne rekordy występujące więcej niż raz.

**Metody:**

- `__init__` — linia 31; brak docstringa.
- `_bind_existing_records` — linia 44; brak docstringa.
- `apply` — linia 71; nanieś bieżące zmiany modelu na dokument. metoda może być wykonywana wielokrotnie. dodane rekordy nie będą ponownie dopisywane, a cofnięte zmiany zostaną wyzerowane.
- `_apply_add` — linia 117; brak docstringa.
- `_remove_abandoned_added_nodes` — linia 140; brak docstringa.
- `discard` — linia 158; przywróć dokument do stanu sprzed zmian modelu. powinno być wywołane razem z zonemodel.discard().

## `src/zonectl/core/zone_edit_session.py`

Brak docstringa.

### `class TransactionEngineProtocol`

Linia: `28`

Brak docstringa.

**Metody:**

- `apply` — linia 29; brak docstringa.

### `class ZoneEditSessionError`

Linia: `39`

Błąd sesji edycji strefy.

### `class ZoneSaveResult`

Linia: `44`

Brak docstringa.

**Metody:**

- `committed` — linia 49; brak docstringa.
- `ok` — linia 53; brak docstringa.
- `status` — linia 57; brak docstringa.

### `class ZoneEditSession`

Linia: `61`

Pełna sesja edycji źródłowego pliku strefy. Pipeline: ZoneFileParser -> ZoneDocument -> ZoneModel -> ZoneDocumentAdapter -> ZoneWriter -> TransactionEngine

**Metody:**

- `__init__` — linia 75; brak docstringa.
- `close` — linia 121; zwolnij blokadę sesji edycyjnej, jeśli została założona.
- `source_path` — linia 127; brak docstringa.
- `dirty` — linia 136; brak docstringa.
- `change_count` — linia 140; brak docstringa.
- `_load` — linia 143; brak docstringa.
- `_prepare_document` — linia 165; brak docstringa.
- `render_candidate` — linia 190; wygeneruj tekst kandydata bez tworzenia pliku.
- `unified_diff` — linia 197; pokaż różnice między aktywnym plikiem a kandydatem. metoda nie tworzy pliku tymczasowego i nie wykonuje transakcji.
- `export_diff` — linia 220; atomowo zapisz unified diff bez wykonywania commit.
- `create_candidate` — linia 280; utwórz bezpieczny plik tymczasowy z bieżącymi zmianami.
- `save` — linia 297; waliduj albo zapisz zmiany przez transactionengine. commit=false: dry-run, aktywny plik nie jest zmieniany. commit=true: backup, atomic install, reload, weryfikacja i rollback.
- `discard` — linia 339; porzuć wszystkie niezapisane zmiany.
- `undo` — linia 347; cofnij ostatnią zmianę bieżącej sesji.
- `reload` — linia 357; ponownie odczytaj aktywny plik strefy. niezapisane zmiany są tracone.

## `src/zonectl/core/zone_file_parser.py`

Brak docstringa.

### `class ZoneFileParseError`

Linia: `17`

Błąd odczytu źródłowego pliku strefy.

### `class _Token`

Linia: `22`

Brak docstringa.

### `class ZoneFileParser`

Linia: `28`

Zachowujący formatowanie parser źródłowego pliku strefy. Parser interpretuje bezpieczne rekordy jednowierszowe. Linie, których nie potrafi jednoznacznie rozpoznać, zapisuje jako RawLine. Dzięki temu żadna część źródłowego pliku nie jest tracona.

**Metody:**

- `parse_file` — linia 100; brak docstringa.
- `parse_text` — linia 120; brak docstringa.
- `_parse_directive` — linia 199; brak docstringa.
- `_parse_record_line` — linia 223; brak docstringa.
- `_is_ttl` — linia 314; brak docstringa.
- `_is_record_type` — linia 326; brak docstringa.
- `_normalise_class` — linia 337; brak docstringa.
- `_remove_comment` — linia 346; usuń komentarz rozpoczynający się średnikiem poza cudzysłowem.
- `_tokenise` — linia 372; podziel linię według białych znaków, zachowując tekst w cudzysłowach.
- `_parenthesis_delta` — linia 425; policz nawiasy poza cudzysłowami. nie interpretuje rekordów wielowierszowych, lecz pozwala zachować cały blok jako rawline.

## `src/zonectl/core/zone_inventory.py`

Brak docstringa.

### `class InactiveZone`

Linia: `10`

Brak docstringa.

**Metody:**

- `to_dict` — linia 19; brak docstringa.

### `class ZoneInventory`

Linia: `23`

Read-only inventory of disabled and quarantined zones.

**Metody:**

- `__init__` — linia 26; brak docstringa.
- `records` — linia 38; brak docstringa.
- `_disabled` — linia 46; brak docstringa.
- `_quarantined` — linia 69; brak docstringa.
- `_latest_disable_manifest` — linia 91; brak docstringa.
- `_record` — linia 107; brak docstringa.
- `_load_json` — linia 130; brak docstringa.
- `_mtime` — linia 138; brak docstringa.

## `src/zonectl/core/zone_lifecycle.py`

Brak docstringa.

### `class ZoneLifecycleError`

Linia: `13`

Nieprawidłowy lub kolidujący plan cyklu życia strefy.

### `def normalize_zone_name`

Linia: `20`

Znormalizuj i zwaliduj nazwę strefy DNS.

### `def normalize_fqdn`

Linia: `35`

Zwróć bezpieczną absolutną nazwę DNS zakończoną kropką.

### `class ZoneCreateRequest`

Linia: `47`

Brak docstringa.

### `class ZoneCreatePlan`

Linia: `68`

Brak docstringa.

**Metody:**

- `to_dict` — linia 78; brak docstringa.

### `class ZoneLifecyclePlanner`

Linia: `88`

Twórz pozbawione skutków ubocznych plany zarządzania strefami.

**Metody:**

- `__init__` — linia 91; brak docstringa.
- `ensure_lifecycle_allowed` — linia 104; reject lifecycle mutations for automatically managed rpz zones.
- `plan_create` — linia 137; zbuduj plan utworzenia strefy bez zapisywania plików.
- `_address` — linia 219; brak docstringa.
- `_zone_text` — linia 235; brak docstringa.

## `src/zonectl/core/zone_model.py`

Brak docstringa.

### `class ChangeKind`

Linia: `10`

Brak docstringa.

### `class ZoneModelReadOnlyError`

Linia: `16`

Próba zmiany modelu uruchomionego w trybie tylko do odczytu.

### `class ZoneChange`

Linia: `21`

Brak docstringa.

**Metody:**

- `record` — linia 27; brak docstringa.

### `class ZoneRecordView`

Linia: `38`

Rekord prezentowany w edytorze wraz ze stanem zmiany.

**Metody:**

- `deleted` — linia 46; brak docstringa.
- `marker` — linia 50; brak docstringa.

### `class _RecordEntry`

Linia: `60`

Brak docstringa.

### `class _ModelSnapshot`

Linia: `67`

Brak docstringa.

### `class ZoneModel`

Linia: `73`

Bufor edycji rekordów pojedynczej strefy. Model nie zapisuje plików i nie wykonuje poleceń systemowych. Przechowuje jedynie stan początkowy, bieżący i wyliczony diff.

**Metody:**

- `__init__` — linia 81; brak docstringa.
- `_allocate_identifier` — linia 105; brak docstringa.
- `_snapshot` — linia 110; brak docstringa.
- `_remember` — linia 127; brak docstringa.
- `_ensure_writable` — linia 130; brak docstringa.
- `_visible_entries` — linia 136; brak docstringa.
- `_entry_at` — linia 143; brak docstringa.
- `records` — linia 154; brak docstringa.
- `original_records` — linia 162; brak docstringa.
- `record_views` — linia 170; zwraca rekordy widoczne w edytorze, również usuwane.
- `pending_changes` — linia 208; brak docstringa.
- `dirty` — linia 250; brak docstringa.
- `change_count` — linia 254; brak docstringa.
- `can_undo` — linia 258; brak docstringa.
- `transaction_metadata` — linia 262; zwróć opis zmian przekazywany do manifestu transakcji.
- `describe_last_bulk_operation` — linia 273; przypisz opis do ostatniego atomowego kroku masowego.
- `add` — linia 280; brak docstringa.
- `_entry_by_identifier` — linia 293; brak docstringa.
- `replace_by_identifier` — linia 302; brak docstringa.
- `delete_by_identifier` — linia 323; brak docstringa.
- `replace` — linia 341; brak docstringa.
- `delete` — linia 363; brak docstringa.
- `bulk_replace_by_identifiers` — linia 384; zastąp wiele rekordów jako jeden krok historii cofania.
- `bulk_delete_by_identifiers` — linia 409; usuń wiele rekordów jako jeden krok historii cofania.
- `undo` — linia 436; cofnij ostatnią operację wykonaną w modelu.
- `discard` — linia 447; brak docstringa.
- `accept` — linia 461; uznaje aktualny stan za nowy stan bazowy. metoda będzie używana dopiero po udanym zapisie transakcji.

## `src/zonectl/core/zone_parser.py`

Brak docstringa.

### `class DNSRecord`

Linia: `7`

Brak docstringa.

**Metody:**

- `relative_owner` — linia 15; brak docstringa.

### `class ZoneRecordParser`

Linia: `30`

Parser kanonicznego wyjścia `named-checkzone -D`.

**Metody:**

- `parse_output` — linia 39; brak docstringa.
- `parse_line` — linia 67; oczekiwany format kanoniczny: owner ttl class type rdata rdata pozostaje tekstem, dzięki czemu zachowujemy składnię rekordów txt, soa, mx, srv, caa i innych typów.

## `src/zonectl/core/zone_quarantine.py`

Brak docstringa.

### `class ZoneQuarantinePlan`

Linia: `15`

Brak docstringa.

### `class ZoneQuarantineStep`

Linia: `25`

Brak docstringa.

### `class ZoneQuarantineResult`

Linia: `32`

Brak docstringa.

**Metody:**

- `ok` — linia 43; brak docstringa.

### `class ZoneQuarantineError`

Linia: `47`

Strefa nie spełnia warunków bezpiecznej kwarantanny.

### `class ZoneQuarantineTransaction`

Linia: `51`

Przenosi uprzednio wyłączoną strefę do pakietu odtworzeniowego.

**Metody:**

- `plan` — linia 55; brak docstringa.
- `apply` — linia 96; brak docstringa.
- `_sha256` — linia 226; brak docstringa.
- `_atomic_write` — linia 234; brak docstringa.

## `src/zonectl/core/zone_quarantine_restore.py`

Brak docstringa.

### `class QuarantineRestorePlan`

Linia: `18`

Brak docstringa.

### `class QuarantineRestoreStep`

Linia: `32`

Brak docstringa.

### `class QuarantineRestoreResult`

Linia: `39`

Brak docstringa.

**Metody:**

- `ok` — linia 49; brak docstringa.

### `class QuarantineRestoreError`

Linia: `58`

Pakiet kwarantanny nie pozwala na bezpieczne odtworzenie.

### `class QuarantineRestoreTransaction`

Linia: `62`

Odtwarza i aktywuje strefę ze zweryfikowanego pakietu kwarantanny.

**Metody:**

- `__init__` — linia 65; brak docstringa.
- `plan` — linia 79; brak docstringa.
- `apply` — linia 125; brak docstringa.
- `_sha256` — linia 241; brak docstringa.
- `_atomic_write` — linia 245; brak docstringa.
- `_validate_zone` — linia 261; brak docstringa.
- `_validate_config` — linia 266; brak docstringa.
- `_activate_bind` — linia 271; brak docstringa.
- `_verify_loaded` — linia 276; brak docstringa.

## `src/zonectl/core/zone_restore_transaction.py`

Brak docstringa.

### `class ZoneRestorePlan`

Linia: `17`

Brak docstringa.

### `class ZoneRestoreStep`

Linia: `28`

Brak docstringa.

### `class ZoneRestoreResult`

Linia: `35`

Brak docstringa.

**Metody:**

- `ok` — linia 45; brak docstringa.

### `class ZoneRestoreError`

Linia: `54`

Nie można bezpiecznie zaplanować przywrócenia strefy.

### `class ZoneRestoreTransaction`

Linia: `58`

Przywraca wyłączoną strefę do aktywnej konfiguracji BIND.

**Metody:**

- `__init__` — linia 61; brak docstringa.
- `plan` — linia 77; brak docstringa.
- `apply` — linia 117; brak docstringa.
- `_save` — linia 247; brak docstringa.
- `_atomic_write` — linia 261; brak docstringa.
- `_validate_zone` — linia 279; brak docstringa.
- `_validate_config` — linia 288; brak docstringa.
- `_activate_bind` — linia 297; brak docstringa.
- `_verify_loaded` — linia 306; brak docstringa.

## `src/zonectl/core/zone_serializer.py`

Serializacja modelu strefy DNS do pliku kandydata.

### `class ZoneSerializationError`

Linia: `13`

Błąd podczas serializacji strefy DNS.

### `class ZoneModelProtocol`

Linia: `17`

Brak docstringa.

**Metody:**

- `records` — linia 19; brak docstringa.

### `class ZoneSerializer`

Linia: `23`

Serializuje rekordy DNS do tekstowego pliku strefy. Serializer: - nie wykonuje walidacji, - nie zwiększa numeru SOA, - nie zapisuje aktywnego pliku strefy, - nie uruchamia rndc, - pomija rekordy oznaczone jako usunięte.

**Metody:**

- `__init__` — linia 35; brak docstringa.
- `_is_deleted` — linia 44; obsługuje kilka wariantów modelu rekordów. preferowane pole: deleted: bool obsługiwane również: is_deleted: bool state == "deleted" change_type == "deleted"
- `_normalise_owner` — linia 90; brak docstringa.
- `_normalise_class` — linia 96; brak docstringa.
- `_record_owner` — linia 102; brak docstringa.
- `_record_type` — linia 118; brak docstringa.
- `_record_rdata` — linia 134; brak docstringa.
- `_record_ttl` — linia 153; brak docstringa.
- `_record_class` — linia 174; brak docstringa.
- `render_record` — linia 189; brak docstringa.
- `render_records` — linia 216; brak docstringa.
- `render_model` — linia 235; brak docstringa.
- `write_candidate` — linia 248; brak docstringa.

## `src/zonectl/core/zone_writer.py`

Brak docstringa.

### `class ZoneWriteError`

Linia: `19`

Błąd podczas generowania lub zapisywania dokumentu strefy.

### `class ZoneWriter`

Linia: `23`

Bezstratny zapis źródłowego dokumentu strefy. Zasady: - niezmienione węzły są zapisywane z pola `raw`, - zmodyfikowane rekordy są renderowane ponownie, - rekordy oznaczone jako usunięte są pomijane, - komentarze, dyrektywy, puste linie i RawLine pozostają bez zmian, - zachowywana jest informacja o końcowym znaku nowej linii.

**Metody:**

- `__init__` — linia 35; brak docstringa.
- `render_document` — linia 41; brak docstringa.
- `render_node` — linia 62; brak docstringa.
- `render_modified_record` — linia 90; renderuj rekord, zachowując jego komentarz końcowy.
- `_inline_comment_suffix` — linia 100; zwróć komentarz poza cudzysłowem wraz z odstępem przed nim.
- `render_record` — linia 128; brak docstringa.
- `write_candidate` — linia 167; brak docstringa.

## `src/zonectl/legacy_v220.py`

Brak docstringa.

### `def c`

Linia: `29`

Brak docstringa.

### `def run`

Linia: `31`

Brak docstringa.

### `def yes`

Linia: `37`

Brak docstringa.

### `def require_root`

Linia: `44`

Brak docstringa.

### `def load_config`

Linia: `47`

Brak docstringa.

### `def zone_items`

Linia: `55`

Brak docstringa.

### `def sync_zone_items`

Linia: `60`

Brak docstringa.

### `def selected`

Linia: `64`

Brak docstringa.

### `def dig_lines`

Linia: `71`

Brak docstringa.

### `def dig_serial`

Linia: `77`

Brak docstringa.

### `def authoritative_servers`

Linia: `82`

Brak docstringa.

### `def parent_ds`

Linia: `83`

Brak docstringa.

### `def local_dnskeys`

Linia: `84`

Brak docstringa.

### `def has_rrsig`

Linia: `86`

Brak docstringa.

### `def delv_validate`

Linia: `99`

Brak docstringa.

### `def validation_targets`

Linia: `109`

Zwróć walidatory DNSSEC używane do ustalenia wyniku konsensusu. Konfiguracja opcjonalna w [toolkit]: dnssec_validators = 1.1.1.1, 8.8.8.8, 9.9.9.9 dnssec_validation_quorum = 2

### `def dnssec_validation_consensus`

Linia: `123`

Brak docstringa.

### `def cmd_check`

Linia: `145`

Brak docstringa.

### `def cmd_sync`

Linia: `161`

Brak docstringa.

### `def cmd_notify`

Linia: `183`

Brak docstringa.

### `def cmd_reload`

Linia: `192`

Brak docstringa.

### `def cmd_backup`

Linia: `204`

Brak docstringa.

### `def dnssec_zone_result`

Linia: `219`

Brak docstringa.

### `def cmd_dnssec_status`

Linia: `241`

Brak docstringa.

### `def explain_dnssec_result`

Linia: `256`

Brak docstringa.

### `def cmd_dnssec_check`

Linia: `284`

Brak docstringa.

### `def cmd_dnssec_report`

Linia: `309`

Brak docstringa.

### `def cmd_health`

Linia: `318`

Brak docstringa.

### `def cmd_doctor`

Linia: `332`

Brak docstringa.

### `def confirm`

Linia: `353`

Brak docstringa.

### `def update_ini_zone`

Linia: `361`

Brak docstringa.

### `def find_zone_config`

Linia: `385`

Znajdź aktywny plik zawierający deklarację zone. Nie ograniczamy wyszukiwania do ``*.conf``, ponieważ typowy plik BIND ``named.conf.local`` nie pasuje do tego wzorca. Pomijamy kopie zapasowe i pliki robocze, aby nie wykrywać tej samej strefy wielokrotnie.

### `def zone_block_bounds`

Linia: `420`

Brak docstringa.

### `def patch_zone_declaration`

Linia: `439`

Brak docstringa.

### `def generate_ds`

Linia: `456`

Brak docstringa.

### `def cmd_dnssec_enable`

Linia: `474`

Brak docstringa.

### `def tui_select`

Linia: `548`

Brak docstringa.

### `def human_age`

Linia: `577`

Brak docstringa.

### `def latest_backup`

Linia: `586`

Brak docstringa.

### `def zone_quick_status`

Linia: `592`

Brak docstringa.

### `def domain_status_lines`

Linia: `610`

Brak docstringa.

### `def cmd_zone_serial`

Linia: `624`

Brak docstringa.

### `def cmd_zone_edit`

Linia: `647`

Brak docstringa.

### `def cmd_zone_report`

Linia: `661`

Brak docstringa.

### `def cmd_backups`

Linia: `672`

Brak docstringa.

### `def domain_menu`

Linia: `680`

Brak docstringa.

### `def cmd_domains`

Linia: `702`

Brak docstringa.

### `def cmd_menu`

Linia: `726`

Brak docstringa.

### `def cmd_update`

Linia: `744`

Brak docstringa.

### `def parser`

Linia: `750`

Brak docstringa.

### `def main`

Linia: `771`

Brak docstringa.

## `src/zonectl/presentation.py`

Brak docstringa.

### `def transaction_lines`

Linia: `6`

Zbuduj wspólną prezentację wyniku transakcji dla CLI i TUI.

### `def transaction_title`

Linia: `63`

Zwróć wspólny tytuł wyniku transakcji.

### `def transaction_exit_code`

Linia: `70`

Przełóż wynik transakcji na kod procesu CLI.

## `src/zonectl/ui/__init__.py`

Terminal UI for ZoneCTL.

Brak klas i funkcji na poziomie modułu.

## `src/zonectl/ui/credits.py`

Dyskretny podpis twórców projektu w głównym widoku TUI.

### `def _safe_addnstr`

Linia: `20`

Rysuje tekst bez przerywania pracy przy małym terminalu.

### `def draw_project_credits`

Linia: `44`

Wyświetla dane twórców w prawym dolnym rogu głównego widoku. Podpis jest pomijany, gdy terminal jest zbyt mały, dzięki czemu nie nachodzi na listę domen ani dolny pasek klawiszy.

## `src/zonectl/ui/curses_app.py`

Brak docstringa.

### `class Row`

Linia: `43`

Brak docstringa.

### `class CursesApp`

Linia: `50`

Brak docstringa.

**Metody:**

- `__init__` — linia 53; brak docstringa.
- `run` — linia 97; brak docstringa.
- `_main` — linia 100; brak docstringa.
- `_init_colors` — linia 139; brak docstringa.
- `_color` — linia 149; brak docstringa.
- `_symbol` — linia 160; brak docstringa.
- `_start_refresh` — linia 163; brak docstringa.
- `_refresh_worker` — linia 171; brak docstringa.
- `_consume_results` — linia 185; brak docstringa.
- `_zone_key` — linia 196; brak docstringa.
- `_ordered_groups` — linia 213; brak docstringa.
- `_rebuild_rows` — linia 220; brak docstringa.
- `_selected_zone_name` — linia 244; brak docstringa.
- `_draw` — linia 249; brak docstringa.
- `_activate` — linia 310; brak docstringa.
- `_toggle_multi_selection` — linia 323; dodaj lub usuń bieżącą strefę z zestawu wielostrefowego.
- `_activate_group_selection` — linia 336; zachowaj dotychczasowe działanie spacji dla nagłówka grupy.
- `_search` — linia 349; filtruje domeny na głównej liście.
- `_records_view` — linia 365; wyświetla i edytuje źródłowy dokument strefy.
- `_message_view` — linia 975; wyświetla prosty modalny komunikat.
- `_function_key_sequence` — linia 1040; brak docstringa.
- `_get_key` — linia 1046; odczytuje klawisz i rozpoznaje f2 wysyłane jako esc [ 12 ~.
- `_transaction_result_view` — linia 1090; wyświetla wynik zapisu lub rollbacku transakcji.
- `_pending_changes_view` — linia 1103; wyświetla oczekujące zmiany w rekordach strefy.
- `_diff_view` — linia 1333; wyświetl przewijany unified diff bez zapisywania strefy.
- `_export_diff` — linia 1434; wyeksportuj oczekujące zmiany bez wykonywania commit.
- `_read_only_message` — linia 1462; brak docstringa.
- `_bulk_operation_view` — linia 1476; brak docstringa.
- `_bulk_preview_view` — linia 1579; pokaż podgląd; enter przechodzi do potwierdzenia.
- `_approve_zone_change` — linia 1639; odrzuć nowe błędy i wymagaj potwierdzenia nowych ostrzeżeń.
- `_multi_zone_view` — linia 1701; edytuj kilka zaznaczonych stref w jednej sesji tui.
- `_domain_view` — linia 1912; wyświetla szczegóły wybranej strefy. klawisze: - r: ponowne sprawdzenie strefy, - q / esc / backspace: powrót do listy.
- `_serial_ok` — linia 2181; brak docstringa.
- `_bool_text` — linia 2191; brak docstringa.

## `src/zonectl/ui/dialogs.py`

Brak docstringa.

### `class CursesDialogs`

Linia: `7`

Wspólne dialogi tekstowe interfejsu curses.

**Metody:**

- `normalize_query` — linia 11; normalizuje frazę wyszukiwania. wyszukiwanie działa jako dopasowanie fragmentu tekstu. gwiazdki na początku i końcu są traktowane jak opcjonalne symbole wildcard, np. *elk.pl oraz elk.pl*.
- `text_input` — linia 30; wyświetla jednowierszowy dialog tekstowy. enter zatwierdza wartość. esc anuluje dialog.
- `search` — linia 132; brak docstringa.
- `confirm` — linia 153; wyświetla potwierdzenie [t/n].

## `src/zonectl/ui/function_keys.py`

Brak docstringa.

### `def decode_function_key`

Linia: `31`

Rozpoznaj sekwencję funkcyjną xterm lub PuTTY/Linux.

## `src/zonectl/ui/records/__init__.py`

Widoki i komponenty obsługi rekordów DNS.

Brak klas i funkcji na poziomie modułu.

## `src/zonectl/ui/records/controller.py`

Stan, sortowanie i filtrowanie widoku rekordów DNS.

### `class RecordController`

Linia: `10`

Zarządza prezentacją rekordów bez zależności od curses.

**Metody:**

- `__init__` — linia 19; brak docstringa.
- `sort_name` — linia 33; brak docstringa.
- `cycle_sort` — linia 36; brak docstringa.
- `set_search` — linia 44; brak docstringa.
- `clear_search` — linia 49; brak docstringa.
- `_name_key` — linia 54; brak docstringa.
- `_type_key` — linia 67; brak docstringa.
- `_ttl_key` — linia 80; brak docstringa.
- `ordered_views` — linia 94; brak docstringa.
- `clamp_selection` — linia 140; brak docstringa.
- `move` — linia 167; brak docstringa.
- `current` — linia 181; brak docstringa.
- `select_identifier` — linia 193; brak docstringa.

## `src/zonectl/ui/records/editor.py`

Formularz edycji rekordów DNS w interfejsie curses.

### `class RecordEditor`

Linia: `18`

Obsługuje formularz edycji pojedynczego rekordu DNS.

**Metody:**

- `__init__` — linia 21; brak docstringa.
- `_owner_from_form` — linia 26; zachowaj źródłową postać właściciela, jeśli jej nie zmieniono.
- `_get_key` — linia 47; odczytuje klawisz i rozpoznaje f2 wysyłane jako esc [ 12 ~.
- `_edit_line` — linia 88; prosty edytor pojedynczej linii dla formularzy curses.
- `create_record_dialog` — linia 210; tworzy nowy rekord, wykorzystując formularz edycji.
- `edit_record_dialog` — linia 231; edytuje rekord w pamięci. zwraca nowy rekord albo none.

## `src/zonectl/ui/records/keybindings.py`

Brak docstringa.

### `class KeyBinding`

Linia: `8`

Brak docstringa.

**Metody:**

- `render` — linia 12; brak docstringa.

### `def render_footer`

Linia: `35`

Brak docstringa.

## `src/zonectl/ui/records/new_record.py`

Interaktywny kreator nowych rekordów DNS.

### `class NewRecordDialog`

Linia: `21`

Tworzy rekord DNS bez modyfikowania pliku strefy.

**Metody:**

- `__init__` — linia 29; brak docstringa.
- `default_ttl` — linia 36; pobiera ttl z głównego rekordu soa strefy.
- `absolute_owner` — linia 66; brak docstringa.
- `validate_hostname` — linia 82; brak docstringa.
- `validate_rdata` — linia 106; brak docstringa.
- `build_record` — linia 213; brak docstringa.
- `_put` — linia 263; brak docstringa.
- `_type_window` — linia 295; brak docstringa.
- `create_record_dialog` — linia 306; brak docstringa.

## `src/zonectl/ui/records/renderer.py`

Brak docstringa.

### `class RecordRenderer`

Linia: `10`

Renderuje ekran rekordów DNS bez obsługi klawiatury.

**Metody:**

- `visible_rows` — linia 17; brak docstringa.
- `summary_text` — linia 21; brak docstringa.
- `footer_text` — linia 45; brak docstringa.
- `_put` — linia 49; brak docstringa.
- `_change_attr` — linia 78; brak docstringa.
- `draw` — linia 91; brak docstringa.
