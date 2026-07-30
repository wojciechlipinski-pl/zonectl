# Migracje projektu ZoneCTL

Każda migracja:
- ma unikalny numer,
- sprawdza warunki wejściowe,
- tworzy kopie zmienianych plików,
- jest bezpieczna przy ponownym uruchomieniu,
- uruchamia testy,
- nie wykonuje automatycznie `git commit`.

## Migracja 001 — katalogi systemowe

Plan bez modyfikowania systemu:

```bash
python3 tools/migrations/m001_system_paths.py
```

Zastosowanie migracji:

```bash
python3 tools/migrations/m001_system_paths.py --apply
```

Stare katalogi pozostają na miejscu do czasu potwierdzenia poprawnego
wdrożenia nowej wersji. Manifest i pełna kopia danych są zapisywane w
`/var/backups/zonectl-migrations`.

Rollback usuwa wyłącznie katalogi utworzone przez migrację:

```bash
python3 tools/migrations/m001_system_paths.py \
  --rollback /var/backups/zonectl-migrations/.../manifest.json
```
