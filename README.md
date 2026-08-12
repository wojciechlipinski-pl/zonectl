# ZoneCTL

> **Transactional DNS Management Toolkit**

ZoneCTL jest terminalowym narzędziem do bezpiecznego zarządzania strefami DNS serwera BIND9.

## Wersja

**4.6.0 — transactional DNSSEC lifecycle management**

## Uruchomienie

```bash
zctl --version
zctl tui
zctl domains
zctl domains --grouped
```

Pakiet systemowy instaluje wyłącznie polecenie `zctl`. Historyczna nazwa
`elkman-dns` nie jest już udostępniana jako systemowy entry point.

## Cykl życia stref

ZoneCTL potrafi transakcyjnie tworzyć i aktywować strefy, odwracalnie je
wyłączać, przywracać oraz przenosić do chronionej kwarantanny. Polecenia bez
`--commit` wykonują wyłącznie dry-run:

```bash
zctl zone create --help
zctl zone disable --help
zctl zone restore --help
zctl zone quarantine --help
zctl zone quarantine-restore --help
zctl zone inventory
zctl zone safety
```

W głównym ekranie TUI klawisz `n` uruchamia kreator nowej strefy. Kreator
zbiera parametry, pokazuje plan i wymaga jawnego potwierdzenia utworzenia
oraz aktywacji strefy.

Formularze stref i rekordów wyróżniają aktywne pole znacznikiem `▶`,
kontrastowym tłem całego wiersza oraz podpisem bieżącego pola.

Operacje cyklu życia są blokowane dla automatycznych stref RPZ oraz stref,
w których BIND wykrył `dnssec-policy` lub `inline-signing`.

## Raport DNSSEC

Wersja 4.6 udostępnia raportowanie oraz transakcyjne zarządzanie cyklem życia
DNSSEC:

```bash
zctl dnssec report example.pl
zctl dnssec report example.pl --json
zctl dnssec enable-plan example.pl
zctl dnssec enable example.pl
zctl dnssec disable-plan example.pl
zctl dnssec withdrawal-backup example.pl
zctl dnssec withdrawal-check example.pl
zctl dnssec withdrawal-confirm example.pl
zctl dnssec disable-apply example.pl --stage insecure
zctl dnssec prepare-finalize-serial example.pl
zctl dnssec disable-apply example.pl --stage finalize
```

Raport pokazuje konfigurację `dnssec-policy` i `inline-signing`, stan KASP
z `rndc`, pliki kluczy, lokalne DNSKEY i RRSIG, DS obliczony z DNSKEY metodą
SHA-256 oraz DS widoczny przez publiczny resolver. Polecenie nie modyfikuje
konfiguracji BIND, plików stref ani materiału kluczowego.

`enable-plan` pokazuje kandydacki unified diff deklaracji strefy oraz pełną
listę przyszłych kroków transakcji. Nie zapisuje konfiguracji, nie tworzy
kluczy i nie wykonuje `rndc reconfig`.

`enable` również domyślnie wykonuje wyłącznie dry-run. Właściwa operacja jest
dostępna dopiero po podaniu obu flag `--commit --activate`; pojedyncza flaga
jest odrzucana jako niepełne potwierdzenie.

`disable-plan` wyłącznie inwentaryzuje konfigurację, klucze i artefakty
podpisywania oraz pokazuje bezpieczną kolejność wycofania DNSSEC. Nie usuwa DS,
nie zmienia KASP ani BIND.

`withdrawal-backup` tworzy po jawnym `--commit` zweryfikowany pakiet
odtworzeniowy wymagany przed usunięciem DS u rejestratora.

`withdrawal-check` jest wyłącznie odczytowe i sprawdza, czy DS zniknął już
z odpowiedzi wszystkich kontrolowanych resolverów. Status `BLOCKED` oznacza,
że co najmniej jeden resolver nadal zwraca DS i `rndc dnssec -checkds
withdrawn` nie wolno jeszcze wykonać. Dopiero `READY_FOR_WITHDRAWN` pozwala
rozważyć ten krok.

`withdrawal-confirm` jest jedynym miejscem w ZoneCTL, które wykonuje `rndc
dnssec -checkds withdrawn`. Bez `--commit` pozostaje dry-runem. Właściwa
operacja wymaga jednocześnie `--commit` i `--acknowledge-withdrawn` oraz
ponownie uruchamia pełną kontrolę DS bezpośrednio przed wykonaniem `rndc`;
jeśli świeży wynik nie jest `READY_FOR_WITHDRAWN`, komenda kończy się
statusem `BLOCKED` i niczego nie zmienia. Sukces zapisuje manifest z
identyfikatorem transakcji i kontrolą DS, która go autoryzowała.

`disable-apply` domyka procedurę w dwóch etapach, zgodnie z wymaganiem
BIND, by strefę przeprowadzić przez wbudowaną politykę `insecure`, a nie
usuwać `dnssec-policy` od razu. Etap `insecure` podmienia politykę i jest
bramkowany zniknięciem DS z resolverów; etap `finalize` usuwa
`dnssec-policy`, `inline-signing` i `key-directory`, i jest bramkowany
potwierdzeniem z KASP, że wszystkie klucze są w stanie `hidden`. Kluczy
ani pakietu odtworzeniowego żaden z etapów nie usuwa.

## Filtrowanie rekordów

W widoku rekordów naciśnij `/`. Zwykły tekst nadal przeszukuje wszystkie
widoczne pola. Filtry pól można łączyć spacjami (AND):

```text
type:A ttl>=3600
name:www -value:192.0.2.10
name~"^_acme" type:TXT
status:modified
ttl:-
```

