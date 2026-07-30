# ZoneCTL

> **Transactional DNS Management Toolkit**

ZoneCTL jest terminalowym narzędziem do bezpiecznego zarządzania strefami DNS serwera BIND9.

## Wersja

**4.1.1 — Rebranding & RPZ Health Profile**

## Uruchomienie

```bash
zctl --version
zctl tui
zctl domains
zctl domains --grouped
```

Stare polecenie `elkman-dns` pozostaje chwilowo dostępne i wyświetla ostrzeżenie.

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
