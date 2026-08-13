# Dokumentacja modułów

> Wygenerowano z AST: `2026-08-13T19:16:42+02:00`.

## `src/elkman_dns/__init__.py`

Zgodna nazwa historyczna; nowy kod powinien używać pakietu zonectl.

Brak klas i funkcji na poziomie modułu.

## `src/zonectl/__init__.py`

ZoneCTL — Transactional DNS Management Toolkit.

Brak klas i funkcji na poziomie modułu.

## `src/zonectl/cli.py`

Brak docstringa.

### `def parser`

Linia: `82`

Brak docstringa.

### `def legacy_main`

Linia: `779`

Brak docstringa.

### `def grouped_lines`

Linia: `789`

Brak docstringa.

### `def print_transaction`

Linia: `803`

Brak docstringa.

### `def transaction_main`

Linia: `812`

Brak docstringa.

### `def main`

Linia: `876`

Brak docstringa.

### `def deprecated_main`

Linia: `2264`

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

## `src/zonectl/core/bind_access_audit.py`

Safety audit for BIND ACLs and secondary server groups.

### `class BindAccessFinding`

Linia: `14`

Brak docstringa.

**Metody:**

- `to_dict` — linia 22; brak docstringa.

### `class BindAccessAudit`

Linia: `30`

Brak docstringa.

**Metody:**

- `to_dict` — linia 34; brak docstringa.

### `class BindAccessAuditor`

Linia: `41`

Brak docstringa.

**Metody:**

- `audit` — linia 44; brak docstringa.
- `_definition_findings` — linia 119; brak docstringa.
- `_reference` — linia 187; brak docstringa.

## `src/zonectl/core/bind_access_inventory.py`

Read-only inventory of BIND ACLs and named secondary server groups.

### `class BindAccessInventoryError`

Linia: `12`

Brak docstringa.

### `class BindListDefinition`

Linia: `17`

Brak docstringa.

**Metody:**

- `to_dict` — linia 24; brak docstringa.

### `class BindListUsage`

Linia: `32`

Brak docstringa.

**Metody:**

- `to_dict` — linia 39; brak docstringa.

### `class BindAccessInventory`

Linia: `47`

Brak docstringa.

**Metody:**

- `to_dict` — linia 51; brak docstringa.

### `class BindAccessInventoryReader`

Linia: `58`

Brak docstringa.

**Metody:**

- `__init__` — linia 68; brak docstringa.
- `collect` — linia 71; brak docstringa.
- `_zone_ranges` — linia 123; brak docstringa.
- `_entries` — linia 136; brak docstringa.
- `_mask_comments` — linia 145; brak docstringa.

## `src/zonectl/core/bind_acl_plan.py`

Read-only, validated cleanup plan for one BIND ACL.

### `class BindAclPlanError`

Linia: `18`

Brak docstringa.

### `class BindAclPlan`

Linia: `23`

Brak docstringa.

**Metody:**

- `to_dict` — linia 34; brak docstringa.

### `class BindAclPlanner`

Linia: `42`

Brak docstringa.

**Metody:**

- `__init__` — linia 48; brak docstringa.
- `plan` — linia 51; brak docstringa.
- `_validate_full_entries` — linia 118; brak docstringa.
- `_replace_entries` — linia 147; brak docstringa.
- `_rewrite_body` — linia 173; brak docstringa.
- `_normalized` — linia 204; brak docstringa.
- `_validate_candidate` — linia 213; brak docstringa.

## `src/zonectl/core/bind_acl_transaction.py`

Transactional application of a validated BIND ACL plan.

### `class BindAclStep`

Linia: `20`

Brak docstringa.

### `class BindAclResult`

Linia: `27`

Brak docstringa.

### `class BindAclTransaction`

Linia: `42`

Brak docstringa.

**Metody:**

- `__init__` — linia 43; brak docstringa.
- `apply` — linia 58; brak docstringa.
- `_write_manifest` — linia 144; brak docstringa.
- `_atomic_write` — linia 155; brak docstringa.
- `_validate_config` — linia 170; brak docstringa.
- `_activate` — linia 176; brak docstringa.

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

## `src/zonectl/core/bind_environment_report.py`

Odczytowa autodetekcja środowiska BIND i integracji RPZ.

### `class RpzEnvironment`

Linia: `16`

Stan pojedynczej strefy używanej przez ``response-policy``.

### `class BindEnvironmentReport`

Linia: `38`

Wynik pierwszego, pozbawionego skutków ubocznych rozpoznania BIND.

**Metody:**

- `to_dict` — linia 50; brak docstringa.

### `class BindEnvironmentReporter`

Linia: `54`

Rozpoznaje aktywną konfigurację bez zapisywania plików i wywołań mutujących.

**Metody:**

- `__init__` — linia 67; brak docstringa.
- `collect` — linia 84; brak docstringa.
- `_response_policy_zones` — linia 121; brak docstringa.
- `_rpz_environment` — linia 136; brak docstringa.
- `_systemctl_bool` — linia 190; brak docstringa.
- `_systemctl_property` — linia 193; brak docstringa.
- `_systemctl_exec_path` — linia 200; brak docstringa.
- `_status_values` — linia 210; brak docstringa.

