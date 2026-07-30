# Dokumentacja modułów

> Wygenerowano z AST: `2026-07-30T23:09:24+02:00`.

## `src/elkman_dns/__init__.py`

Zgodna nazwa historyczna; nowy kod powinien używać pakietu zonectl.

Brak klas i funkcji na poziomie modułu.

## `src/zonectl/__init__.py`

ZoneCTL — Transactional DNS Management Toolkit.

Brak klas i funkcji na poziomie modułu.

## `src/zonectl/cli.py`

Brak docstringa.

### `def parser`

Linia: `16`

Brak docstringa.

### `def legacy_main`

Linia: `76`

Brak docstringa.

### `def grouped_lines`

Linia: `86`

Brak docstringa.

### `def print_transaction`

Linia: `100`

Brak docstringa.

### `def transaction_main`

Linia: `110`

Brak docstringa.

### `def main`

Linia: `174`

Brak docstringa.

### `def deprecated_main`

Linia: `208`

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
- `_zones_from_discovery` — linia 328; brak docstringa.
- `_zones_from_legacy_config` — linia 342; tryb zgodności ze starym zones.conf. używany wyłącznie, gdy auto_discover_zones = no.
- `zones` — linia 414; brak docstringa.

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

Linia: `30`

Brak docstringa.

## `src/zonectl/core/paths.py`

Centralne ścieżki systemowe ZoneCTL. Ten moduł jest jedynym źródłem domyślnych ścieżek używanych przez kod Pythona. Na tym etapie zachowujemy dotychczasowe katalogi systemowe. Ich migracja do przestrzeni nazw ZoneCTL zostanie wykonana osobno, z backupem i możliwością wycofania.

Brak klas i funkcji na poziomie modułu.

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

- `ok` — linia 50; brak docstringa.

### `class ZoneLock`

Linia: `54`

Brak docstringa.

**Metody:**

- `__init__` — linia 55; brak docstringa.
- `__enter__` — linia 59; brak docstringa.
- `__exit__` — linia 73; brak docstringa.

### `class TransactionEngine`

Linia: `83`

Atomic zone-file replacement with validation, backup, reload and rollback.

**Metody:**

- `__init__` — linia 86; brak docstringa.
- `find_zone` — linia 129; brak docstringa.
- `_safe_zone_name` — linia 137; brak docstringa.
- `_digest` — linia 141; brak docstringa.
- `_step_command` — linia 148; brak docstringa.
- `_zone_validation` — linia 153; brak docstringa.
- `_config_validation` — linia 156; brak docstringa.
- `_zone_serial` — linia 159; brak docstringa.
- `_serial` — linia 169; brak docstringa.
- `_loaded_serial` — linia 176; brak docstringa.
- `_verify_loaded_zone` — linia 185; brak docstringa.
- `validate` — linia 205; brak docstringa.
- `verify` — linia 223; brak docstringa.
- `apply` — linia 316; brak docstringa.
- `rollback` — linia 432; brak docstringa.
- `backups` — linia 470; brak docstringa.
- `history` — linia 477; odczytaj ostatnie manifesty transakcji.
- `load_transaction` — linia 528; odtwórz wynik transakcji z manifestu.
- `_new_id` — linia 593; brak docstringa.
- `_backup` — linia 597; brak docstringa.
- `_atomic_install` — linia 618; brak docstringa.
- `_rollback` — linia 645; brak docstringa.
- `_save_manifest` — linia 655; brak docstringa.
- `_finish` — linia 667; brak docstringa.

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

Linia: `38`

Błąd sesji edycji strefy.

### `class ZoneSaveResult`

Linia: `43`

Brak docstringa.

**Metody:**

- `committed` — linia 48; brak docstringa.
- `ok` — linia 52; brak docstringa.
- `status` — linia 56; brak docstringa.

### `class ZoneEditSession`

Linia: `60`

Pełna sesja edycji źródłowego pliku strefy. Pipeline: ZoneFileParser -> ZoneDocument -> ZoneModel -> ZoneDocumentAdapter -> ZoneWriter -> TransactionEngine

