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

### Izolowany test tworzenia strefy

Test integracyjny `test_zone_create_bind_integration.py` uruchamia prawdziwe
`named-checkzone` i `named-checkconf`, ale wszystkie pliki zapisuje wyłącznie
w katalogu tymczasowym pytest. Nie wykonuje `rndc reconfig`, nie dołącza
pliku do aktywnego BIND i nie modyfikuje `/etc/bind`.

Konfiguracja zarządzana używa jednego pliku deklaracji na strefę w
`/etc/bind/zonectl-zones.d`. Plik `/etc/bind/zonectl-zones.conf` jest
wyłącznie indeksem zawierającym dyrektywy `include` tych deklaracji.

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

## Cykl życia stref DNS w ZoneCTL 4.4

Każda operacja modyfikująca system wymaga jawnego `--commit`. Bez tej opcji
polecenia wykonują dry-run. Strefy zarządzane przez ZoneCTL mają osobne
deklaracje w `/etc/bind/zonectl-zones.d`, dołączane przez indeks
`/etc/bind/zonectl-zones.conf`.

### Odczytowy plan migracji deklaracji 4.7

Przed przenoszeniem starszych deklaracji z `named.conf.local` należy wykonać
inwentaryzację i plan dla jednej wybranej strefy:

```bash
zctl zone migration-inventory
zctl zone migration-plan example.pl
```

Inwentaryzacja rozróżnia strefy już zarządzane, zwykłe primary, secondary,
RPZ, DNSSEC i deklaracje pochodzące z innych plików include. Plan pokazuje
usunięcie bloku z `named.conf.local`, utworzenie kompletnej deklaracji w
`zonectl-zones.d` i dopisanie pojedynczego include do `zonectl-zones.conf`.
Na tym etapie polecenia nie zapisują plików, nie uruchamiają walidatorów i nie
kontaktują się z `rndc`.

Po weryfikacji planu dry-run właściwa migracja pojedynczej strefy wygląda tak:

```bash
zctl zone migration-apply example.pl
zctl zone migration-apply example.pl \
  --commit --activate --confirm example.pl
```

Transakcja ponownie sprawdza niezmienność obu plików wejściowych, wykonuje
backup, zachowuje uprawnienia, zapisuje trzy elementy atomowo, uruchamia
`named-checkconf`, `rndc reconfig` i `rndc zonestatus`. Błąd na dowolnym etapie
przywraca `named.conf.local` oraz indeks i usuwa nową deklarację.
Przed wdrożeniem produkcyjnym ten przebieg jest również sprawdzany w izolacji
z prawdziwym `named-checkconf`, bez kontaktowania się z produkcyjnym `rndc`.

W TUI ekran szczegółów strefy udostępnia `F6 migracja`. W widoku migracji
`F3` pokazuje plan, a `F4` wykonuje dry-run i dopiero potem prosi o pełną nazwę
strefy oraz końcowe potwierdzenie. Stany RPZ, DNSSEC, secondary i `MANAGED`
pozostają zablokowane przez ten sam planner co CLI.

### Inwentaryzacja ACL i secondary 4.7

```bash
zctl bind inventory
zctl bind inventory --json
```

Raport przechodzi przez aktywne pliki `include`, pokazuje źródło i numer linii
każdej definicji `acl`, `primaries` lub `masters`, jej elementy oraz użycia w
`allow-query`, `allow-recursion`, `allow-transfer`, `allow-notify`,
`also-notify` i `primaries`. Polecenie nie zapisuje konfiguracji i nie wywołuje
`rndc`.

`zctl bind audit` uzupełnia raport o duplikaty, błędne i niekanoniczne
prefiksy, nierozpoznane odwołania, nieużywane definicje oraz strefy dotknięte
problemem. Kod zakończenia `1` oznacza wykrycie błędu konfiguracji wejściowej;
audyt nadal pozostaje operacją wyłącznie odczytową.

Plan uporządkowania pojedynczej ACL również nie zapisuje pliku:

```bash
zctl bind acl-plan trusted \
  --replace 192.168.200/24=192.168.200.0/24
```

