# Instrukcja operacyjna

## Zasady bezpieczeństwa

- Polecenia zmieniające strefy wykonuj jako `root`.
- Przed zmianą sprawdź stan Git, testy i aktywną wersję ZoneCTL.
- Najpierw używaj trybu walidacji, a dopiero potem `--commit`.
- Nie usuwaj backupów transakcyjnych przed potwierdzeniem poprawnego SOA.
- Po każdej zmianie sprawdź stan BIND oraz dziennik audytowy ZoneCTL.

## Tryb tylko do odczytu

Na czas diagnostyki lub pracy operatora bez uprawnień do zmian można
włączyć globalną blokadę zapisu:

```ini
[toolkit]
read_only = yes
```

W tym trybie TUI pozwala przeglądać strefy, ich stan, oczekujące zmiany
i historię transakcji, ale ukrywa akcje dodawania, edycji, usuwania,
cofania oraz zapisu. Silnik transakcyjny niezależnie blokuje także
`apply --commit` i `rollback --commit`, zwracając status `READ-ONLY`.
Tryby walidacyjne bez `--commit` pozostają dostępne.

## Blokada równoległej edycji

Po otwarciu strefy do edycji ZoneCTL zakłada blokadę `flock` w katalogu
`/var/lib/zonectl/edit-locks`. Plik blokady zawiera nazwę strefy, PID,
użytkownika, host i czas rozpoczęcia sesji. Próba otwarcia tej samej
strefy do zapisu w drugim procesie kończy się czytelnym komunikatem
wskazującym właściciela blokady.

Blokada jest zwalniana przy normalnym wyjściu. Po awarii procesu blokada
jądra jest zwalniana automatycznie, a pozostały plik metadanych zostanie
bezpiecznie nadpisany przez następną sesję. Sesje uruchomione z
`read_only = yes` nie zakładają blokad edycyjnych i mogą działać
równolegle.

## Sesja wielu stref

Koordynator sesji wielostrefowej utrzymuje osobny model, blokadę edycji
i kandydat dla każdej otwartej strefy. Przed pierwszym zapisem wszystkie
zmienione strefy przechodzą walidację bez COMMIT. Dopiero poprawny wynik
całego zestawu pozwala rozpocząć kolejne, niezależne transakcje.

Każda strefa otrzymuje własny backup i manifest. Błąd zapisu zatrzymuje
dalsze transakcje, a wynik wskazuje strefy zapisane i niezapisane.
Mechanizm nie deklaruje atomowości pomiędzy różnymi strefami.

## Kontrola instalacji

```bash
zctl --version
readlink -f /opt/zonectl/current
zctl domains
```

Weryfikacja wskazanego wydania:

```bash
/opt/zonectl/current/venv/bin/python -c \
  'import zonectl; print(zonectl.__version__)'
/root/elkman-dns/scripts/verify.sh /opt/zonectl/current
```

## Kontrola strefy

W przykładach należy zastąpić `example.pl` właściwą nazwą strefy.

```bash
zctl tx verify example.pl
rndc zonestatus example.pl
dig @127.0.0.1 example.pl SOA +short
```

W odpowiedzi `dig` numer seryjny SOA jest zwykle trzecim polem po nazwie
serwera głównego i adresie administratora strefy.

## Historia i backupy

Lista ostatnich zdarzeń:

```bash
zctl tx history example.pl --limit 20
```

Domyślnie historia pokazuje po jednym podsumowaniu na manifest
transakcji: czas, strefę, wynik i identyfikator. Pełny wynik wybranej
transakcji można odtworzyć poleceniem:

```bash
zctl tx show IDENTYFIKATOR_TRANSAKCJI
```

Surowe zdarzenia dziennika audytowego pozostają dostępne przez:

```bash
zctl tx history example.pl --events --limit 20
```

Każde z poleceń historii obsługuje również format JSON przez `--json`.

### Operacje masowe w historii

Operacje `SELECT ... SET` i `SELECT ... DELETE` są zapisywane jako jedna
transakcja obejmująca cały kandydat strefy. Jeden manifest zawiera filtr,
rodzaj operacji i liczbę dopasowanych rekordów. Walidacja, instalacja
atomowa, przeładowanie BIND i ewentualny rollback dotyczą całego zestawu.
Nie jest możliwy częściowy COMMIT wybranych rekordów.

Szczegóły operacji są widoczne przez:

```bash
zctl tx show IDENTYFIKATOR_TRANSAKCJI
zctl tx show IDENTYFIKATOR_TRANSAKCJI --json
```

Lista backupów, od najnowszego:

```bash
zctl tx backups example.pl --limit 20
```

Każdy backup ma obok plik metadanych `.json`, zawierający między innymi
sumę SHA-256, właściciela, prawa dostępu, źródło i identyfikator transakcji.