## `src/zonectl/core/bind_onboarding_report.py`

Odczytowy raport gotowości istniejącego BIND do importu przez ZoneCTL.

### `class OnboardingClass`

Linia: `14`

Brak docstringa.

### `class OnboardingCandidate`

Linia: `21`

Brak docstringa.

### `class OnboardingBlocker`

Linia: `29`

Brak docstringa.

### `class BindOnboardingReport`

Linia: `36`

Brak docstringa.

**Metody:**

- `to_dict` — linia 52; brak docstringa.

### `class BindOnboardingReporter`

Linia: `56`

Łączy istniejące inwentaryzacje bez modyfikowania konfiguracji.

**Metody:**

- `__init__` — linia 70; brak docstringa.
- `collect` — linia 73; brak docstringa.
- `_normalise_state` — linia 137; brak docstringa.

## `src/zonectl/core/bind_secondary_plan.py`

Read-only validated plan for changing one BIND secondary group.

### `class BindSecondaryPlanError`

Linia: `19`

Brak docstringa.

### `class BindSecondaryPlan`

Linia: `24`

Brak docstringa.

**Metody:**

- `to_dict` — linia 38; brak docstringa.

### `class BindSecondaryPlanner`

Linia: `46`

Brak docstringa.

**Metody:**

- `__init__` — linia 53; brak docstringa.
- `plan` — linia 56; brak docstringa.
- `_validate_addresses` — linia 121; brak docstringa.
- `_format_body` — linia 140; brak docstringa.
- `_validate_candidate` — linia 157; brak docstringa.

## `src/zonectl/core/bind_secondary_report.py`

Read-only impact report for BIND secondary/notify groups.

### `class SecondaryGroupReport`

Linia: `12`

Brak docstringa.

**Metody:**

- `to_dict` — linia 22; brak docstringa.

### `class SecondaryPairReport`

Linia: `31`

Brak docstringa.

**Metody:**

- `to_dict` — linia 40; brak docstringa.

### `class BindSecondaryReport`

Linia: `51`

Brak docstringa.

**Metody:**

- `to_dict` — linia 55; brak docstringa.

### `class BindSecondaryReporter`

Linia: `62`

Brak docstringa.

**Metody:**

- `build` — linia 66; brak docstringa.
- `_role` — linia 129; brak docstringa.
- `_base_name` — linia 137; brak docstringa.

## `src/zonectl/core/bind_secondary_transaction.py`

Transactional application of a validated BIND secondary-group plan.

### `class BindSecondaryStep`

Linia: `20`

Brak docstringa.

### `class BindSecondaryResult`

Linia: `27`

Brak docstringa.

### `class BindSecondaryTransaction`

Linia: `46`

Brak docstringa.

**Metody:**

- `__init__` — linia 47; brak docstringa.
- `apply` — linia 62; brak docstringa.
- `_write_manifest` — linia 165; brak docstringa.
- `_atomic_write` — linia 176; brak docstringa.
- `_validate_config` — linia 191; brak docstringa.
- `_activate` — linia 197; brak docstringa.

## `src/zonectl/core/bind_zone_secondary.py`

Plan assignment of one primary zone to logical secondary groups.

### `class BindZoneSecondaryError`

Linia: `17`

Brak docstringa.

### `class BindZoneSecondaryPlan`

Linia: `22`

Brak docstringa.

**Metody:**

- `transaction_plan` — linia 33; brak docstringa.

### `class BindZoneSecondaryPlanner`

Linia: `44`

Brak docstringa.

**Metody:**

- `__init__` — linia 47; brak docstringa.
- `available_pairs` — linia 50; brak docstringa.
- `plan` — linia 54; brak docstringa.
- `_directive_values` — linia 102; brak docstringa.
- `_set_directive` — linia 112; brak docstringa.

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
- `_zones_from_discovery` — linia 331; brak docstringa.
- `_zones_from_legacy_config` — linia 345; tryb zgodności ze starym zones.conf. używany wyłącznie, gdy auto_discover_zones = no.
- `zones` — linia 428; brak docstringa.

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

## `src/zonectl/core/dnssec_confirm_ds.py`

Controlled acknowledgement of a published DS record in BIND KASP.

### `class DnssecConfirmStep`

Linia: `20`

Brak docstringa.

### `class DnssecConfirmResult`

Linia: `27`

Brak docstringa.

### `class DnssecConfirmDsTransaction`

Linia: `40`

Acknowledge DS only after an independent check returned PASS.

**Metody:**

- `__init__` — linia 43; brak docstringa.
- `apply` — linia 56; brak docstringa.
- `_finish` — linia 121; brak docstringa.
- `_atomic_json` — linia 141; brak docstringa.
- `_confirm` — linia 156; brak docstringa.
- `_verify` — linia 162; brak docstringa.

## `src/zonectl/core/dnssec_disable_plan.py`

Side-effect-free plan for safely withdrawing DNSSEC from a BIND zone.

### `class DnssecDisablePlanError`

Linia: `13`

The requested DNSSEC withdrawal is unsafe or ambiguous.

### `class DnssecDisablePlan`

Linia: `18`

Brak docstringa.

**Metody:**

- `to_dict` — linia 33; brak docstringa.

