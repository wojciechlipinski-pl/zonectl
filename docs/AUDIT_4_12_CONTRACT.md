# Kontrakt audytu ZoneCTL 4.12

Ten dokument zamyka odczytowy audyt istniejących mechanizmów historii i
definiuje kontrakt danych dla wspólnego rejestru audytowego ZoneCTL 4.12.
Nie zmienia zachowania programu ani formatu istniejących manifestów.

## Stan obecny

ZoneCTL przechowuje obecnie dwa główne rodzaje informacji:

1. silnik transakcji plików stref zapisuje manifest JSON oraz zdarzenia JSONL;
2. wyspecjalizowane transakcje BIND, DNSSEC, RPZ i cyklu życia stref zapisują
   własne manifesty w osobnych katalogach.

Silnik stref udostępnia już `zctl tx history`, `zctl tx show` i surowe
`zctl tx history --events`. Historia manifestów filtruje po strefie i limicie,
a błędne pliki pomija. Widok pojedynczej transakcji odrzuca niebezpieczne
identyfikatory oraz jawnie zgłasza brak lub uszkodzenie manifestu.

### Mocne strony

- identyfikatory transakcji łączą wynik, backup i manifest;
- podstawowy dziennik JSONL jest dopisywany z `fsync` i trybem pliku `0640`;
- manifesty zawierają kroki walidacji, commit oraz wynik rollbacku;
- ACL i secondary korzystają z jawnej listy pól oraz rekurencyjnej redakcji;
- istnieją testy historii, uszkodzonych manifestów, bezpiecznych
  identyfikatorów i prywatności manifestów BIND;
- CLI potrafi zwrócić historię i wynik transakcji jako JSON.

### Luki wymagające ujednolicenia

| Obszar | Stan obecny | Wymaganie 4.12 |
|---|---|---|
| Schemat | brak `schema_version`; różne pola rodzin transakcji | wersjonowana wspólna koperta |
| Statusy | m.in. `COMMIT`, `COMMITTED`, `FAIL`, `FAILED`, `ROLLED-BACK`, `ROLLBACK-FAILED`, `DRY-RUN` | kanoniczny słownik i mapowanie wartości historycznych |
| Zakres | część operacji trafia do centralnej historii, pozostałe tylko do własnych katalogów | wspólny indeks wszystkich wspieranych operacji |
| Czas | `saved_at`, czas zdarzenia albo awaryjnie mtime pliku | UTC, początek, koniec i opcjonalny czas trwania |
| Prywatność | jawna redakcja tylko w części manifestów; bazowe kroki mogą zawierać stdout/stderr i polecenia | jedna allowlista i wspólny sanitizer przed zapisem |
| Zapis | JSONL używa append + `fsync`; część manifestów używa bezpośredniego `write_text` | blokada, zapis atomowy, `fsync`, stałe tryby i ochrona przed symlinkami |
| Błędy danych | historia pomija uszkodzone wpisy bez diagnostyki | licznik ostrzeżeń i bezpieczna kwarantanna, bez blokowania odczytu zdrowych wpisów |
| Filtry | strefa i limit | czas, operacja, zasób, status i identyfikator |
| Retencja | brak wspólnej polityki | jawna retencja rekordów niezależna od retencji backupów |
| TUI | brak wspólnej przeglądarki | odczytowa lista i szczegóły na małych terminalach |

## Decyzja architektoniczna

Wspólny rejestr jest indeksem operacyjnym, a nie zamiennikiem istniejących
manifestów i backupów. Każda operacja zapisuje małą, znormalizowaną kopertę
JSONL. Koperta może wskazywać manifest i backup przez bezpieczne referencje,
ale nie kopiuje ich pełnej treści.

Istniejące manifesty pozostają źródłem szczegółów i materiałem do odtworzenia.
Adaptery poszczególnych rodzin transakcji mapują ich wyniki do wspólnego
kontraktu. Migracja starych manifestów nie jest wymagana do rozpoczęcia 4.12;
odczyt historyczny może mapować je w locie.

## Koperta `zonectl.audit/v1`

Każdy wiersz rejestru jest pojedynczym obiektem JSON zakodowanym w UTF-8.
Klucze są zapisywane w stabilnej kolejności, a wiersz kończy się `LF`.

### Pola wymagane