**Metody:**

- `__init__` — linia 74; brak docstringa.
- `close` — linia 120; zwolnij blokadę sesji edycyjnej, jeśli została założona.
- `source_path` — linia 126; brak docstringa.
- `dirty` — linia 135; brak docstringa.
- `change_count` — linia 139; brak docstringa.
- `_load` — linia 142; brak docstringa.
- `_prepare_document` — linia 164; brak docstringa.
- `render_candidate` — linia 189; wygeneruj tekst kandydata bez tworzenia pliku.
- `unified_diff` — linia 196; pokaż różnice między aktywnym plikiem a kandydatem. metoda nie tworzy pliku tymczasowego i nie wykonuje transakcji.
- `export_diff` — linia 219; atomowo zapisz unified diff bez wykonywania commit.
- `create_candidate` — linia 279; utwórz bezpieczny plik tymczasowy z bieżącymi zmianami.
- `save` — linia 296; waliduj albo zapisz zmiany przez transactionengine. commit=false: dry-run, aktywny plik nie jest zmieniany. commit=true: backup, atomic install, reload, weryfikacja i rollback.
- `discard` — linia 337; porzuć wszystkie niezapisane zmiany.
- `undo` — linia 345; cofnij ostatnią zmianę bieżącej sesji.
- `reload` — linia 355; ponownie odczytaj aktywny plik strefy. niezapisane zmiany są tracone.

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

Linia: `72`

Bufor edycji rekordów pojedynczej strefy. Model nie zapisuje plików i nie wykonuje poleceń systemowych. Przechowuje jedynie stan początkowy, bieżący i wyliczony diff.

**Metody:**

- `__init__` — linia 80; brak docstringa.
- `_allocate_identifier` — linia 103; brak docstringa.
- `_snapshot` — linia 108; brak docstringa.
- `_remember` — linia 121; brak docstringa.
- `_ensure_writable` — linia 124; brak docstringa.
- `_visible_entries` — linia 130; brak docstringa.
- `_entry_at` — linia 137; brak docstringa.
- `records` — linia 148; brak docstringa.
- `original_records` — linia 156; brak docstringa.
- `record_views` — linia 164; zwraca rekordy widoczne w edytorze, również usuwane.
- `pending_changes` — linia 202; brak docstringa.
- `dirty` — linia 244; brak docstringa.
- `change_count` — linia 248; brak docstringa.
- `can_undo` — linia 252; brak docstringa.
- `add` — linia 255; brak docstringa.
- `_entry_by_identifier` — linia 268; brak docstringa.
- `replace_by_identifier` — linia 277; brak docstringa.
- `delete_by_identifier` — linia 298; brak docstringa.
- `replace` — linia 316; brak docstringa.
- `delete` — linia 338; brak docstringa.
- `undo` — linia 359; cofnij ostatnią operację wykonaną w modelu.
- `discard` — linia 369; brak docstringa.
- `accept` — linia 382; uznaje aktualny stan za nowy stan bazowy. metoda będzie używana dopiero po udanym zapisie transakcji.

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

Linia: `42`

Zwróć wspólny tytuł wyniku transakcji.

### `def transaction_exit_code`

Linia: `49`

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

Linia: `33`

Brak docstringa.

### `class CursesApp`

Linia: `40`

Brak docstringa.

**Metody:**