### `class DnssecDisablePlanner`

Linia: `45`

Build the final unsigned configuration without changing the system.

**Metody:**

- `_artifacts` — linia 63; brak docstringa.
- `plan` — linia 72; brak docstringa.

## `src/zonectl/core/dnssec_disable_transaction.py`

Transakcyjne wycofanie DNSSEC — dwa etapy. BIND nie pozwala po prostu usunąć ``dnssec-policy``: dokumentacja wymaga przejścia przez wbudowaną politykę ``insecure``, bo w przeciwnym razie strefa zostanie ponownie podpisana. Stąd dwa etapy: **Etap ``insecure``** — podmienia ``dnssec-policy default`` na ``dnssec-policy insecure``, zostawiając ``inline-signing``. Bramką jest zniknięcie DS ze wszystkich kontrolowanych resolverów, czyli dokładnie ten sam warunek, który przepuszcza ``withdrawal-confirm``. Dopiero ta zmiana przestawia cel KASP z ``omnipresent`` na ``hidden`` i uruchamia uporządkowane wycofywanie kluczy. **Etap ``finalize``** — usuwa ``dnssec-policy``, ``inline-signing`` i ``key-directory``. Bramką jest potwierdzenie z KASP, że **wszystkie** klucze mają ``goal``, ``dnskey`` i ``ds`` w stanie ``hidden``. Ta bramka jest osiągalna wyłącznie po etapie pierwszym. W obu etapach brak ``--commit`` oznacza dry-run, każde niepowodzenie walidacji powoduje pełny rollback deklaracji z backupu, a klucze i pakiet odtworzeniowy pozostają nietknięte.

### `class DnssecDisableStep`

Linia: `42`

Brak docstringa.

### `class DnssecDisableResult`

Linia: `49`

Brak docstringa.

**Metody:**

- `ok` — linia 62; brak docstringa.

### `class KaspReading`

Linia: `74`

Odczyt stanu kluczy z ``rndc dnssec -status``. ``all_hidden`` jest ``None``, gdy wyjścia nie udało się zinterpretować — tylko wtedy dopuszczamy świadome przesłonięcie bramki.

### `def read_kasp_states`

Linia: `89`

Brak docstringa.

### `class DnssecDisableTransaction`

Linia: `106`

Stosuje diff wycofania DNSSEC z backupem i pełnym rollbackiem.

**Metody:**

- `__init__` — linia 109; brak docstringa.
- `apply` — linia 132; brak docstringa.
- `_insecure_gate` — linia 268; etap 1 wolno wykonać dopiero, gdy ds zniknął z resolverów.
- `_finalize_gate` — linia 313; etap 2 wolno wykonać dopiero, gdy kasp schował wszystkie klucze.
- `_serial_gate` — linia 358; nie dopuść do cofnięcia soa po odłączeniu inline-signing.
- `_preflight` — linia 409; brak docstringa.
- `_finish` — linia 426; brak docstringa.
- `_copy_backup` — linia 451; brak docstringa.
- `_atomic_write` — linia 458; brak docstringa.
- `_validate_config` — linia 477; brak docstringa.
- `_activate_bind` — linia 486; brak docstringa.
- `_verify_loaded` — linia 495; brak docstringa.

## `src/zonectl/core/dnssec_ds_check.py`

Read-only verification of DNSSEC delegation and authoritative servers.

### `class DsResolverCheck`

Linia: `14`

Brak docstringa.

### `class DnskeyAuthorityCheck`

Linia: `22`

Brak docstringa.

### `class DnssecDsCheck`

Linia: `32`

Brak docstringa.

**Metody:**

- `to_dict` — linia 42; brak docstringa.

### `class DnssecDsChecker`

Linia: `46`

Compare DS and DNSKEY through independent read-only DNS queries.

**Metody:**

- `__init__` — linia 49; brak docstringa.
- `_command` — linia 60; brak docstringa.
- `_dig` — linia 63; brak docstringa.
- `_normal` — linia 85; brak docstringa.
- `_kasp_ready` — linia 89; brak docstringa.
- `_kasp_ds_state` — linia 103; brak docstringa.
- `collect` — linia 111; brak docstringa.

## `src/zonectl/core/dnssec_enable_plan.py`

Pozbawiony skutków ubocznych plan włączenia DNSSEC w BIND.

### `class DnssecEnablePlanError`

Linia: `13`

Plan włączenia DNSSEC jest niebezpieczny albo niejednoznaczny.

### `class DnssecEnablePlan`

Linia: `18`

Brak docstringa.

**Metody:**

- `to_dict` — linia 31; brak docstringa.

### `class DnssecEnablePlanner`

Linia: `43`

Buduje plan zmiany deklaracji strefy, ale niczego nie zapisuje.

**Metody:**

- `_display_lines` — linia 55; normalizuje wyłącznie końcowe spacje na potrzeby czytelnego diffu.
- `_unified_range` — linia 65; brak docstringa.
- `_unified_diff` — linia 74; tworzy diff bez heurystyki autojunk mylącej powtarzalne bloki bind.
- `_matching_brace` — linia 108; brak docstringa.
- `_target_block` — linia 133; brak docstringa.
- `plan` — linia 155; brak docstringa.

