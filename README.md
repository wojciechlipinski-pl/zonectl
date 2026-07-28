# elkman DNS Toolkit 3.1.0 — Sprint 2: Transaction Layer

Ta wersja dodaje bezpieczną warstwę transakcyjną dla plików stref BIND.

## Zasada działania

`tx apply` wykonuje kolejno:

1. blokadę strefy,
2. kontrolę pliku źródłowego,
3. `named-checkzone`,
4. `named-checkconf -z`,
5. dry-run (domyślnie) albo backup,
6. atomową podmianę pliku z zachowaniem praw i właściciela,
7. ponowną walidację,
8. `rndc reload <strefa>`,
9. sprawdzenie SOA,
10. automatyczny rollback przy błędzie,
11. zapis manifestu i audytu JSONL.

## Instalacja

```bash
sudo ./install.sh
hash -r
elkman-dns --version
```

## Bezpieczny test

```bash
elkman-dns tx check um.elk.pl
elkman-dns tx apply um.elk.pl --source /root/um.elk.pl.new
```

Drugie polecenie jest tylko dry-run. Nie zmienia aktywnej strefy.

## Commit

```bash
elkman-dns tx apply um.elk.pl --source /root/um.elk.pl.new --commit
```

## Backupy i historia

```bash
elkman-dns tx backups um.elk.pl
elkman-dns tx history um.elk.pl
elkman-dns tx history --json
```

## Ręczny rollback

Najpierw dry-run:

```bash
elkman-dns tx rollback um.elk.pl --backup /var/lib/elkman-dns-toolkit/backups/um.elk.pl/PLIK
```

Następnie świadomy commit:

```bash
elkman-dns tx rollback um.elk.pl --backup /var/lib/elkman-dns-toolkit/backups/um.elk.pl/PLIK --commit
```

## Pliki

- backupy: `/var/lib/elkman-dns-toolkit/backups/`
- manifesty: `/var/lib/elkman-dns-toolkit/transactions/`
- blokady: `/var/lib/elkman-dns-toolkit/locks/`
- audyt: `/var/log/elkman-dns-toolkit/audit.jsonl`

## Ważne

- `apply` bez `--commit` nigdy nie zmienia pliku.
- Strefa musi istnieć w `/etc/elkman-dns-toolkit/zones.conf`.
- Dla stref inline-signing wskazuj plik źródłowy używany przez BIND, np. w `/var/lib/bind/Primary`.
- Narzędzie nie edytuje automatycznie seriala; kandydat musi zawierać właściwy serial.