| Pole | Typ | Znaczenie |
|---|---|---|
| `schema` | string | stała `zonectl.audit/v1` |
| `record_id` | string | losowy UUID rekordu |
| `transaction_id` | string | istniejący bezpieczny identyfikator transakcji |
| `recorded_at` | string | RFC 3339 w UTC z końcówką `Z` |
| `record_kind` | string | `START` albo `RESULT` |
| `operation` | string | kanoniczny typ operacji |
| `resource` | object | typ i znormalizowana nazwa zasobu |
| `outcome` | string | kanoniczny wynik |
| `committed` | boolean | czy wykonano zmianę materialną |
| `rollback` | object | informacja o próbie i wyniku rollbacku |

### Pola opcjonalne

| Pole | Typ | Reguła |
|---|---|---|
| `started_at` | string | RFC 3339 UTC; wymagane dla `RESULT`, jeśli istnieje rekord startowy |
| `duration_ms` | integer | nieujemny czas monotoniczny |
| `actor` | object | `uid` i opcjonalna jawna etykieta operatora; bez automatycznej nazwy hosta |
| `risk` | string | `LOW`, `MEDIUM`, `HIGH` albo `CRITICAL` |
| `reason` | string | krótka przyczyna podana przez operatora, po sanityzacji |
| `summary` | object | wyłącznie zagregowane liczniki i nazwy bramek |
| `manifest_ref` | string | ścieżka względna względem skonfigurowanego katalogu manifestów |
| `backup_ref` | string | ścieżka względna względem skonfigurowanego katalogu backupów |
| `compat` | object | źródłowa rodzina i status użyte podczas odczytu starszego manifestu |

Nieznane pola czytnik ignoruje. Brak pola wymaganego powoduje odrzucenie
rekordu i zwiększenie licznika diagnostycznego, ale nie przerywa odczytu
pozostałej historii.

## Słowniki kanoniczne

### `record_kind`

- `START` — operacja została przyjęta i otrzymała identyfikator;
- `RESULT` — operacja osiągnęła stan końcowy.

Para rekordów pozwala wykryć transakcje przerwane przez awarię procesu lub
hosta. Czytnik może prezentować samotny `START` jako `INTERRUPTED`, ale nie
zapisuje takiego wyniku bez dowodu zakończenia.

### `outcome`

- `STARTED`
- `PASS`
- `NO_CHANGE`
- `DRY_RUN`
- `COMMITTED`
- `ROLLED_BACK`
- `ROLLBACK_FAILED`
- `BLOCKED`
- `READ_ONLY`
- `FAILED`

Wartości historyczne są mapowane podczas odczytu, na przykład `COMMIT` do
`COMMITTED`, `ROLLED-BACK` do `ROLLED_BACK`, a `FAIL` do `FAILED`.

### `operation`

Nazwa jest stabilnym identyfikatorem w formacie `obszar.czasownik`, np.:

- `zone.records.apply`
- `zone.create`
- `zone.disable`
- `zone.restore`
- `zone.quarantine`
- `zone.quarantine_restore`
- `zone.quarantine_purge`
- `bind.acl.apply`
- `bind.secondary.apply`
- `dnssec.enable`
- `dnssec.confirm_ds`
- `dnssec.disable`
- `rpz.install`
- `rpz.migrate`

Nowa wartość wymaga testu kontraktu i dokumentacji, ale nie nowej wersji
schematu. Zmiana znaczenia istniejącej wartości wymaga nowej wersji schematu.

### `resource`

```json
{
  "kind": "zone",
  "name": "example.test"
}
```

Dozwolone `kind` w v1 to `zone`, `acl`, `secondary_group`, `rpz` i
`bind_environment`. Nazwa jest logicznym identyfikatorem zasobu, nie ścieżką
pliku. Dla operacji obejmującej wiele stref `name` zawiera nazwę logicznego
planu, a `summary.resource_count` liczbę zasobów.

### `rollback`

```json
{
  "attempted": true,
  "outcome": "PASS"
}
```

Jeśli rollbacku nie próbowano, `attempted` ma wartość `false`, a `outcome`
jest `null`.

## Przykład rekordu końcowego