## `src/zonectl/core/dnssec_enable_transaction.py`

Transakcyjne zastosowanie planu włączenia DNSSEC.

### `class DnssecEnableStep`

Linia: `20`

Brak docstringa.

### `class DnssecEnableResult`

Linia: `27`

Brak docstringa.

**Metody:**

- `ok` — linia 38; brak docstringa.

### `class DnssecEnableTransaction`

Linia: `47`

Stosuje plan DNSSEC z backupem i pełnym rollbackiem plików.

**Metody:**

- `__init__` — linia 50; brak docstringa.
- `apply` — linia 71; brak docstringa.
- `_preflight` — linia 182; brak docstringa.
- `_finish` — linia 208; brak docstringa.
- `_copy_backup` — linia 229; brak docstringa.
- `_atomic_write` — linia 236; brak docstringa.
- `_atomic_copy_exact` — linia 253; brak docstringa.
- `_atomic_copy_to_parent_owner` — linia 258; brak docstringa.
- `_remove_new_artifacts` — linia 264; brak docstringa.
- `_validate_zone` — linia 270; brak docstringa.
- `_validate_config` — linia 275; brak docstringa.
- `_activate_bind` — linia 280; brak docstringa.
- `_verify_loaded` — linia 285; brak docstringa.
- `_verify_dnssec` — linia 290; brak docstringa.

## `src/zonectl/core/dnssec_finalize_serial.py`

Safe SOA preparation before DNSSEC withdrawal finalization.

### `class DnssecFinalizeSerialStep`

Linia: `22`

Brak docstringa.

### `class DnssecFinalizeSerialResult`

Linia: `29`

Brak docstringa.

### `class DnssecFinalizeSerialTransaction`

Linia: `45`

Raise the source SOA above the currently served signed serial.

**Metody:**

- `__init__` — linia 48; brak docstringa.
- `apply` — linia 61; brak docstringa.
- `_blocked` — linia 151; brak docstringa.
- `_served_serial` — linia 159; brak docstringa.
- `_validate_zone` — linia 174; brak docstringa.

## `src/zonectl/core/dnssec_guidance.py`

Operator guidance derived from the read-only DNSSEC report.

### `class DnssecGuidance`

Linia: `15`

Brak docstringa.

**Metody:**

- `to_dict` — linia 23; brak docstringa.

### `def _kasp_states`

Linia: `27`

Brak docstringa.

### `def localize_bind_time`

Linia: `40`

Convert a BIND GMT timestamp to the server's local timezone.

### `def build_dnssec_guidance`

Linia: `53`

Return one unambiguous next step without changing BIND.

## `src/zonectl/core/dnssec_onboarding_audit.py`

Zbiorczy, odczytowy audyt gotowości deklaracji DNSSEC do importu.

### `class DnssecOnboardingAuditItem`

Linia: `15`

Brak docstringa.

**Metody:**

- `to_dict` — linia 22; brak docstringa.

### `class DnssecOnboardingAuditor`

Linia: `26`

Sprawdza wiele stref kolejno, nie modyfikując BIND, KASP ani DS.

**Metody:**

- `__init__` — linia 29; brak docstringa.
- `audit` — linia 44; brak docstringa.

## `src/zonectl/core/dnssec_report.py`

Odczytowy raport konfiguracji i stanu DNSSEC strefy.

### `class DnssecReport`

Linia: `18`

Brak docstringa.

**Metody:**

- `to_dict` — linia 38; brak docstringa.

### `def _dns_name_wire`

Linia: `44`

Brak docstringa.

### `def _key_tag`

Linia: `57`

Brak docstringa.

### `def dnskey_to_ds`

Linia: `65`

Oblicz RDATA rekordu DS z tekstowego RDATA DNSKEY (RFC 4034).

### `def _answer_rdata`

Linia: `86`

Brak docstringa.

### `class DnssecReporter`

Linia: `116`

Zbiera stan DNSSEC bez wykonywania operacji zmieniających system.

**Metody:**

- `__init__` — linia 119; brak docstringa.
- `_command` — linia 132; brak docstringa.
- `_dig` — linia 139; brak docstringa.
- `_key_files` — linia 155; brak docstringa.
- `_signing_state` — linia 168; brak docstringa.
- `collect` — linia 189; brak docstringa.

## `src/zonectl/core/dnssec_withdrawal_backup.py`

Verified recovery package created before DNSSEC withdrawal.

### `class DnssecWithdrawalBackupStep`

Linia: `19`

Brak docstringa.

### `class DnssecWithdrawalBackupResult`

Linia: `26`

Brak docstringa.

### `class DnssecWithdrawalBackupError`

Linia: `36`

A complete and verified recovery package could not be created.

### `class DnssecWithdrawalBackup`

Linia: `40`

Copy every withdrawal input into an atomically published package.

**Metody:**

- `__init__` — linia 43; brak docstringa.
- `_sha256` — linia 47; brak docstringa.
- `_copy_record` — linia 55; brak docstringa.
- `_sources` — linia 84; brak docstringa.
- `_preflight` — linia 97; brak docstringa.
- `create` — linia 108; brak docstringa.

## `src/zonectl/core/dnssec_withdrawal_check.py`