## Automatyczny rollback

Podczas COMMIT ZoneCTL:

1. waliduje kandydata przez `named-checkzone`,
2. sprawdza aktywną konfigurację przez `named-checkconf -z`,
3. tworzy backup aktywnego pliku,
4. atomowo instaluje nowy plik,
5. ponownie wykonuje walidację,
6. wywołuje `rndc reload`,
7. porównuje oczekiwany i załadowany serial SOA.

Jeżeli krok po instalacji nie powiedzie się, ZoneCTL przywraca backup
atomowo i ponownie wywołuje `rndc reload`.

Status `ROLLED-BACK` oznacza, że plik został przywrócony i ponowne
przeładowanie zakończyło się powodzeniem. Status `ROLLBACK-FAILED`
oznacza, że pełne przywrócenie nie zostało potwierdzone i wymaga
interwencji operatora.

## Ręczny rollback

### 1. Zatrzymaj dalsze zmiany

Nie wykonuj kolejnego COMMIT dla tej strefy, dopóki jej stan nie zostanie
ustalony.

### 2. Zbierz stan i historię

```bash
zctl tx verify example.pl
zctl tx history example.pl --limit 20
zctl tx backups example.pl --limit 20
rndc zonestatus example.pl
dig @127.0.0.1 example.pl SOA +short
journalctl -u bind9 --since "-15 minutes"
```

Na systemach używających innej nazwy usługi zastąp `bind9` przez `named`.

### 3. Wybierz backup

Skopiuj pełną ścieżkę z wyniku:

```bash
zctl tx backups example.pl --limit 20
```

Przykład:

```text
/var/lib/zonectl/backups/example.pl/TRANSACTION-example.pl
```

Nie wybieraj pliku kończącego się na `.json`.

### 4. Wykonaj walidację bez zmian

```bash
zctl tx rollback example.pl \
  --backup /pełna/ścieżka/do/backupu
```

Oczekiwany status to `DRY-RUN`, a krok `named-checkzone` powinien mieć
wynik `OK`. Jeśli walidacja nie przechodzi, nie używaj `--commit`.

### 5. Przywróć backup

```bash
zctl tx rollback example.pl \
  --backup /pełna/ścieżka/do/backupu \
  --commit
```

Oczekiwany status to `ROLLBACK-COMMIT`.

Przed przywróceniem ZoneCTL automatycznie tworzy dodatkowy backup
aktualnego pliku z oznaczeniem `pre-rollback`. Umożliwia to powrót do
stanu sprzed ręcznej operacji.

### 6. Potwierdź wynik

```bash
zctl tx verify example.pl
rndc zonestatus example.pl
dig @127.0.0.1 example.pl SOA +short
named-checkzone example.pl /ścieżka/do/aktywnego/pliku.strefy
zctl tx history example.pl --limit 20
```

Nie uznawaj operacji za zakończoną, dopóki:

- `zctl tx verify` nie zakończy się poprawnie,
- serial załadowany przez BIND nie odpowiada aktywnemu plikowi,
- `named-checkzone` nie zwraca błędu,
- log BIND nie pokazuje błędu ładowania strefy.

### 7. Gdy reload po rollbacku nadal się nie powiedzie

Jeśli otrzymasz status `FAIL`:

1. nie wykonuj kolejnych zmian pliku,
2. sprawdź `journalctl -u bind9`,
3. uruchom `named-checkconf -z`,
4. uruchom `named-checkzone` dla aktywnego pliku,
5. sprawdź prawa, właściciela i kontekst bezpieczeństwa pliku,
6. zachowaj wynik `zctl tx history` oraz ścieżki obu backupów,
7. po usunięciu przyczyny wykonaj `rndc reload example.pl`,
8. ponownie wykonaj pełną weryfikację z kroku 6.

Jeżeli trzeba powrócić do pliku sprzed ręcznego rollbacku, użyj backupu
`pre-rollback`, najpierw bez `--commit`, a następnie z `--commit`.

## Diagnostyka BIND

```bash
journalctl -u bind9 --since "-15 minutes"
rndc status
rndc zonestatus example.pl
named-checkconf -z
named-checkzone example.pl /ścieżka/do/pliku.strefy
```

Nazwy usługi mogą różnić się zależnie od systemu, np. `bind9` lub `named`.

## Wdrożenie nowego wydania

Przed wdrożeniem:

```bash
cd /root/elkman-dns
git status --short --branch
git log -1 --oneline
.venv/bin/python -m pytest -q
```

Skrypt wdrożeniowy:

```bash
./scripts/deploy.sh /root/elkman-dns
```

Po wdrożeniu sprawdź:

```bash
zctl --version
readlink -f /opt/zonectl/current
readlink -f /opt/zonectl/previous
zctl domains
```