Planner zachowuje pierwsze wystąpienie każdego wpisu, usuwa wyłącznie dalsze
duplikaty, stosuje jawnie podane zamiany i uruchamia `named-checkconf` na
izolowanej kopii całego aktywnego drzewa konfiguracji.

Właściwe zastosowanie identycznego planu wymaga trzech jawnych zabezpieczeń:

```bash
zctl bind acl-apply trusted \
  --replace 192.168.200/24=192.168.200.0/24 \
  --commit --activate --confirm trusted
```

Transakcja ponownie sprawdza niezmienność pliku, zachowuje właściciela i tryb,
wykonuje backup, zapis atomowy, `named-checkconf`, `rndc reconfig` i manifest.
Niepowodzenie przywraca oryginalny plik i ponownie ładuje poprzednią
konfigurację, jeśli aktywacja została już rozpoczęta.

Raport wpływu grup serwerów secondary jest odczytowy:

```bash
zctl bind secondary-report
zctl bind secondary-report --json
```

Raport łączy definicje notify i transfer w pary logiczne, pokazuje osobne
adresy każdej roli, liczbę użyć i kompletną listę korzystających stref. Różne
adresy notify i transfer są dozwolone; ostrzeżeniem jest brak jednej z ról.

Plan zmiany jednej grupy przyjmuje pełną docelową listę adresów:

```bash
zctl bind secondary-plan dns2-notify --address 5.172.189.198
zctl bind secondary-plan he-transfer --address 216.218.133.2
zctl bind secondary-apply dns2-notify --address 5.172.189.198
zctl bind secondary-apply dns2-notify --address 5.172.189.198 \
  --commit --activate --confirm dns2-notify
```

Planner odrzuca pustą listę, duplikaty oraz błędne IPv4/IPv6. Pokazuje
minimalny diff i wszystkie dotknięte strefy, a następnie sprawdza izolowaną
kandydacką konfigurację prawdziwym `named-checkconf`. Nie zapisuje plików.

`secondary-apply` ponownie buduje i sprawdza plan, odrzuca zmianę pliku
wykrytą po planowaniu, wykonuje backup, zapis atomowy, `named-checkconf` oraz
`rndc reconfig`. Manifest zawiera stare i nowe adresy, role grupy oraz listę
stref objętych zmianą. Błąd walidacji lub aktywacji uruchamia rollback
konfiguracji i ponowne `rndc reconfig`.

Strefy z `health_profile = rpz` są automatycznie zarządzanymi źródłami
polityki i nie podlegają zwykłemu cyklowi życia domen. ZoneCTL blokuje dla
nich wyłączenie, przywrócenie i kwarantannę; nadal je monitoruje.

Tak samo blokowane są operacje na strefach, dla których autodetekcja BIND
wykryła `dnssec-policy` albo `inline-signing yes`. Raport ochrony jest
dostępny bez modyfikowania systemu:

```bash
zctl zone safety
zctl zone safety example.pl --json
```

### Odczytowy raport DNSSEC 4.6

Przed planowaniem włączenia DNSSEC należy zebrać stan początkowy strefy:

```bash
zctl dnssec report example.pl
zctl dnssec report example.pl --json
zctl dnssec enable-plan example.pl
zctl dnssec enable-plan example.pl --json
zctl dnssec enable example.pl
```

Raport odpytuje lokalny BIND o `zonestatus`, stan KASP, DNSKEY i RRSIG.
Następnie oblicza DS typu 2 (SHA-256) z kluczy DNSKEY oznaczonych flagą SEP
i porównuje go z DS widocznym przez publiczny resolver. Domyślnie używany
jest resolver `1.1.1.1`; można wskazać inny przez `--resolver`.

Status `WARN` przy braku publicznego DS jest prawidłowy dla strefy podpisanej,
której DS nie został jeszcze przekazany do strefy nadrzędnej. Status `FAIL`
oznacza między innymi brak DNSKEY/RRSIG albo niezgodność opublikowanego DS.
Polecenie jest bezpieczne i nie wykonuje żadnych zapisów ani przeładowań BIND.

