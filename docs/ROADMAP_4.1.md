# ZoneCTL 4.1 — Rebranding & Bulk Operations

## Tożsamość

- Projekt: **ZoneCTL**
- CLI: `zctl`
- Pakiet Python: `zonectl`
- Tagline: **Transactional DNS Management Toolkit**

## Zakres

### Rebranding
- nazwa produktu,
- komenda `zctl`,
- przestrzeń nazw Python,
- README i dokumentacja,
- generator dokumentacji,
- komunikaty TUI i `--version`,
- migracja istniejącej instalacji.

### Bulk Operations
Planowana składnia:

```text
SELECT type=A AND ttl=3600
SET ttl=7200

SELECT type=A AND value=192.0.2.10
SET value=192.0.2.20

SELECT type=TXT AND name~="^_old"
DELETE
```

Operacje masowe mają korzystać z istniejącego modelu zmian i jednej transakcji zapisu.
