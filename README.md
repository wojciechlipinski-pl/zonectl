# ZoneCTL

> **Transactional DNS Management Toolkit**

ZoneCTL jest terminalowym narzędziem do bezpiecznego zarządzania strefami DNS serwera BIND9.

## Wersja

**4.4.0 — Transactional DNS zone lifecycle**

## Uruchomienie

```bash
zctl --version
zctl tui
zctl domains
zctl domains --grouped
```

Stare polecenie `elkman-dns` pozostaje chwilowo dostępne i wyświetla ostrzeżenie.

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

Operacje cyklu życia są blokowane dla automatycznych stref RPZ oraz stref,
w których BIND wykrył `dnssec-policy` lub `inline-signing`.

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

## Testy

```bash
pytest -q
```