`enable-plan` wymaga autodetekcji deklaracji BIND. Odrzuca strefy secondary,
RPZ i strefy posiadające już pełną lub częściową konfigurację DNSSEC. Wynik
zawiera dokładny unified diff, ścieżkę katalogu kluczy i kolejność przyszłych
walidacji. Sam plan nie tworzy katalogów i nie zapisuje żadnego pliku.
Jeżeli źródłowy plik strefy znajduje się poza `/var/lib/bind/Primary`, plan
obejmuje jego bezpieczne skopiowanie, zmianę dyrektywy `file` i zachowanie
oryginału do czasu zakończenia całej transakcji.

Rdzeń przyszłej transakcji jest sprawdzany również na izolowanej konfiguracji
przez prawdziwe `named-checkzone` i `named-checkconf`. Testy nie wywołują
`rndc`, nie przeładowują usługi i nie korzystają z produkcyjnego `/etc/bind`.
Polecenie `dnssec enable` pozostaje dry-runem bez flag. Zmiana i aktywacja
wymagają równoczesnego, jawnego `--commit --activate`; podanie tylko jednej
z tych flag kończy się błędem bez zapisów.

Kontrolowany test rollbacku jest ograniczony w kodzie do strefy
`zonectl-test.invalid`. Narzędzie `tools/dnssec_rollback_drill.py` domyślnie
wykonuje dry-run, a rzeczywisty drill wymaga dwóch jawnych parametrów:
`--execute --confirm zonectl-test.invalid`. Weryfikator celowo zgłasza błąd
dopiero po zaobserwowaniu podpisywania, aby sprawdzić produkcyjną ścieżkę
przywrócenia konfiguracji i sprzątania nowych artefaktów.
Backup deklaracji zachowuje tryb, UID i GID oryginału. Rollback odtwarza te
metadane również z zapamiętanego stanu początkowego, aby BIND nie utracił
prawa odczytu pliku po przywróceniu.

### Utworzenie strefy

```bash
zctl zone create example.pl \
  --primary-ns ns1.example.pl. \
  --admin hostmaster.example.pl. \
  --ns ns1.example.pl. \
  --ns ns2.example.pl. \
  --ipv4 192.0.2.10 \
  --www

# Po sprawdzeniu planu:
zctl zone create example.pl \
  --primary-ns ns1.example.pl. \
  --admin hostmaster.example.pl. \
  --ns ns1.example.pl. \
  --ns ns2.example.pl. \
  --ipv4 192.0.2.10 \
  --www --commit
```

Transakcja wykonuje `named-checkzone`, `named-checkconf`, `rndc reconfig`
i `rndc zonestatus`. Błąd aktywacji powoduje automatyczny rollback.

### Wyłączenie i przywrócenie

Wyłączenie zachowuje plik strefy, przenosi deklarację do
`/var/lib/zonectl/disabled-zones` i usuwa include z aktywnego indeksu.

```bash
zctl zone disable example.pl --reason "koniec obsługi"
zctl zone disable example.pl --reason "koniec obsługi" --commit

zctl zone restore example.pl
zctl zone restore example.pl --commit
```

### Kwarantanna

Kwarantanna jest dostępna tylko dla uprzednio wyłączonej strefy. Wymaga
jednocześnie `--commit` i wpisania pełnej nazwy strefy. Pakiet zawiera
`zone.db`, `zone.conf`, `manifest.json` oraz sumy SHA-256.

```bash
zctl zone quarantine example.pl \
  --reason "zakończenie retencji" \
  --confirm example.pl \
  --commit
```

Pakiety znajdują się w `/var/lib/zonectl/quarantine/NAZWA_STREFY/`.
Nie należy usuwać ich ręcznie.

### Odtworzenie z kwarantanny

Należy jawnie wskazać konkretny katalog pakietu. Po odtworzeniu pakiet
pozostaje niezmieniony jako trwały ślad i źródło kolejnego odtworzenia.

```bash
zctl zone quarantine-restore example.pl \
  --package /var/lib/zonectl/quarantine/example.pl/TRANSAKCJA

zctl zone quarantine-restore example.pl \
  --package /var/lib/zonectl/quarantine/example.pl/TRANSAKCJA \
  --commit
```