Obsługiwane pola to `name`, `type`, `ttl`, `value` i `status`. Operator
`~` oznacza wyrażenie regularne, początkowy `-` neguje warunek, a wartość
w cudzysłowie może zawierać spacje. Status przyjmuje wartości `added`,
`modified`, `deleted` i `unchanged`.

## Walidacja rekordów

Formularze dodawania i edycji sprawdzają składnię RDATA zależnie od typu
rekordu, między innymi adresy IPv4/IPv6 oraz strukturę rekordów `MX`,
`SRV`, `CAA`, `DS`, `DNSKEY`, `SSHFP`, `TLSA`, `SOA`, `NAPTR`,
`SVCB/HTTPS` i `TXT`.

Przed dodaniem zmiany sprawdzana jest również spójność całej strefy:
obecność `SOA` i `NS` w apexie, konflikty i pętle `CNAME`, duplikaty,
lokalne cele rekordów oraz glue dla serwerów nazw. Nowe błędy blokują
zmianę, natomiast nowe ostrzeżenia wymagają świadomego potwierdzenia.
Kandydat nadal przechodzi przez `named-checkzone` przed COMMIT.

## Transakcje

```bash
zctl tx check um.elk.pl
zctl tx apply um.elk.pl --source /root/um.elk.pl.new
zctl tx apply um.elk.pl --source /root/um.elk.pl.new --commit
zctl tx backups um.elk.pl
zctl tx history um.elk.pl
```

## Bulk Operations

W widoku rekordów naciśnij `b`, wpisz pojedyncze polecenie i sprawdź
podgląd dopasowań przed potwierdzeniem:

```text
SELECT type:A ttl:3600 SET ttl=7200
SELECT type:A value:192.0.2.10 SET value=192.0.2.20
SELECT type:TXT name~"^_old" DELETE
```

Operacje obsługują filtry opisane wyżej. `SET` zmienia obecnie `ttl` lub
`value`. Wynik trafia wyłącznie do bufora sesji, przechodzi walidację
strefy i wymaga późniejszego, osobnego COMMIT. Jedno `u` cofa całą
operację masową.

## Sesja wielu stref

Na głównej liście zaznacz co najmniej dwie strefy klawiszem `Spacja`,
a następnie naciśnij `m`. `Enter` otwiera edycję wskazanej strefy bez
zamykania pozostałych sesji. Powrót zachowuje jej robocze zmiany.

Klawisz `F2` w widoku wielostrefowym najpierw waliduje wszystkie
zmienione strefy. Dopiero poprawna walidacja całego zestawu rozpoczyna
osobne, bezpieczne transakcje. Błąd zatrzymuje dalsze zapisy.

## Plan utworzenia strefy

Wersja rozwojowa 4.4 udostępnia pozbawiony skutków ubocznych plan:

```bash
zctl zone create-plan example.pl \
  --primary-ns ns1.elkman.pl. \
  --admin hostmaster.elkman.pl. \
  --ns ns1.elkman.pl. \
  --ns ns2.elkman.pl. \
  --ipv4 192.0.2.10 \
  --www
```

Polecenie jedynie prezentuje kandydat pliku strefy, deklarację BIND oraz
planowane etapy. Nie tworzy plików i nie wykonuje `rndc reconfig`.
Docelowo każda strefa otrzymuje osobny plik
`/etc/bind/zonectl-zones.d/NAZWA.conf`, a indeks
`/etc/bind/zonectl-zones.conf` zawiera wyłącznie dyrektywy `include`.

Istniejące deklaracje można najpierw bezpiecznie zinwentaryzować i obejrzeć
plan migracji pojedynczej strefy. Oba polecenia są wyłącznie odczytowe:

```bash
zctl zone migration-inventory
zctl zone migration-plan example.pl
zctl zone migration-apply example.pl
```

Plan zachowuje pełny blok strefy, pokazuje diff trzech plików i blokuje RPZ,
strefy secondary oraz strefy używające DNSSEC. Nie zapisuje plików i nie
wywołuje `rndc`.

Właściwa migracja wymaga jednocześnie `--commit`, `--activate` oraz dokładnego
potwierdzenia nazwy strefy:

```bash
zctl zone migration-apply example.pl \
  --commit --activate --confirm example.pl
```

W TUI otwórz szczegóły strefy i użyj `F6`, następnie `F3` dla planu albo
`F4` dla dry-runu i kontrolowanej migracji.

Odczytowa inwentaryzacja globalnych ACL i grup secondary:

```bash
zctl bind inventory
zctl bind inventory --json
zctl bind audit
zctl bind secondary-report
zctl bind secondary-plan dns2-notify --address 5.172.189.198
zctl bind secondary-apply dns2-notify --address 5.172.189.198

W TUI klawisz `F9` otwiera listę ACL i grup secondary. `F3` pokazuje wpływ
wybranej definicji, a `F4` prowadzi przez plan, dry-run i transakcyjną zmianę
grupy secondary.
Edytory ACL i secondary używają tych samych klawiszy co rekordy: `Insert`,
`F4`, `F8/Delete` oraz `F2` do przejścia do planu i dry-runu.
W szczegółach strefy `F5` zarządza przypisaniem do logicznych par secondary.
zctl bind acl-plan trusted \
  --replace 192.168.200/24=192.168.200.0/24
zctl bind acl-plan trusted --entry localhost --entry 192.168.200.0/24
zctl bind acl-apply trusted \
  --replace 192.168.200/24=192.168.200.0/24
```

## Testy

```bash
pytest -q
```