Read-only confirmation that DS has disappeared everywhere before withdrawal. This is the mirror image of :mod:`dnssec_ds_check`: instead of waiting for a DS record to *appear* at every resolver, it waits for the DS record to *disappear* at every resolver before allowing the operator to run ``rndc dnssec -checkds withdrawn``. As long as any checked resolver still returns a DS record, the result is ``BLOCKED`` and no follow-up command should touch KASP or the registrar.

### `class ResolverDsWithdrawalCheck`

Linia: `21`

Brak docstringa.

### `class DnssecWithdrawalCheckResult`

Linia: `29`

Brak docstringa.

**Metody:**

- `to_dict` — linia 36; brak docstringa.

### `class DnssecWithdrawalChecker`

Linia: `40`

Confirms DS is gone everywhere before permitting the withdrawn step. Purely read-only: issues ``dig ... DS`` queries against each resolver and never touches BIND, KASP, or the registrar. ``dig_runner`` can be injected for testing; it defaults to a real ``subprocess.run`` call.

**Metody:**

- `__init__` — linia 48; brak docstringa.
- `_default_dig_runner` — linia 57; brak docstringa.
- `_check_resolver` — linia 68; brak docstringa.
- `collect` — linia 102; brak docstringa.

## `src/zonectl/core/dnssec_withdrawal_confirm.py`

Guarded confirmation of DNSSEC withdrawal. This is the write-side counterpart to :mod:`dnssec_withdrawal_check`. It is the only place in ZoneCTL allowed to run ``rndc dnssec -checkds withdrawn``, and it refuses to do so unless: 1. the caller passed ``--commit`` (otherwise it is a pure dry-run), and 2. the caller passed the explicit ``--acknowledge-withdrawn`` flag, and 3. a *freshly run* :class:`DnssecWithdrawalChecker` reports ``READY_FOR_WITHDRAWN`` at the moment of the call. Any of those failing leaves BIND, KASP, and the zone completely untouched and returns ``BLOCKED`` with the reason. A successful run writes a manifest recording the DS check that authorized it, so the decision is auditable after the fact.

### `class DnssecWithdrawalConfirmStep`

Linia: `36`

Brak docstringa.

### `class DnssecWithdrawalConfirmResult`

Linia: `43`

Brak docstringa.

### `class DnssecWithdrawalConfirmTransaction`

Linia: `52`

Executes the withdrawn step only behind a freshly verified gate.

**Metody:**

- `__init__` — linia 55; brak docstringa.
- `_default_rndc_runner` — linia 68; brak docstringa.
- `_step` — linia 79; brak docstringa.
- `apply` — linia 82; brak docstringa.

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

## `src/zonectl/core/managed_zone_migration.py`

Read-only inventory and plans for migrating legacy BIND declarations.

### `class ManagedZoneMigrationError`

Linia: `14`

A migration cannot be planned without violating a safety rule.

### `class ManagedZoneInventoryItem`

Linia: `19`

Brak docstringa.

**Metody:**

- `to_dict` — linia 28; brak docstringa.

### `class ManagedZoneMigrationPlan`

Linia: `38`

Brak docstringa.

**Metody:**

- `to_dict` — linia 53; brak docstringa.

### `class _ZoneSpan`

Linia: `62`

Brak docstringa.

### `class ManagedZoneMigrationPlanner`

Linia: `69`

Build migration inventory and unified diffs without writing files.

**Metody:**

- `__init__` — linia 81; brak docstringa.
- `inventory` — linia 96; brak docstringa.
- `plan` — linia 117; brak docstringa.
- `_discover` — linia 246; brak docstringa.
- `_inventory_item` — linia 252; brak docstringa.
- `_is_rpz` — linia 316; brak docstringa.
- `_key` — linia 322; brak docstringa.
- `_read` — linia 326; brak docstringa.
- `_zone_spans` — linia 337; brak docstringa.
- `_mask_comments` — linia 373; brak docstringa.
- `_included_paths` — linia 420; brak docstringa.
- `_append_include` — linia 431; brak docstringa.
- `_diff` — linia 438; brak docstringa.

## `src/zonectl/core/managed_zone_migration_transaction.py`

Transactional migration of one legacy BIND zone declaration.

### `class ManagedZoneMigrationStep`

Linia: `20`

Brak docstringa.

### `class ManagedZoneMigrationResult`

Linia: `27`

Brak docstringa.

### `class ManagedZoneMigrationTransaction`

Linia: `42`

Apply a precomputed plan atomically and restore all files on failure.

**Metody:**

- `__init__` — linia 45; brak docstringa.
- `apply` — linia 62; brak docstringa.
- `_preflight` — linia 175; brak docstringa.
- `_write_manifest` — linia 190; brak docstringa.
- `_atomic_write` — linia 201; brak docstringa.
- `_validate_config` — linia 217; brak docstringa.
- `_activate` — linia 223; brak docstringa.
- `_verify_loaded` — linia 229; brak docstringa.

## `src/zonectl/core/models.py`

Brak docstringa.

### `class Health`

Linia: `8`

Brak docstringa.

### `class Zone`

Linia: `16`

Brak docstringa.

### `class ZoneStatus`

Linia: `33`

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