Po każdej operacji sprawdź `named-checkconf`, `rndc zonestatus` oraz manifest
transakcji. Nie edytuj ręcznie indeksu ani deklaracji w trakcie transakcji.

Testy integracyjne cyklu życia budują własne pliki stref i konfigurację pod
`/tmp`, uruchamiają prawdziwe `named-checkzone` oraz `named-checkconf`, ale
zastępują `rndc` kontrolowaną atrapą. Nie przeładowują produkcyjnego BIND-a.

## Backup Veeam i backupy ZoneCTL

Podstawowym zabezpieczeniem serwera `tanatos` jest backup całej maszyny
wirtualnej VMware wykonywany przez Veeam. Pozwala on odtworzyć system,
konfigurację BIND, pliki stref, dane ZoneCTL i historię operacji jako spójny
punkt w czasie.

Manifesty, snapshoty i pakiety kwarantanny ZoneCTL są zabezpieczeniem
operacyjnym do szybkiego cofania pojedynczych zmian. Nie zastępują Veeam.
Repozytorium Git przechowuje historię kodu aplikacji i również nie zastępuje
backupu maszyny wirtualnej.

Przed wydaniem, migracją lub większą zmianą konfiguracji należy potwierdzić,
że ostatnie zadanie Veeam zakończyło się powodzeniem. Po odtworzeniu maszyny
z Veeam trzeba wykonać co najmniej:

```bash
named-checkconf /etc/bind/named.conf
rndc status
zctl domains
zctl tui
```

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

## Kontrola publikacji DS

Po przekazaniu rekordu DS rejestratorowi kontroluj jego propagację poleceniem:

```bash
zctl dnssec check-ds example.pl
```

Polecenie jest wyłącznie odczytowe. Porównuje lokalnie obliczony DS z
odpowiedziami kilku publicznych resolverów, ustala delegowane serwery NS oraz
sprawdza na każdym z nich flagę `AA`, DNSKEY i RRSIG DNSKEY. Status `PASS`
oznacza, że DS jest wszędzie zgodny, a serwery autorytatywne udostępniają ten
sam materiał kluczowy. Statusy `NOT_READY`, `NOT_PUBLISHED`, `PROPAGATING`
i `INDETERMINATE` nie upoważniają do potwierdzenia publikacji DS w KASP.

Listę kontrolowanych resolverów można określić jawnie:

```bash
zctl dnssec check-ds example.pl \
  --resolver 1.1.1.1 \
  --resolver 8.8.8.8 \
  --resolver 9.9.9.9
```

Po uzyskaniu `PASS` można najpierw wykonać dry-run potwierdzenia:

```bash
zctl dnssec confirm-ds example.pl
```

Właściwa operacja wymaga dwóch jawnych flag i ponownie wykonuje pełne
`check-ds` bezpośrednio przed zmianą stanu KASP:

```bash
zctl dnssec confirm-ds example.pl --commit --acknowledge-published
```

Po potwierdzeniu stan KASP `ds: rumoured` lub `ds: omnipresent` oznacza, że
operacji `confirm-ds` nie wolno wykonywać ponownie; `check-ds` przechodzi wtedy
w tryb monitorowania stabilizacji DNSSEC.

ZoneCTL nie wywołuje automatycznie stanu `withdrawn`, jeżeli późniejsza
weryfikacja KASP zawiedzie. Opublikowany DS pozostaje wtedy nadrzędnym faktem,
a program zapisuje manifest i nakazuje ręczną diagnostykę.

W TUI wybierz strefę, otwórz jej szczegóły klawiszem `Enter`, a następnie
naciśnij `d`. Ekran DNSSEC jest odczytowy; `r` ponawia kontrolę, strzałki i
`PgUp`/`PgDn` przewijają wynik, natomiast `q` lub `Esc` wraca do szczegółów
strefy.

W pozostałych widokach TUI obowiązuje układ zgodny z Midnight Commanderem:
`Insert` tworzy nową strefę albo rekord, `Delete` usuwa rekord, `F3` otwiera
rekordy strefy lub podgląd diff, a `F4` edytuje zaznaczony rekord.