```json
{
  "schema": "zonectl.audit/v1",
  "record_id": "8bd934ca-48f5-4c18-a399-814c842cc187",
  "transaction_id": "20260901-120000-example.test-a1b2c3d4",
  "recorded_at": "2026-09-01T10:00:02Z",
  "record_kind": "RESULT",
  "operation": "zone.records.apply",
  "resource": {
    "kind": "zone",
    "name": "example.test"
  },
  "outcome": "COMMITTED",
  "committed": true,
  "rollback": {
    "attempted": false,
    "outcome": null
  },
  "started_at": "2026-09-01T10:00:00Z",
  "duration_ms": 1840,
  "actor": {
    "uid": 0,
    "label": "operator"
  },
  "risk": "MEDIUM",
  "summary": {
    "changed_file_count": 1,
    "changed_record_count": 2,
    "validation_gates": [
      "named-checkzone",
      "named-checkconf",
      "rndc-reload",
      "verify-soa"
    ]
  },
  "manifest_ref": "transactions/20260901-120000-example.test-a1b2c3d4.json",
  "backup_ref": "backups/example.test/20260901-120000-example.test-a1b2c3d4-zone.db"
}
```

Wartości przykładowe są syntetyczne i używają domeny zarezerwowanej do
dokumentacji.

## Reguły prywatności

Rejestr v1 stosuje allowlistę pól przed serializacją. Zabronione są:

- sekrety, hasła, tokeny i prywatne klucze;
- materiał kluczy DNSSEC oraz pełne odpowiedzi zawierające taki materiał;
- surowe `stdout`, `stderr` i pełne linie poleceń;
- zawartość plików stref, konfiguracji i backupów;
- bezwzględne ścieżki produkcyjne;
- automatycznie wykryta nazwa hosta, adresy interfejsów i dane sesji;
- nieograniczony słownik `details` lub `metadata` pochodzący od wywołującego.

Dozwolone są nazwa zarządzanego zasobu, jawna etykieta operatora, nazwy
bramek walidacyjnych, zagregowane liczniki, statusy i względne referencje do
manifestu oraz backupu. Wartości tekstowe przechodzą wspólną redakcję, limit
długości i kontrolę znaków sterujących.

## Zapis i integralność

- katalog rejestru: `0750`; plik: `0640`;
- odmowa zapisu przez symlink lub do pliku niebędącego zwykłym plikiem;
- blokada międzyprocesowa podczas dopisywania;
- pojedynczy rekord serializowany przed otwarciem pliku;
- jeden append, następnie `flush` i `fsync`;
- limit rozmiaru rekordu przed zapisem;
- błąd zapisu audytu nie może zostać uznany za udany audit; polityka dla
  operacji modyfikujących BIND zostanie jawnie ustalona w implementacji;
- rotacja nie usuwa manifestów ani backupów i nie może przeciąć rekordu JSONL.

## Odczyt i zgodność

Czytnik v1:

1. nie wykonuje ścieżek ani poleceń zapisanych w danych;
2. nakłada limit rozmiaru pliku, wiersza i liczby wyników;
3. raportuje liczbę pominiętych wpisów oraz ich bezpieczne przyczyny;
4. filtruje po czasie, operacji, rodzaju zasobu, nazwie zasobu, wyniku i
   identyfikatorze transakcji;
5. stabilnie sortuje po `recorded_at`, a przy remisie po `record_id`;
6. potrafi mapować istniejące manifesty na kopertę v1 bez ich modyfikowania.

## Retencja

Retencja audytu jest niezależna od backupów i manifestów. Domyślnie niczego
nie usuwa automatycznie w pierwszej implementacji. Późniejszy purge wymaga
dry-runu, limitu wieku i liczby rekordów, blokady usunięcia najnowszego wyniku
dla zasobu oraz własnego rekordu audytowego. Automatyczna RPZ nie generuje
rekordu dla każdego okresowego odświeżenia; rejestrowane są operacje
instalacji, migracji, błędy i zmiany stanu zarządzania.

## Kryteria gotowości implementacji

- dataclasses/enums v1 nie zależą od curses ani CLI;
- serializer odrzuca pola spoza allowlisty i materiał wrażliwy;
- zapis i odczyt mają testy awarii, uprawnień, symlinków i uszkodzonych linii;
- adaptery obejmują każdą rodzinę transakcji przed podłączeniem TUI;
- istniejące `tx history` i `tx show` pozostają kompatybilne do czasu migracji;
- implementacja nie odczytuje produkcyjnych danych podczas testów.

## Kolejność dalszych prac

1. model, walidator i sanitizer koperty v1;
2. bezpieczny writer/reader oraz diagnostyka uszkodzonych wpisów;
3. adapter bazowego `TransactionEngine` — wykonany;
4. adaptery pozostałych rodzin transakcji — wykonane;
5. filtry i eksport CLI;
6. odczytowa przeglądarka TUI;
7. retencja oraz opcjonalna, lokalna historia Git — wykonane; Git jest
   domyślnie wyłączony, nie ma remote, wyklucza RPZ i nie zastępuje backupów.