## `src/zonectl/ui/about_view.py`

Treść ekranu F1 prezentującego projekt i jego autorstwo.

### `class AboutView`

Linia: `9`

Brak docstringa.

**Metody:**

- `build` — linia 14; brak docstringa.

## `src/zonectl/ui/bind_onboarding_view.py`

Prezentacja raportu pierwszego uruchomienia w TUI.

### `class BindOnboardingView`

Linia: `11`

Brak docstringa.

**Metody:**

- `build` — linia 16; brak docstringa.

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

Linia: `86`

Brak docstringa.

### `class CursesApp`

Linia: `93`

Brak docstringa.

**Metody:**

- `__init__` — linia 96; brak docstringa.
- `run` — linia 141; brak docstringa.
- `_main` — linia 144; brak docstringa.
- `_init_colors` — linia 195; brak docstringa.
- `_color` — linia 216; brak docstringa.
- `_symbol` — linia 227; brak docstringa.
- `_start_refresh` — linia 230; brak docstringa.
- `_refresh_worker` — linia 238; brak docstringa.
- `_consume_results` — linia 252; brak docstringa.
- `_zone_key` — linia 263; brak docstringa.
- `_ordered_groups` — linia 280; brak docstringa.
- `_rebuild_rows` — linia 287; brak docstringa.
- `_selected_zone_name` — linia 311; brak docstringa.
- `_draw` — linia 316; brak docstringa.
- `_draw_main_footer` — linia 417; rysuje pasek mc, wyróżniając klawisze zgodnie z koncepcją 4.8.
- `_draw_zone_details_panel` — linia 449; rysuje dolny panel zgodny z opublikowaną koncepcją tui 4.8.
- `_activate` — linia 532; brak docstringa.
- `_selected_zone_preview` — linia 545; otwiera kontekstowy podgląd f3; dla rpz pokazuje stan integracji.
- `_selected_zone_edit` — linia 557; otwiera ekran strefy, zachowując rpz jako zasób tylko do odczytu.
- `_rpz_status_view` — linia 578; pokazuje odczytowy panel rpz, łącząc wiek pliku z systemd i bind.
- `_bind_onboarding_view` — linia 612; pokazuje gotowość istniejącego bind bez wykonywania importu.
- `_about_view` — linia 632; pokazuje koncepcyjny ekran autorstwa zgodny wizualnie z tui 4.8.
- `_draw_about_identity` — linia 685; lewa kolumna ekranu f1: człowiek, ai i charakter projektu.
- `_draw_about_history` — linia 701; prawa kolumna ekranu f1: historia i repozytorium.
- `_draw_about_compact` — linia 722; jednokolumnowy wariant f1 dla węższych terminali.
- `_onboarding_summary_view` — linia 743; raport f2 z przejściem do listy kandydatów klawiszem enter.
- `_onboarding_footer` — linia 801; pokazuje wyłącznie akcje mające dostępne elementy docelowe.
- `_draw_onboarding_summary_48` — linia 811; rysuje raport środowiska w dwukolumnowym układzie zonectl 4.8.
- `_refresh_onboarding_report` — linia 916; ponownie odkrywa bind po wyjściu z listy importu.
- `_onboarding_candidates_view` — linia 921; lista legacy: plan, dry-run i jawnie potwierdzony import.
- `_show_bind_onboarding_plan` — linia 986; wyświetla diff kandydata; ten przepływ nie ma ścieżki zapisu.
- `_onboarding_dnssec_view` — linia 1008; koncepcyjny ekran stref dnssec: wyłącznie plan i dry-run.
- `_draw_dnssec_onboarding_48` — linia 1075; rysuje listę importu dnssec zgodnie z wizualnym kontraktem 4.8.
- `_show_dnssec_onboarding_plan` — linia 1142; pokazuje deklaracyjny plan dnssec bez operacji na kluczach.
- `_dnssec_onboarding_audit_view` — linia 1164; pokazuje zbiorczą gotowość dnssec w koncepcyjnym układzie 4.8.
- `_dnssec_onboarding_audit_result_view` — linia 1206; pokazuje zbiorczy audyt dnssec w układzie zonectl 4.8.
- `_dry_run_dnssec_onboarding_import` — linia 1314; uruchamia transakcyjny dry-run profilu dnssec bez aktywacji.
- `_dnssec_import_gate` — linia 1337; wymaga aktywnego, w pełni zgodnego łańcucha dnssec.
- `_commit_dnssec_onboarding_import` — linia 1380; importuje deklarację dnssec z bramką przed i po rndc reconfig.
- `_dry_run_bind_onboarding_import` — linia 1458; waliduje transakcję importu bez zapisu plików i aktywacji bind.
- `_commit_bind_onboarding_import` — linia 1498; importuje jedną deklarację po dwóch niezależnych potwierdzeniach.
- `_toggle_multi_selection` — linia 1569; dodaj lub usuń bieżącą strefę z zestawu wielostrefowego.
- `_activate_group_selection` — linia 1582; zachowaj dotychczasowe działanie spacji dla nagłówka grupy.
- `_search` — linia 1595; filtruje domeny na głównej liście.
- `_create_zone_wizard` — linia 1611; collect, preview and transactionally create a primary zone.
- `_records_view` — linia 1715; wyświetla i edytuje źródłowy dokument strefy.
- `_message_view` — linia 2325; wyświetla zawijany i przewijany modalny komunikat.
- `_draw_message_view_48` — linia 2409; wspólny renderer komunikatów, planów i wyników w układzie 4.8.
- `_draw_context_panel_48` — linia 2478; dodaje panel kontekstowy 4.8 do starszych ekranów listowych.
- `_onboarding_result_view` — linia 2515; renderuje wynik importu w dwukolumnowym układzie tui 4.8.
- `_wrap_message_lines` — linia 2616; zawijaj tekst, zachowując puste linie i wcięcie kontynuacji.
- `_function_key_sequence` — linia 2640; brak docstringa.
- `_get_key` — linia 2646; odczytuje klawisz i rozpoznaje f2 wysyłane jako esc [ 12 ~.
- `_transaction_result_view` — linia 2690; wyświetla wynik zapisu lub rollbacku transakcji.
- `_pending_changes_view` — linia 2703; wyświetla oczekujące zmiany w rekordach strefy.
- `_diff_view` — linia 2951; wyświetl przewijany unified diff bez zapisywania strefy.
- `_export_diff` — linia 3062; wyeksportuj oczekujące zmiany bez wykonywania commit.
- `_read_only_message` — linia 3090; brak docstringa.
- `_bulk_operation_view` — linia 3104; brak docstringa.
- `_bulk_preview_view` — linia 3207; pokaż podgląd; enter przechodzi do potwierdzenia.
- `_approve_zone_change` — linia 3277; odrzuć nowe błędy i wymagaj potwierdzenia nowych ostrzeżeń.
- `_multi_zone_view` — linia 3339; edytuj kilka zaznaczonych stref w jednej sesji tui.
- `_collect_dnssec_status` — linia 3561; brak docstringa.
- `_ensure_dnssec_tui_allowed` — linia 3593; brak docstringa.
- `_dnssec_disable_plan` — linia 3599; brak docstringa.
- `_dnssec_enable_plan` — linia 3610; brak docstringa.
- `_dnssec_enable_dry_run` — linia 3621; brak docstringa.
- `_dnssec_enable_commit` — linia 3628; brak docstringa.
- `_dnssec_confirm_ds` — linia 3635; brak docstringa.
- `_dnssec_finalize_dry_run` — linia 3659; brak docstringa.
- `_dnssec_finalize_commit` — linia 3666; brak docstringa.
- `_dnssec_withdrawal_backup` — linia 3673; brak docstringa.
- `_dnssec_backup_result_lines` — linia 3705; brak docstringa.
- `_dnssec_enable_result_lines` — linia 3721; brak docstringa.
- `_dnssec_confirm_result_lines` — linia 3734; brak docstringa.
- `_dnssec_disable_result_lines` — linia 3748; brak docstringa.
- `_dnssec_status_view` — linia 3762; read-only dnssec workflow status with explicit operator guidance.
- `_draw_dnssec_status_48` — linia 4172; rysuje status strefy dnssec w dwukolumnowym układzie 4.8.
- `_draw_domain_view_48` — linia 4270; rysuje szczegóły strefy zgodnie z opublikowanym układem 4.8.
- `_domain_view` — linia 4390; wyświetla szczegóły wybranej strefy. klawisze: - r: ponowne sprawdzenie strefy, - q / esc / backspace: powrót do listy.
- `_zone_secondary_view` — linia 4674; brak docstringa.
- `_bind_root_config` — linia 4747; brak docstringa.
- `_bind_access_view` — linia 4751; f9 browser for named acls and secondary groups.
- `_show_bind_access_item` — linia 4824; brak docstringa.
- `_secondary_result_lines` — linia 4840; brak docstringa.
- `_edit_acl` — linia 4852; brak docstringa.
- `_acl_entry_editor` — linia 4891; full-screen editor for hosts, networks and named acl elements.
- `_edit_secondary_group` — linia 4955; brak docstringa.
- `_secondary_address_editor` — linia 5000; full-screen mc-style editor for a secondary address list.
- `_zone_migration_planner` — linia 5076; brak docstringa.
- `_migration_result_lines` — linia 5094; brak docstringa.
- `_zone_migration_view` — linia 5112; f3 shows a plan; f4 runs dry-run and guarded migration.
- `_show_zone_migration_plan` — linia 5191; brak docstringa.
- `_apply_zone_migration` — linia 5216; brak docstringa.
- `_serial_ok` — linia 5274; brak docstringa.
- `_bool_text` — linia 5284; brak docstringa.

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

## `src/zonectl/ui/dnssec_status_view.py`

Presentation model for the read-only DNSSEC TUI screen.

### `class DnssecStatusView`

Linia: `14`

Brak docstringa.

**Metody:**

- `build` — linia 24; brak docstringa.
- `_operation_for_stage` — linia 120; brak docstringa.
- `_operation_label` — linia 132; brak docstringa.
- `_kasp_ds_state` — linia 142; brak docstringa.
- `_yes_no` — linia 150; brak docstringa.

## `src/zonectl/ui/form_style.py`

Brak docstringa.

### `def active_field_attr`

Linia: `9`

Return a high-contrast attribute, with a monochrome fallback.

### `def field_marker`

Linia: `19`

Brak docstringa.

## `src/zonectl/ui/function_keys.py`

Brak docstringa.

### `def decode_function_key`

Linia: `41`

Rozpoznaj sekwencję funkcyjną xterm lub PuTTY/Linux.

## `src/zonectl/ui/records/__init__.py`

Widoki i komponenty obsługi rekordów DNS.

Brak klas i funkcji na poziomie modułu.

## `src/zonectl/ui/records/controller.py`

Stan, sortowanie i filtrowanie widoku rekordów DNS.

### `def natural_name_key`

Linia: `11`

Sortuj cyfry według wartości, a tekst bez rozróżniania liter.

### `class RecordController`

Linia: `23`

Zarządza prezentacją rekordów bez zależności od curses.

**Metody:**

- `__init__` — linia 32; brak docstringa.
- `sort_name` — linia 46; brak docstringa.
- `cycle_sort` — linia 49; brak docstringa.
- `set_search` — linia 57; brak docstringa.
- `clear_search` — linia 62; brak docstringa.
- `_name_key` — linia 67; brak docstringa.
- `_type_key` — linia 80; brak docstringa.
- `_ttl_key` — linia 93; brak docstringa.
- `ordered_views` — linia 107; brak docstringa.
- `clamp_selection` — linia 153; brak docstringa.
- `move` — linia 180; brak docstringa.
- `current` — linia 194; brak docstringa.
- `select_identifier` — linia 206; brak docstringa.

## `src/zonectl/ui/records/editor.py`

Formularz edycji rekordów DNS w interfejsie curses.

### `class RecordEditor`

Linia: `19`

Obsługuje formularz edycji pojedynczego rekordu DNS.

**Metody:**

- `__init__` — linia 22; brak docstringa.
- `_owner_from_form` — linia 27; zachowaj źródłową postać właściciela, jeśli jej nie zmieniono.
- `_get_key` — linia 48; odczytuje klawisz i rozpoznaje f2 wysyłane jako esc [ 12 ~.
- `_edit_line` — linia 89; prosty edytor pojedynczej linii dla formularzy curses.
- `create_record_dialog` — linia 211; tworzy nowy rekord, wykorzystując formularz edycji.
- `edit_record_dialog` — linia 232; edytuje rekord w pamięci. zwraca nowy rekord albo none.

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

Linia: `22`

Tworzy rekord DNS bez modyfikowania pliku strefy.

**Metody:**

- `__init__` — linia 30; brak docstringa.
- `default_ttl` — linia 37; pobiera ttl z głównego rekordu soa strefy.
- `absolute_owner` — linia 67; brak docstringa.
- `validate_hostname` — linia 83; brak docstringa.
- `validate_rdata` — linia 107; brak docstringa.
- `build_record` — linia 214; brak docstringa.
- `_put` — linia 264; brak docstringa.
- `_type_window` — linia 296; brak docstringa.
- `create_record_dialog` — linia 307; brak docstringa.

## `src/zonectl/ui/records/renderer.py`

Brak docstringa.

### `class RecordRenderer`

Linia: `10`

Renderuje ekran rekordów DNS bez obsługi klawiatury.

**Metody:**

- `panel_enabled` — linia 17; brak docstringa.
- `details_height` — linia 21; brak docstringa.
- `visible_rows` — linia 30; brak docstringa.
- `summary_text` — linia 42; brak docstringa.
- `footer_text` — linia 66; brak docstringa.
- `_put` — linia 70; brak docstringa.
- `_change_attr` — linia 99; brak docstringa.
- `_draw_footer` — linia 112; brak docstringa.
- `_draw_details_panel` — linia 143; brak docstringa.
- `draw` — linia 184; brak docstringa.

## `src/zonectl/ui/rpz_status_view.py`

Model prezentacyjny panelu stanu integracji RPZ.

### `class RpzStatusView`

Linia: `11`

Gotowe do renderowania, niezależne od curses dane stanu RPZ.

**Metody:**

- `build` — linia 20; brak docstringa.
- `_age` — linia 58; brak docstringa.

## `src/zonectl/ui/zone_create_dialog.py`

Brak docstringa.

### `class ZoneCreateForm`

Linia: `11`

Brak docstringa.

### `class ZoneCreateDialog`

Linia: `21`

Pełnoekranowy formularz parametrów nowej strefy DNS.

**Metody:**

- `_get_key` — linia 35; brak docstringa.
- `_put` — linia 60; brak docstringa.
- `_edit_line` — linia 69; brak docstringa.
- `collect` — linia 121; brak docstringa.

## `src/zonectl/ui/zone_details_view.py`

Model prezentacyjny stałego panelu szczegółów strefy.

### `class ZoneDetailsView`

Linia: `11`

Zwięzłe szczegóły aktywnej strefy do prawego panelu TUI.

**Metody:**

- `build` — linia 20; brak docstringa.
- `_age` — linia 66; brak docstringa.
- `_yes_no` — linia 73; brak docstringa.
- `_dnssec` — linia 79; brak docstringa.
- `_secondary` — linia 85; brak docstringa.