## Plan bezpiecznego wycofania DNSSEC

Pierwszy etap wycofania jest wyłącznie odczytowy:

```bash
zctl dnssec disable-plan example.pl
```

Polecenie pokazuje końcowy diff konfiguracji, inwentaryzuje klucze i artefakty
podpisywania oraz drukuje obowiązkową kolejność operacji. Nie usuwa DS, nie
zmienia KASP, nie zapisuje konfiguracji i nie przeładowuje BIND. Diff wolno
zastosować dopiero po potwierdzonym zniknięciu DS z delegacji i zakończeniu
kontrolowanej procedury `withdrawn`.

Przed usunięciem DS utwórz zweryfikowany pakiet odtworzeniowy. Bez flagi
polecenie pozostaje dry-runem:

```bash
zctl dnssec withdrawal-backup example.pl
zctl dnssec withdrawal-backup example.pl --commit
```

Pakiet zawiera deklarację BIND, plik strefy, klucze, artefakty podpisywania,
sumy SHA-256, metadane właścicieli i uprawnień oraz bieżący raport DNSSEC i
kontrolę DS. Utworzenie pakietu nie zmienia konfiguracji ani stanu BIND.

Po usunięciu DS u rejestratora nie wykonuj `rndc dnssec -checkds withdrawn`
od razu. Poczekaj na propagację i sprawdź jego zniknięcie na wielu
resolwerach:

```bash
zctl dnssec withdrawal-check example.pl
zctl dnssec withdrawal-check example.pl \
  --resolver 1.1.1.1 \
  --resolver 8.8.8.8 \
  --resolver 9.9.9.9
```

Polecenie jest wyłącznie odczytowe — wysyła zapytania `dig ... DS` do
wskazanych resolwerów i nie dotyka BIND, KASP ani rejestratora. Status
`BLOCKED` wskazuje resolwery, na których DS jest nadal widoczny; w tym
stanie `rndc dnssec -checkds withdrawn` nie wolno wykonywać. Dopiero status
`READY_FOR_WITHDRAWN` — brak DS na wszystkich sprawdzonych resolwerach —
pozwala rozważyć ten krok, pod warunkiem że DNSKEY i RRSIG są nadal
bezpiecznie publikowane. Status `ERROR` oznacza problem z samym zapytaniem
(np. timeout) i również nie upoważnia do wycofania.

Gdy `withdrawal-check` zwróci `READY_FOR_WITHDRAWN`, wykonanie właściwego
kroku jest osobną, jawną operacją:

```bash
zctl dnssec withdrawal-confirm example.pl
zctl dnssec withdrawal-confirm example.pl --commit --acknowledge-withdrawn
```

Bez flag polecenie jest dry-runem — pokazuje wynik świeżej kontroli DS i nic
nie zmienia. Właściwe wykonanie `rndc dnssec -checkds withdrawn` wymaga
jednocześnie `--commit` i `--acknowledge-withdrawn`; podanie tylko jednej z
tych flag kończy się statusem `BLOCKED`. Nawet z obiema flagami polecenie
uruchamia pełną kontrolę DS ponownie, bezpośrednio przed wywołaniem `rndc` —
jeśli w tej właśnie chwili wynik nie jest `READY_FOR_WITHDRAWN` (np. DS
zdążył się na nowo pojawić przez cache resolvera), operacja jest blokowana.
Powodzenie zapisuje manifest z transakcją i kontrolą DS, która ją
autoryzowała, w `/var/backups/zonectl-dnssec-withdrawal-confirm/manifests`.

Po `withdrawal-confirm` KASP **nie** przejdzie samoczynnie w stan końcowy.
Dopóki strefa ma `dnssec-policy default`, cel klucza pozostaje
`goal: omnipresent` — KASP nadal dąży do posiadania DS i stan `ds` nie zejdzie
do `hidden`. Czekanie na `hidden` pod polityką `default` jest bezcelowe.