- `__init__` — linia 43; brak docstringa.
- `run` — linia 86; brak docstringa.
- `_main` — linia 89; brak docstringa.
- `_init_colors` — linia 124; brak docstringa.
- `_color` — linia 134; brak docstringa.
- `_symbol` — linia 145; brak docstringa.
- `_start_refresh` — linia 148; brak docstringa.
- `_refresh_worker` — linia 156; brak docstringa.
- `_consume_results` — linia 170; brak docstringa.
- `_zone_key` — linia 181; brak docstringa.
- `_ordered_groups` — linia 198; brak docstringa.
- `_rebuild_rows` — linia 205; brak docstringa.
- `_selected_zone_name` — linia 229; brak docstringa.
- `_draw` — linia 234; brak docstringa.
- `_activate` — linia 289; brak docstringa.
- `_search` — linia 302; filtruje domeny na głównej liście.
- `_records_view` — linia 318; wyświetla i edytuje źródłowy dokument strefy.
- `_message_view` — linia 881; wyświetla prosty modalny komunikat.
- `_function_key_sequence` — linia 946; brak docstringa.
- `_get_key` — linia 952; odczytuje klawisz i rozpoznaje f2 wysyłane jako esc [ 12 ~.
- `_transaction_result_view` — linia 996; wyświetla wynik zapisu lub rollbacku transakcji.
- `_pending_changes_view` — linia 1009; wyświetla oczekujące zmiany w rekordach strefy.
- `_diff_view` — linia 1239; wyświetl przewijany unified diff bez zapisywania strefy.
- `_export_diff` — linia 1340; wyeksportuj oczekujące zmiany bez wykonywania commit.
- `_read_only_message` — linia 1368; brak docstringa.
- `_domain_view` — linia 1382; wyświetla szczegóły wybranej strefy. klawisze: - r: ponowne sprawdzenie strefy, - q / esc / backspace: powrót do listy.
- `_serial_ok` — linia 1651; brak docstringa.
- `_bool_text` — linia 1661; brak docstringa.

## `src/zonectl/ui/dialogs.py`

Brak docstringa.

### `class CursesDialogs`

Linia: `6`

Wspólne dialogi tekstowe interfejsu curses.

**Metody:**

- `normalize_query` — linia 10; normalizuje frazę wyszukiwania. wyszukiwanie działa jako dopasowanie fragmentu tekstu. gwiazdki na początku i końcu są traktowane jak opcjonalne symbole wildcard, np. *elk.pl oraz elk.pl*.
- `text_input` — linia 29; wyświetla jednowierszowy dialog tekstowy. enter zatwierdza wartość. esc anuluje dialog.
- `search` — linia 131; brak docstringa.
- `confirm` — linia 152; wyświetla potwierdzenie [t/n].

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

Linia: `14`

Obsługuje formularz edycji pojedynczego rekordu DNS.

**Metody:**

- `__init__` — linia 17; brak docstringa.
- `_owner_from_form` — linia 22; zachowaj źródłową postać właściciela, jeśli jej nie zmieniono.
- `_get_key` — linia 43; odczytuje klawisz i rozpoznaje f2 wysyłane jako esc [ 12 ~.
- `_edit_line` — linia 84; prosty edytor pojedynczej linii dla formularzy curses.
- `create_record_dialog` — linia 206; tworzy nowy rekord, wykorzystując formularz edycji.
- `edit_record_dialog` — linia 227; edytuje rekord w pamięci. zwraca nowy rekord albo none.

## `src/zonectl/ui/records/keybindings.py`

Brak docstringa.

### `class KeyBinding`

Linia: `8`

Brak docstringa.

**Metody:**

- `render` — linia 12; brak docstringa.

### `def render_footer`

Linia: `34`

Brak docstringa.

## `src/zonectl/ui/records/new_record.py`

Interaktywny kreator nowych rekordów DNS.

### `class NewRecordDialog`

Linia: `35`

Tworzy rekord DNS bez modyfikowania pliku strefy.

**Metody:**

- `__init__` — linia 43; brak docstringa.
- `default_ttl` — linia 50; pobiera ttl z głównego rekordu soa strefy.
- `absolute_owner` — linia 80; brak docstringa.
- `validate_hostname` — linia 96; brak docstringa.
- `validate_rdata` — linia 120; brak docstringa.
- `build_record` — linia 227; brak docstringa.
- `_put` — linia 277; brak docstringa.
- `_type_window` — linia 309; brak docstringa.
- `create_record_dialog` — linia 320; brak docstringa.

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
