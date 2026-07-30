# ZoneCTL

> **Transactional DNS Management Toolkit**

ZoneCTL jest terminalowym narzędziem do bezpiecznego zarządzania strefami DNS serwera BIND9.

## Wersja

**4.2.0 — Safe editing and transaction history**

## Uruchomienie

```bash
zctl --version
zctl tui
zctl domains
zctl domains --grouped
```

Stare polecenie `elkman-dns` pozostaje chwilowo dostępne i wyświetla ostrzeżenie.

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

## Transakcje

```bash
zctl tx check um.elk.pl
zctl tx apply um.elk.pl --source /root/um.elk.pl.new
zctl tx apply um.elk.pl --source /root/um.elk.pl.new --commit
zctl tx backups um.elk.pl
zctl tx history um.elk.pl
```

## Bulk Operations

```text
SELECT type=A AND ttl=3600
SET ttl=7200

SELECT type=A AND value=192.0.2.10
SET value=192.0.2.20

SELECT type=TXT AND name~="^_old"
DELETE
```

## Testy

```bash
pytest -q
```