Dokumentacja BIND wymaga przeprowadzenia strefy przez wbudowaną politykę
`insecure`; samo usunięcie `dnssec-policy` spowodowałoby ponowne podpisanie
strefy. Stąd wycofanie ma dwa etapy.

**Etap 1 — podmiana polityki na `insecure`:**

```bash
zctl dnssec disable-apply example.pl --stage insecure
zctl dnssec disable-apply example.pl --stage insecure --commit --activate
```

Podmienia `dnssec-policy default` na `dnssec-policy insecure`, zostawiając
`inline-signing`. Bramką jest zniknięcie DS ze wszystkich kontrolowanych
resolverów — ten sam warunek, który przepuszcza `withdrawal-confirm`. Widoczny
DS jest twardą blokadą, której nie przesłania żadna flaga. Ten etap przestawia
cel KASP na `hidden` i uruchamia uporządkowane wycofywanie kluczy.

Następnie obserwujemy, aż KASP schowa klucze:

```bash
rndc dnssec -status example.pl
```

**Etap 2 — usunięcie konfiguracji DNSSEC:**

```bash
zctl dnssec prepare-finalize-serial example.pl
zctl dnssec prepare-finalize-serial example.pl --commit
zctl dnssec disable-apply example.pl --stage finalize
zctl dnssec disable-apply example.pl --stage finalize --commit --activate
```

Przed finalizacją ZoneCTL porównuje serial źródłowego pliku strefy z serialem
aktualnie serwowanym przez wariant inline-signed. Źródłowy serial musi być
ściśle nowszy, aby secondary zaakceptowały pierwszą strefę bez DNSSEC.
`prepare-finalize-serial` wylicza bezpieczny serial, sprawdza kandydacki plik
przez `named-checkzone`, a po `--commit` wykonuje backup i atomowo aktualizuje
wyłącznie plik źródłowy. Polecenie nie przeładowuje BIND; właściwe przełączenie
następuje dopiero w transakcji `finalize`.

Usuwa `dnssec-policy`, `inline-signing` i `key-directory`. Bramką jest
potwierdzenie z KASP, że **wszystkie** stany kluczy (`goal`, `dnskey`, `ds`)
są `hidden`. Każdy inny odczytany stan jest twardą blokadą.

W obu etapach brak `--commit` oznacza dry-run; `--activate` dokłada
`rndc reconfig` i weryfikację `rndc zonestatus`. Gdy stanu KASP nie da się
odczytać (inna wersja BIND, zmieniony format wyjścia), polecenie także
blokuje, ale operator może wziąć odpowiedzialność na siebie flagą
`--acknowledge-unsigned`. Niepowodzenie `named-checkconf` lub aktywacji
powoduje pełny rollback deklaracji z backupu i status `ROLLED-BACK`.

Żaden z etapów **nie usuwa kluczy ani pakietu odtworzeniowego** — są jedyną
drogą powrotu do stanu podpisanego.

### Produkcyjna weryfikacja procedury 4.6

Pełny proces włączenia DNSSEC zweryfikowano na `mops.elk.pl`: DNSKEY i RRSIG
były zgodne na primary i secondary, DS został potwierdzony przez wiele
resolverów, a odpowiedzi walidujące posiadały flagę AD.

Pełny proces wycofania zweryfikowano na `investin.elk.pl`. Po usunięciu DS,
potwierdzeniu `withdrawn`, przejściu przez politykę `insecure` i osiągnięciu
stanów KASP `goal=hidden`, `dnskey=hidden`, `ds=hidden`, finalizacja została
przepuszczona dopiero po podniesieniu źródłowego seriala ponad serial wariantu
podpisanego. Po finalizacji:

- primary oraz `ns2.elkman.pl` i pięć serwerów HE.net serwowały serial
  `2026081101`;
- wszystkie serwery autorytatywne zwracały zero rekordów DNSKEY;
- DS był nieobecny przez resolvery `1.1.1.1`, `8.8.8.8` i `9.9.9.9`;
- BIND raportował `secure: no`, a deklaracja nie zawierała `dnssec-policy`,
  `inline-signing` ani `key-directory`;
- klucze, manifesty, snapshoty i pakiety odtworzeniowe pozostały zachowane.
