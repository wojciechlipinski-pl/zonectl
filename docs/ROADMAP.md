# Roadmap

Roadmapa porządkuje dalszy rozwój ZoneCTL. Pozycje oznaczone `[x]` zostały
zrealizowane, a `[ ]` pozostają do wykonania.

## Zrealizowane

- [x] Rebranding projektu na ZoneCTL.
- [x] Komenda `zctl` i przestrzeń nazw Python `zonectl`.
- [x] Migracja katalogów systemowych do ścieżek ZoneCTL.
- [x] Generator dokumentacji projektu.
- [x] Profil kontroli zdrowia RPZ.
- [x] Kontrola składni, stanu załadowania i świeżości pliku RPZ.
- [x] Testy dekodowania klawiszy funkcyjnych dla xterm i PuTTY/Linux.
- [x] Wyjście z głównego TUI przez F10, `q` i Esc.
- [x] Ujednolicić klawisze TUI w stylu Midnight Commandera: `Insert`
  dodaje, `Delete` usuwa, `F3` otwiera podgląd, `F4` edytuje, a `d`
  otwiera stan DNSSEC.

## Etap 1 — bezpieczeństwo zapisu i obsługa awarii

- [x] Dodać test zapisu z widoku Pending Changes.
- [x] Dodać test odświeżenia modelu po COMMIT.
- [x] Dodać test zachowania po nieudanym `named-checkzone`.
- [x] Dodać test zachowania po nieudanym `rndc reload`.
- [x] Potwierdzić automatyczny rollback pliku strefy po błędzie reloadu.
- [x] Opisać procedurę ręcznego rollbacku po błędzie reloadu BIND.
- [x] Ujednolicić prezentację błędów warstwy UI i core.

## Etap 2 — kontrola i historia zmian

- [x] Dodać podgląd różnic w formacie unified diff przed COMMIT.
- [x] Dodać eksport zmian przed COMMIT.
- [x] Rozbudować historię zmian i transakcji.
- [x] Dodać cofanie ostatniej zmiany w bieżącej sesji.
- [x] Dodać tryb tylko do odczytu.
- [x] Dodać mechanizm blokowania równoległej edycji.

## Etap 3 — operacje masowe i wiele stref

- [x] Dodać rozbudowane filtrowanie rekordów.
- [x] Dodać walidację wartości zależną od typu rekordu.
- [x] Dodać operacje masowe `SELECT`, `SET` i `DELETE`.
- [x] Zapisywać operację masową jako jedną transakcję.
- [x] Dodać obsługę wielu stref w jednej sesji.

## ZoneCTL 4.4 — cykl życia stref DNS

### Tworzenie strefy

- [x] Dodać polecenie CLI tworzenia domeny z dry-run i jawnym `--commit`.
- [x] Dodać kreator nowej domeny w TUI, oparty na tym samym planie i
  transakcji co polecenie CLI.
- [x] Walidować nazwę domeny i odrzucać strefy już istniejące.
- [x] Umożliwić wybór grupy, serwerów NS, administratora SOA i parametrów
  czasowych SOA.
- [x] Zapisywać przypisanie grupy atomowo w `groups.yaml` w ramach tej samej
  transakcji i przywracać poprzedni plik podczas rollbacku.
- [x] Generować minimalny plik strefy z SOA, NS i poprawnym serialem.
- [x] Opcjonalnie dodawać rekordy A/AAAA dla apexu i `www`.
- [x] Dodawać deklarację `primary` do zarządzanego fragmentu konfiguracji
  BIND bez modyfikowania obcych sekcji.
- [x] Przygotować transakcyjny bootstrap indeksu i katalogu deklaracji BIND,
  z backupem, walidacją i automatycznym rollbackiem.
- [x] Przed aktywacją wykonywać `named-checkzone` i `named-checkconf`.
- [x] Aktywować strefę przez kontrolowane `rndc reconfig` i potwierdzać jej
  załadowanie.
- [x] Zapisywać manifest utworzenia, backup konfiguracji i wynik każdego
  etapu.
- [x] Automatycznie wycofywać plik oraz konfigurację po błędzie aktywacji.

### Wyłączanie i przywracanie

- [x] Dodać rdzeń odwracalnej operacji wyłączenia strefy bez usuwania jej
  danych.
- [x] Zachowywać plik strefy i deklarację oraz zapisywać manifest wyłączenia.
- [x] Usuwać deklarację strefy z aktywnej konfiguracji przez transakcję.
- [x] Potwierdzać przez BIND, że wyłączona strefa nie jest już obsługiwana.
- [x] Prowadzić listę stref wyłączonych i pakietów kwarantanny wraz z datą,
  operatorem i przyczyną.
- [x] Dodać transakcyjny rdzeń przywracania wyłączonej strefy z pełną
  walidacją, aktywacją i rollbackiem.

### Kwarantanna i usuwanie

- [x] Wymagać wcześniejszego wyłączenia strefy przed kwarantanną.
- [x] Wymagać podwójnego potwierdzenia: `--commit` i pełnej nazwy domeny.
- [x] Przenosić dane do chronionej kwarantanny zamiast wykonywać bezpośrednie
  i nieodwracalne usunięcie.
- [x] Zapisywać sumy kontrolne, manifest i kompletny pakiet odtworzeniowy.
- [x] Umożliwić odtworzenie strefy z kwarantanny z weryfikacją manifestu
  i sum SHA-256, bez usuwania pakietu odtworzeniowego.
- [x] Dodać konfigurowalny okres retencji przed trwałym usunięciem oraz
  odczytowy plan weryfikujący wiek, manifest i sumy SHA-256 pakietu.
- [x] Trwałe usunięcie udostępnić wyłącznie jako osobną operację
  administracyjną z domyślnym dry-runem, ponowną kontrolą integralności,
  potwierdzeniem strefy i identyfikatora pakietu, atomowym stagingiem,
  zweryfikowanym archiwum ratunkowym oraz zewnętrznym manifestem.

### Wymagania bezpieczeństwa 4.4

- [x] Dodać testy integracyjne tworzenia, wyłączania i przywracania z
  odseparowaną instancją BIND.
- [x] Testować awarie `named-checkzone`, `named-checkconf`, `rndc reconfig`
  i weryfikacji załadowania.
- [x] Potwierdzić rollback po awarii na każdym etapie cyklu życia strefy.
- [x] Wykluczyć przypadkowe zarządzanie automatyczną strefą RPZ jak zwykłą
  domeną.
- [x] Wykrywać strefy DNSSEC i `inline-signing`, raportować ich profil oraz
  blokować dla nich zwykłe operacje cyklu życia.
- [x] Udokumentować współpracę z backupem Veeam jako głównym zabezpieczeniem
  maszyny wirtualnej.

## ZoneCTL 4.7 — migracja istniejących deklaracji stref

- [x] Zinwentaryzować strefy zdefiniowane bezpośrednio w
  `/etc/bind/named.conf.local` i odróżnić je od stref automatycznych, RPZ,
  secondary oraz już zarządzanych przez ZoneCTL.
- [x] Dodać pozbawiony skutków ubocznych plan migracji pojedynczej strefy do
  `/etc/bind/zonectl-zones.d/<strefa>.conf`, zachowujący kompletny blok BIND.
- [x] Aktualizować `/etc/bind/zonectl-zones.conf` jako indeks zawierający
  dokładnie jeden `include` dla każdej deklaracji zarządzanej przez ZoneCTL.
- [x] Wymagać backupu `named.conf.local`, indeksu i deklaracji, walidacji
  `named-checkconf`, kontrolowanego `rndc reconfig`, potwierdzenia
  `rndc zonestatus` oraz pełnego rollbacku po błędzie.
- [x] Domyślnie blokować migrację RPZ, secondary i stref DNSSEC; obsłużyć je
  dopiero przez jawne, osobne profile migracyjne.
- [x] Udostępnić dry-run i migrację pojedynczej strefy w CLI oraz TUI, bez
  automatycznej migracji zbiorczej produkcyjnej konfiguracji.

### Zarządzanie ACL i serwerami secondary

- [x] Zinwentaryzować źródła definicji ACL BIND oraz ich użycie w
  `allow-query`, `allow-recursion`, `allow-transfer`, `allow-notify`,
  `also-notify` i `primaries`.
- [x] Dodać odczytowy widok listy zaufanych sieci i hostów (`trusted`) wraz z
  plikiem źródłowym, numerem linii i miejscami użycia każdej ACL.
- [x] Audytować duplikaty, błędne prefiksy, nierozpoznane odwołania,
  nieużywane definicje i wpływ problemów na strefy.
- [x] Generować odczytowy diff uporządkowania pojedynczej ACL i walidować
  kandydacką konfigurację w izolacji prawdziwym `named-checkconf`.
- [x] Stosować zweryfikowany plan ACL transakcyjnie z backupem, atomowym
  zapisem, kontrolowanym `rndc reconfig`, manifestem i rollbackiem.
- [x] Dodać edycję `trusted` w CLI i TUI z walidacją adresów IPv4, IPv6,
  prefiksów CIDR, negacji oraz nazw dozwolonych elementów ACL.
- [x] Dodać zarządzanie nazwanymi grupami serwerów secondary/slave używanymi
  przez `also-notify`, `allow-transfer`, `allow-notify` i `primaries`, bez
  powielania adresów w deklaracjach poszczególnych stref.
- [x] Dodać odczytowy, walidowany plan zmiany pełnej listy adresów pojedynczej
  grupy notify lub transfer wraz z raportem wpływu na strefy.
- [x] Stosować plan zmiany grupy secondary transakcyjnie z backupem, atomowym
  zapisem, `named-checkconf`, `rndc reconfig`, manifestem i rollbackiem.
- [x] Udostępnić w TUI przegląd ACL i grup secondary oraz transakcyjną edycję
  pełnej listy adresów grupy secondary przez `F3`/`F4`.
- [x] Udostępnić odczytowy raport pokazujący role, adresy i strefy korzystające
  z danego serwera lub grupy secondary.
- [x] Udostępnić przypisywanie strefy do logicznych par secondary w CLI i TUI.
- [x] Każdą zmianę ACL wykonywać przez planowany diff, backup, atomowy zapis,
  `named-checkconf`, kontrolowane `rndc reconfig` i automatyczny rollback.
- [x] Blokować przed backupem usunięcie ostatniego wpisu administracyjnego,
  transferowego lub notify oraz całej aktywnie używanej ACL; pokazywać raport
  skutków bez oferowania niebezpiecznego obejścia.
- [x] Rejestrować w manifeście operatora, przyczynę, stan przed i po zmianie
  oraz listę stref, których dotyczyła modyfikacja ACL lub secondary.

## Jakość techniczna

- [x] Zachować względną nazwę właściciela i komentarz inline po edycji.
- [ ] Uzupełnić docstringi publicznych klas i metod.
- [ ] Rozszerzyć pokrycie testami krytycznych ścieżek zapisu.
- [x] Dodać statyczną analizę typów. Ścisła bramka `mypy` obejmuje już nowe
  moduły retencji/purge oraz audyt publicznego API; zakres należy rozszerzać
  stopniowo po usunięciu błędów typów z kolejnych modułów. Bramką objęto już
  także transakcje tworzenia, wyłączania i przywracania stref oraz pakowania
  strefy do kwarantanny i jej bezpiecznego odtwarzania, a także wykrywanie
  konfiguracji oraz planowanie i transakcje migracji i relokacji zarządzanych
  plików stref. Kolejny zakres obejmuje bezpieczną serializację manifestów
  audytowych, analizę wpływu ACL, health secondary i parser konfiguracji BIND,
  a następnie planowanie przypisań secondary, transakcje ACL i secondary,
  inwentaryzację stref nieaktywnych, blokady sesji edycji oraz bezstratny
  adapter dokumentu, serializację, zapis kandydatów, dziennik audytowy,
  główny silnik transakcji, sesję edycji strefy oraz instalację MANAGED RPZ i
  transakcyjną migrację zewnętrznej konfiguracji RPZ. Pierwszy zakres TUI
  obejmuje edytor rekordów, formularz tworzenia strefy i wspólne dialogi.
  Wszystkie moduły core przechodzą pełny audyt mypy; ostatni zakres domyka
  transakcję włączenia DNSSEC i sesję edycji wielu stref. Bramką objęto też
  wszystkie pomocnicze moduły TUI; pozostały dług typów interfejsu skupia się
  w głównej aplikacji `curses_app.py`. Pierwszy etap porządkuje typy wspólnych
  funkcji sortowania i renderowania, zmniejszając raport mypy ze 100 do 56
  błędów. Drugi etap typuje onboarding BIND, audyt i import DNSSEC oraz ekran
  informacji o projekcie, pozostawiając 33 błędy przed objęciem całego pliku
  bramką. Trzeci etap typuje wspólne widoki wyników, walidację rekordów,
  sesję wielu stref oraz plany i wyniki transakcji DNSSEC, redukując raport
  do 15 błędów. Ostatni etap typuje obsługę ACL i secondary, edytory list oraz
  migrację i relokację stref; cały `curses_app.py` przechodzi rygorystyczny
  audyt i zostaje objęty bramką CI. Pierwszy etap porządkowania głównego CLI
  rozdziela typy wyników poleceń BIND access, ACL, secondary, onboardingu i
  MANAGED RPZ, zmniejszając liczbę błędów należących do `cli.py` z 304 do 196;
  drugi etap rozdziela instalację MANAGED RPZ, migrację EXTERNAL RPZ oraz
  inwentaryzację i audyt dostępu BIND, pozostawiając 139 błędów. Trzeci etap
  typuje potwierdzenie DS, finalizację seriala oraz plan, wykonanie
  i pakiet bezpieczeństwa wycofania DNSSEC, pozostawiając 95 błędów. Czwarty
  etap rozdziela plan i wynik włączenia DNSSEC, kontrole DS oraz
  potwierdzenie wycofania, pozostawiając 75 błędów. Piąty etap typuje raport
  DNSSEC, migrację zarządzanych stref, raport
  bezpieczeństwa cyklu życia, inwentaryzację i retencję kwarantanny,
  pozostawiając 51 błędów. Szósty etap rozdziela purge, odtwarzanie z
  kwarantanny, kwarantannę oraz transakcje disable, restore i create,
  pozostawiając 12 błędów przed końcowym objęciem modułu bramką. Ostatni etap
  typuje wspólne funkcje CLI i usuwa pozostałe kolizje inferencji; `cli.py`
  przechodzi ścisły audyt i trafia do CI. Historyczny moduł kompatybilności
  `legacy_v220.py` pozostaje jawnym, osobno wydzielonym wyjątkiem.
- [x] Dodać automatyczne formatowanie i lint. Ruff normalizuje cały kod,
  testy i skrypty, a CI blokuje niepoprawne formatowanie, podstawowe błędy
  składniowe, nieużywane importy oraz niezdefiniowane nazwy.
- [x] Dodać testy integracyjne z odseparowaną konfiguracją i prawdziwymi
  narzędziami walidacyjnymi BIND, bez kontaktu z produkcyjnym `rndc`.
- [x] Dodać testy stref `inline-signing`. Izolowana macierz korzysta z
  prawdziwych `named-checkzone` i `named-checkconf`, sprawdza akceptację `yes`,
  odrzucenie `no` przy aktywnej polityce oraz błędnej wartości, poprawność
  discovery i blokady zwykłego cyklu życia oraz ponownego włączania DNSSEC.
- [x] Zweryfikować TUI dla kolejnych rozmiarów i typów terminali. Rygorystyczna
  macierz odrzuca rysowanie poza ekranem dla widoków kompaktowych, VT100,
  xterm i szerokich terminali, sprawdza animację UTF-8/ASCII oraz sekwencje
  `Home` i `End` używane przez xterm, VT100, konsolę Linux i rxvt.
- [x] Dodać obsługę klawiszy `Home` i `End` we wszystkich polach tekstowych
  formularzy TUI, szczególnie podczas edycji długich rekordów TXT.
- [x] Dodać naturalne sortowanie nazw rekordów, aby etykiety numeryczne
  (szczególnie w strefach odwrotnych `in-addr.arpa`) były prezentowane jako
  `1, 2, 3, ..., 10, 11`, zamiast leksykograficznie jako `1, 10, 100, ...`.

## ZoneCTL 4.6 — zarządzanie DNSSEC

- [x] Dodać odczytowy raport konfiguracji KASP, kluczy, DNSKEY, RRSIG,
  lokalnie obliczonego DS i DS widocznego przez publiczny resolver.
- [x] Dodać plan oraz dry-run bezpiecznego włączenia DNSSEC dla strefy.
- [x] Wykonać backup konfiguracji BIND i materiału kluczowego przed zmianą.
- [x] Przetestować rdzeń transakcji i rollback na izolowanej konfiguracji
  przy użyciu prawdziwych walidatorów BIND.
- [x] Aktywować `dnssec-policy default` oraz `inline-signing` transakcyjnie,
  z walidacją `named-checkconf`, kontrolowanym `rndc reconfig` i rollbackiem.
- [x] Monitorować utworzenie kluczy, podpisanie strefy i stan rekordów DNSKEY.
- [x] Wyświetlać rekord DS przeznaczony do przekazania rejestratorowi.
- [x] Rozbić prezentowany rekord DS na pola zgodne z formularzami rejestratorów:
  ID klucza (key tag), algorytm klucza, algorytm skrótu i skrót klucza;
  pokazywać nazwy algorytmów IANA oraz pełny rekord do skopiowania.
- [x] Dodać do raportu CLI etap procesu, postęp, lokalny termin następnej
  kontroli i jednoznaczną blokadę publikacji DS do osiągnięcia gotowości KASP.
- [x] Sprawdzać publikację DS oraz pełny łańcuch zaufania DNSSEC.
- [x] Dodać odczytową kontrolę DS przez wiele resolverów oraz zgodności DNSKEY
  i RRSIG na wszystkich serwerach autorytatywnych.
- [x] Dodać kontrolowane potwierdzenie publikacji DS w KASP, blokowane bez
  wyniku `PASS` z pełnej kontroli delegacji.
- [x] Dodać w TUI odczytowy ekran etapu DNSSEC, KASP, propagacji DS oraz
  zgodności serwerów autorytatywnych.
- [x] Prowadzić operatora przez kolejne etapy DNSSEC bez opuszczania TUI:
  kontekstowe odświeżenie gotowości, kontrolę publikacji DS oraz strzeżone
  potwierdzenie DS w KASP; po każdej operacji ponownie odczytywać deklarację
  BIND, aby nie prezentować nieaktualnego etapu.
- [x] Dodać osobną, wieloetapową i bezpieczną procedurę wyłączenia DNSSEC:
  odczytowy plan, zweryfikowany backup, odczytowa kontrola zniknięcia DS na
  wielu resolwerach i strzeżone wykonanie `rndc dnssec -checkds withdrawn`
  dopiero po świeżym potwierdzeniu i podwójnej jawnej fladze.
- [x] Dodać pozbawiony skutków ubocznych plan wyłączenia DNSSEC z
  obowiązkowymi bramkami DS, KASP, backupu i walidacji BIND.
- [x] Dodać atomowy i zweryfikowany pakiet odtworzeniowy tworzony przed
  rozpoczęciem wycofywania DS.
- [x] Chronić operatora przed przedwczesnym usunięciem DS przez odczytową
  kontrolę zniknięcia DS na wielu resolwerach, blokującą `withdrawn` do
  czasu potwierdzenia.
- [x] Po wykonaniu `withdrawal-confirm` dodać transakcyjne zastosowanie
  diffu z `disable-plan` (usunięcie `dnssec-policy`/`inline-signing`),
  z walidacją `named-checkconf`, kontrolowanym `rndc reconfig` i rollbackiem.
- [x] Pokryć włączanie, awarie i rollback testami integracyjnymi BIND oraz
  przeprowadzić produkcyjne włączenie i pełne wycofanie DNSSEC na strefach
  testowych. Rotacja kluczy pozostaje osobnym zakresem kolejnego wydania.

## Dokumentacja

- [x] Dodać polskie i angielskie przykłady wszystkich 17 wspieranych typów
  rekordów. Test dokumentacji porównuje katalog ze źródłową listą typów i
  przepuszcza każde przykładowe RDATA przez produkcyjny walidator formularza.
- [x] Dodać bezpieczne, syntetyczne zrzuty ekranów TUI generowane bez dostępu
  do konfiguracji produkcyjnej.
- [x] Rozszerzyć izolowany demonstrator o syntetyczne widoki ACL/secondary,
  udanej transakcji i zakończonego rollbacku oraz opublikować ich zrzuty bez
  dostępu do hosta, sieci ani konfiguracji BIND.
- [x] Przygotować polską i angielską instrukcję odtwarzania po awarii,
  rozdzielając rollback pojedynczej strefy, naprawę niedostępnego BIND,
  pełne odtworzenie hosta oraz kontrolę DNSSEC i zarządzanej integracji RPZ.
- [ ] Opisać procedurę wydania nowej wersji.
- [ ] Prowadzić listę wspieranych wersji Pythona, BIND i systemów.
- [x] Przygotować publiczną dokumentację w języku polskim i angielskim.
- [x] Ustawić angielski `README.md`, zachować `README.pl.md` oraz dodać
  angielską instrukcję operatorską w `docs/en/OPERATIONS.md`.

## ZoneCTL 4.8 — autodetekcja, integracje i nowy TUI

Priorytetem 4.8 jest bezpieczne uruchomienie ZoneCTL w istniejącym środowisku
BIND oraz stopniowa przebudowa TUI. Każde rozpoznanie jest najpierw tylko
odczytowe; import wymaga osobnego planu, dry-runu i potwierdzenia operatora.

### Pierwsze uruchomienie i autodetekcja BIND

- [x] Rozpocząć odczytowy raport środowiska: aktywny graf `include`, liczba i
  typy stref, DNSSEC oraz strefy używane przez `response-policy`.
- [x] Dodać kreator pierwszego uruchomienia w TUI z podsumowaniem wykrytej
  konfiguracji i możliwością pominięcia importu.
- [x] Przygotować plan importu istniejących stref, ACL, grup secondary i RPZ;
  nie modyfikować automatycznie obcych plików konfiguracyjnych.
- [x] Każdy wspierany import wykonywać przez diff, backup, `named-checkconf`, dry-run,
  jawne potwierdzenie, manifest i rollback.

### Opcjonalna integracja CERT Polska RPZ

- [x] Zachować dotychczasowy pomiar wieku RPZ w sekundach/minutach i wykrywać
  istniejący timer oraz aktualizator jako tryb `EXTERNAL`.
- [x] Dodać odczytowy panel F3 integracji RPZ w TUI: tryb zarządzania, stan,
  wiek, serial, liczba węzłów, timer, usługa i ścieżka aktualizatora.
- [x] Pokazywać wspólny stan `ACTIVE`, `DELAYED`, `STALE`, `FAILED` lub
  `DISABLED`, serial, liczbę węzłów, ostatni wynik usługi i następne uruchomienie.
- [x] Dodać opcjonalny tryb `MANAGED` na świeżym systemie: instalacja aktualizatora i unitów systemd
  wyłącznie po planie, dry-runie oraz jawnym zatwierdzeniu.
  - [x] Odczytowy plan instalacji i blokada cichego przejęcia trybu `EXTERNAL`.
  - [x] Odczytowa inwentaryzacja i plan migracji `EXTERNAL → MANAGED` z SHA-256.
  - [x] Transakcyjny dry-run migracji w izolowanym katalogu tymczasowym.
  - [x] Produkcyjna transakcja przełączenia z manifestem i rollbackiem.
    - [x] Silnik transakcji, potrójna bramka i wymuszony test rollbacku.
    - [x] Bramka powdrożeniowa: unity, wynik usługi, serial, świeżość i BIND.
    - [x] Kontrolowane przełączenie zweryfikowane na aktywnym środowisku.
- [x] W migracji `EXTERNAL → MANAGED` zachować interwał pięciu minut,
  walidację `named-checkzone`, ochronę seriala, atomową podmianę, backup,
  kontrolowany reload i rollback.
- [x] W instalatorze świeżego systemu zachować walidację `named-checkzone`,
  ochronę seriala, atomową podmianę, backup, kontrolowany reload i rollback.
- [x] Nie przejmować istniejącego mechanizmu `EXTERNAL` bez osobnej migracji.
- [x] Dodać plan, dry-run i transakcję świeżej instalacji, która jednoznacznie
  wskazuje blok `options`, dodaje `response-policy` i nigdy nie uruchamia się
  automatycznie podczas instalacji pakietu `.deb`.
  - [x] Jednoznaczne wykrywanie pliku z blokiem `options` i blokada konfliktów.
  - [x] Izolowany dry-run: HTTPS, kandydaci w `/tmp`, `named-checkzone`,
    `named-checkconf`, kontrola skryptu i unitów bez zapisu systemowego.
  - [x] Silnik transakcji z trzema warunkami zgody, backupem, manifestem,
    atomowym zapisem, bramką powdrożeniową i wymuszonym testem rollbacku.
  - [x] Zweryfikować dry-run oraz wymuszony rollback na świeżym Debianie.
  - [x] Zweryfikować kontrolowaną instalację na świeżym środowisku testowym.

### Bezpieczne materiały demonstracyjne

Deterministyczny demonstrator i pierwsza publiczna galeria zostały wydane
w ZoneCTL 4.10.1, a komplet widoków domknięto w ZoneCTL 4.11.0.

- [x] Dodać deterministyczny generator demonstracyjnego stanu TUI, który nie
  czyta `/etc/bind`, `/var/lib/bind`, nazw hostów ani danych operatora.
- [x] Opublikować pochodzące z rzeczywistego renderera syntetyczne ekrany:
  listę stref z ramką oczekiwania, raport BIND, DNSSEC, rekordy oraz formularze
  dodawania rekordu i tworzenia strefy.
- [x] Uzupełnić galerię 4.11 o widoki ACL/secondary, wyniku transakcji oraz
  kontrolowanego rollbacku.
- [x] Zapisać obrazy w `docs/images/` i osadzić je w obu wersjach README.
- [x] Dodać test wykrywający w metadanych obrazów i plikach demonstracyjnych
  zabronione nazwy produkcyjne.

### Docelowy wygląd TUI

Szczegółowe kryteria zgodności z opublikowanymi grafikami określa
`docs/TUI_VISUAL_CONTRACT.md`.

- [x] Rozpocząć przebudowę ekranu głównego na responsywny układ panelowy: lista stref,
  zaznaczenie aktywnego wiersza oraz panel szczegółów wybranej strefy.
- [x] Ujednolicić widoki planu, dry-runu, ostrzeżenia, sukcesu i rollbacku,
  zachowując tę samą hierarchię informacji i semantykę kolorów.
- [x] Stosować stałe paski tytułu i klawiszy funkcyjnych oraz skróty w stylu
  Midnight Commandera: F3 podgląd, F4 edycja, Insert dodawanie, F8/Delete
  usuwanie i F10 powrót.
- [x] Ujednolicić ekran główny z kontraktem wizualnym: turkusowe zaznaczenie,
  nagłówki kolumn, separatory sekcji i pasek klawiszy w stylu MC.
- [x] Pokazywać najważniejszy stan operacji, blokady bezpieczeństwa, postęp i
  następny krok bez konieczności analizowania surowego raportu.
- [x] Zapewnić poprawne skalowanie, zawijanie i przewijanie na małych
  terminalach, bez utraty dostępu do potwierdzeń i komunikatów błędów.
- [x] Poprawić responsywne zawijanie ekranów szczegółów i wyników transakcji:
  ograniczać tekst do szerokości lewego panelu, zachowywać wcięcia wyników
  BIND, przeliczać linie po zmianie rozmiaru i przewijać po liniach już
  zawiniętych; testować ochronę przed wejściem tekstu w prawy panel.
- [x] Po udanym zapisie rekordów bezwarunkowo przeładowywać aktywny plik
  strefy w bieżącej sesji TUI oraz obsługiwać zgodnie z belką oba klawisze
  usuwania: `F8` i `Delete`.
- [x] Traktować grafiki koncepcyjne wyłącznie jako wzorzec projektu; publiczne
  zrzuty oznaczane jako działająca aplikacja muszą pochodzić z rzeczywistego
  renderera ZoneCTL na danych demonstracyjnych.

### Zabezpieczenia ACL i secondary

Kontrakt bramek, manifestu i testów opisuje
`docs/ACL_SECONDARY_SAFETY_PLAN.md`. Implementację należy prowadzić etapami,
zaczynając od raportu wpływu tylko do odczytu.

- [x] Dodać wspólny, odczytowy raport wpływu `bind access-impact`, który
  rozwija zależności pomiędzy nazwanymi listami, pokazuje role, użycia,
  dotknięte strefy, różnicę wpisów, poziom ryzyka i cykle zależności.
- [x] Dołączyć raport wpływu do planów ACL i secondary oraz blokować plan,
  gdy zależności są cykliczne lub wpływu nie można wiarygodnie ustalić;
  poziomy LOW/MEDIUM/HIGH pozostają informacyjne do czasu wdrożenia bramek.
- [x] Zezwalać na dry-run ryzyka HIGH, ale blokować zwykły commit ACL lub
  secondary przed backupem i zapisem; nie udostępniać obejścia awaryjnego
  przed wdrożeniem rozszerzonego potwierdzenia i przyczyny w manifeście.
- [x] Klasyfikować usunięcie ostatniej logicznej pary secondary ze strefy jako
  HIGH i blokować commit przed utworzeniem backupu oraz zmianą konfiguracji.
- [x] Blokować przed backupem usunięcie ostatniego zdalnego wpisu ACL
  używanej przez administrację, zapytania, rekursję, transfer lub notify oraz
  odłączenie ostatniej pary secondary.
- [x] Pokazywać dokładne role i usuwane wpisy dla ryzyka `HIGH`; nie oferować
  obejścia ani rozszerzonego potwierdzenia dla operacji odcinającej ostatni
  aktywny dostęp.
- [x] Rozszerzyć manifest o operatora, przyczynę, ryzyko, stan przed i po operacji oraz
  pełną listę dotkniętych stref.
- [x] Po `rndc reconfig` ponownie odczytywać konfigurację ACL/secondary,
  porównywać ją z zatwierdzonym planem i przy rozbieżności wykonywać rollback
  wraz z kontrolą przywróconego pliku.
- [x] Dla dotkniętych stref sprawdzać po aktywacji flagę AA i serial SOA na
  primary oraz secondary; brak AA i serial wyższy od primary traktować jako
  błąd, a niższy serial secondary jako kontrolowany stan PENDING.
- [x] Stosować tę samą semantykę w głównym statusie strefy: opóźniony
  secondary pokazywać jako żółty `WARN` w konfigurowalnym oknie propagacji,
  a dopiero po jego przekroczeniu jako czerwony `FAIL`.
- [x] Udostępnić tę samą kontrolę jako odczytowy audyt
  `bind secondary-health`, możliwy do uruchomienia przed zmianą produkcyjną.
- [x] Wymagać niepustego uzasadnienia `--reason` dla każdego commitu ACL,
  grupy secondary i przypisania secondary wykonywanego z CLI.
- [x] Pokazywać w TUI raport wpływu, ryzyko, dodawane/usuwane wpisy,
  blokady oraz odczytowy audyt AA/SOA wybranej pary secondary; przed commitem
  wymagać własnego uzasadnienia operatora.
- [x] Ujednolicić wspólny dialog tekstowy TUI: edytować rzeczywistą wartość
  początkową oraz obsługiwać strzałki, Backspace, Delete, Home i End także
  dla sekwencji xterm/PuTTY.

### Testy awarii i jakość

- [x] Dodać macierz wymuszonych awarii dla zapisu, walidacji, aktywacji i
  rollbacku ACL oraz secondary.
- [x] Uzupełnić analogiczną macierz awarii dla wszystkich operacji cyklu
  życia stref.
- [x] Objąć macierzą operację tworzenia strefy: wymuszone awarie każdego
  zapisu atomowego, aktywacji i kontroli załadowania, zachowanie metadanych
  istniejącej konfiguracji oraz jawny stan `ROLLBACK-FAILED`.
- [x] Objąć macierzą wyłączenie i przywrócenie strefy: awarie zapisu,
  walidacji, aktywacji i kontroli stanu, zachowanie metadanych deklaracji
  oraz indeksu i jawny wynik nieskutecznego rollbacku.
- [x] Objąć macierzą kwarantannę i odtworzenie pakietu: integralność SHA-256,
  awarie każdego zapisu, sprzątanie niekompletnych pakietów oraz zachowanie
  trybu, UID i GID pliku strefy i deklaracji.
- [x] Objąć macierzą migrację deklaracji legacy i relokację zarządzanego
  pliku strefy: awarie każdego zapisu, walidacji i aktywacji, zachowanie
  metadanych, kontrolę docelowej ścieżki oraz `ROLLBACK-FAILED`.
- [x] Sprawdzać zachowanie UID, GID i trybu pliku po sukcesie oraz rollbacku
  ACL/secondary i zapisywać te metadane w stanie przed/po manifestu.
- [x] Ograniczyć manifesty ACL/secondary do jawnej listy pól i automatycznie
  redagować sekret TSIG oraz materiał klucza prywatnego.
- [x] Wymuszać testami rollback po awarii walidacji, aktywacji, bramki
  semantycznej i kontroli operacyjnej secondary oraz raportować
  `ROLLBACK-FAILED`, gdy ponowna aktywacja nie powiedzie się.
- [x] Wykonywać izolowany drill ACL i secondary z prawdziwym
  `named-checkconf`, wymuszoną awarią po aktywacji i pełnym odtworzeniem.
- [x] Walidować tworzenie strefy przez główny plik `named.conf`, aby
  `named-checkconf` otrzymywał pełny kontekst istniejących ACL i list
  `remote-servers`, a nie tylko zarządzany indeks deklaracji stref.
- [x] Wykonać kontrolowany drill cyklu życia na syntetycznej,
  niedelegowanej strefie: utworzenie, wyłączenie, zwykłe odtworzenie,
  kwarantanna, weryfikacja SHA-256 i metadanych, odtworzenie z pakietu oraz
  końcowe wycofanie strefy z aktywnego BIND.
- [x] Wykonać kontrolowany drill trwałego usunięcia wyłącznie na syntetycznym
  pakiecie: kwalifikacja retencji, dry-run, atomowy staging, zweryfikowane
  archiwum ratunkowe, zewnętrzny manifest `PURGED` i kontrola niezmienionego
  stanu pozostałych pakietów oraz BIND.
- [ ] Uzupełnić docstringi publicznego API i zwiększyć pokrycie krytycznych
  ścieżek zapisu. Odczytowy audyt obejmuje całe drzewo, a twarda bramka CI
  chroni już nowe moduły retencji i trwałego usuwania kwarantanny; zakres
  rozszerzono również na transakcje tworzenia, wyłączania i przywracania
  stref, kwarantannę, odtwarzanie pakietów oraz migrację i relokację
  zarządzanych stref. Kolejne moduły należy obejmować stopniowo bez masowego
  przepisywania starszego kodu.

### Automatyzacja GitHub i pakietów

- [x] Dodać GitHub Actions uruchamiające testy bez dostępu do produkcyjnego
  BIND.
- [x] Automatycznie budować wheel i pakiet Debian w czystym Debianie 13,
  uruchamiać testy pakietowe i Lintian, weryfikować metadane oraz brak
  `/etc/bind`, generować SHA-256 i zachowywać wynik jako czasowy artefakt CI.
- [x] Publikować artefakty wyłącznie przez ręczny workflow wymagający
  istniejącego tagu, jawnego potwierdzenia, zielonego `Package build` z tego
  samego commitu, zgodności wersji i SHA-256 oraz osobnego prawa zapisu tylko
  dla joba publikującego GitHub Release.

### Bramka wydania ZoneCTL 4.8.3

- [x] Domknąć raport wpływu, bramki ryzyka, uzasadnienie, manifest,
  prywatność, kontrolę metadanych i rollback ACL/secondary.
- [x] Udostępnić w CLI i TUI odczytowy audyt autorytatywności oraz seriali SOA
  secondary, z osobnym profilem `SKIP` dla RPZ.
- [x] Zweryfikować izolowany rollback prawdziwym `named-checkconf` oraz
  produkcyjny dry-run bez zmiany plików i BIND.
- [x] Potwierdzić końcowy stan DNSSEC strefy testowej: raport i delegacja
  `PASS`, KASP oraz DS `omnipresent`.
- [x] Uruchomić końcową regresję, bramkę prywatności i kontrolę dokumentacji.
- [x] Ustawić wersję 4.8.3 oraz przygotować changelog i notatkę wydania.
- [x] Dodać transakcyjną relokację pliku już zarządzanej strefy ze starego
  katalogu, bez ponownego importowania deklaracji i bez zmiany serialu SOA.
- [x] Zbudować wheel i pakiet Debian, uruchomić Lintian oraz sprawdzić brak
  plików `/etc/bind` w pakiecie.
- [x] Przetestować aktualizację na aktywnym środowisku bez zmiany BIND,
  opublikować zatwierdzony tag i artefakty.

### Bramka wydania ZoneCTL 4.9.0

- [x] Ujednolicić semantyczne kolory stanów TUI, obsługę odświeżania oraz
  formularze rekordów i bezpieczną edycję wieloliniowego SOA.
- [x] Zweryfikować macierze awarii i rollbacku tworzenia, disable/restore,
  kwarantanny oraz migracji i relokacji zarządzanych stref.
- [x] Przeprowadzić produkcyjny drill kompletnego cyklu życia strefy oraz
  oddzielny drill atomowego purge pakietu syntetycznego.
- [x] Dodać retencję kwarantanny, trwały purge z potwierdzeniami, stagingiem,
  archiwum ratunkowym i zewnętrznym manifestem audytowym.
- [x] Objąć nowoczesny core, TUI i CLI rygorystycznym `mypy`, pozostawiając
  `legacy_v220.py` jako jawnie wydzielony wyjątek kompatybilności.
- [x] Dodać izolowane workflow jakości, budowy pakietów i ręcznie
  zatwierdzanego wydania oraz test spójności wersji 4.9.0.
- [x] Zbudować końcowe wheel i DEB 4.9.0, uruchomić Lintian i zweryfikować
  sumy SHA-256 oraz brak plików `/etc/bind`.
- [x] Przetestować aktualizację 4.8.3 → 4.9.0 bez zmiany struktury, metadanych
  ani zawartości `/etc/bind`, przy aktywnej usłudze i poprawnym raporcie.
- [x] Scalić gałąź, utworzyć tag `v4.9.0` i uruchomić zatwierdzony release.

## ZoneCTL 4.9 — semantyczna czytelność TUI

- [x] Zdefiniować centralny kontrakt kolorów stanów: zielony dla stanu
  poprawnego, żółty dla ostrzeżenia lub stanu przejściowego oraz czerwony dla
  błędu, konfliktu albo blokady.
- [x] Kolorować stany KASP względem celu polityki: `omnipresent` jako stan
  osiągnięty, `rumoured` i `unretentive` jako przejściowe, a `hidden` zależnie
  od oczekiwanego celu.
- [x] Zastosować wspólną klasyfikację w statusie DNSSEC, wynikach transakcji,
  komunikatach, panelach kontekstowych, RPZ, migracji oraz audytach
  ACL/secondary.
- [x] Zachować jawne etykiety i symbole, aby kolor nie był jedynym nośnikiem
  informacji, oraz zapewnić poprawny tryb terminala bez kolorów.
- [x] Zweryfikować wizualnie reprezentatywne stany PASS/WARN/FAIL w działającym
  TUI przed rozpoczęciem edytora SOA.

### Bezpieczny edytor SOA

- [x] Otwierać dla rekordu SOA osobny formularz z polami primary NS,
  administrator, refresh, retry, expire, minimum oraz opcjonalnym TTL.
- [x] Pokazywać serial wyłącznie informacyjnie i pozostawić jego podbijanie
  istniejącemu mechanizmowi transakcyjnemu ZoneCTL.
- [x] Walidować nazwy DNS, zakresy liczbowych parametrów SOA i TTL przed
  dodaniem zmiany do bufora.
- [x] Zweryfikować formularz wizualnie i przeprowadzić produkcyjny dry-run bez
  zapisywania zmiany.

## ZoneCTL 4.10 — informacja zwrotna podczas oczekiwania

- [x] Dodać wspólny komponent animowanego wskaźnika pracy TUI dla operacji,
  których czasu zakończenia nie można wiarygodnie określić.
- [x] Pokazywać nazwę bieżącego etapu i upływający czas bez prezentowania
  pozornego procentowego postępu.
- [x] Zastosować wskaźnik najpierw podczas głównego odświeżania stref oraz
  oczekiwania na stan BIND po aktywacji lub rollbacku, a następnie rozszerzyć
  go na kontrole DNSSEC, DS i secondary.
  Integracja głównego odświeżania, odczytowy audyt propagacji secondary,
  transakcyjny zapis zmian rekordów, commity ACL/secondary oraz tworzenie,
  onboarding, migracja i relokacja stref oraz commity DNSSEC/DS są gotowe.
  Ramka obejmuje również odpowiadające im dry-runy transakcyjne BIND.
  Kontrole stanu DNSSEC, delegacji DS i wszystkie dry-runy DNSSEC/DS także
  korzystają ze wspólnego okna.
  Końcowy audyt obejmuje ponadto raport RPZ, onboarding BIND, zbiorczy audyt
  DNSSEC i bramkę DNSSEC przed importem; lokalne parsery pozostają bez modala.
  Dla wiersza RPZ `F3` prowadzi do raportu integracji, a `Enter` zachowuje
  ekran szczegółów i dostępny w nim podgląd rekordów `F3`. W otwartym
  raporcie integracji `F3` i `r` ponawiają kontrolę przez ramkę.
- [x] Przywracać cykliczne odpytywanie głównej pętli po zamknięciu modala, aby
  zakończone odświeżanie samo zdejmowało ramkę bez dodatkowego klawisza.
- [x] Obsłużyć `Home` i `End` na głównej liście jako przejście do
  pierwszej i ostatniej domeny z pominięciem nagłówków grup.
- [x] Pokazywać ramkę podczas odświeżania szczegółów strefy oraz
  wczytywania i parsowania dużych plików rekordów, w tym RPZ.
- [x] Po zakończeniu zastępować animację jawnym wynikiem semantycznym:
  zielonym `PASS`, żółtym `WARN` albo czerwonym `FAIL` wraz z opisem.
- [x] Zapewnić wariant ASCII `| / - \\` dla terminali bez poprawnej obsługi
  znaków Braille'a oraz wyłączać animację w JSON, logach i środowisku
  nieinteraktywnym.
- [x] Nie udostępniać anulowania operacji, dopóki poszczególne transakcje nie
  mają bezpiecznie zdefiniowanego punktu przerwania i rollbacku.
  Audyt AST blokuje nowe commity TUI omijające wspólne, nieanulowalne okno.

### Bramka wydania ZoneCTL 4.10.0

- [x] Objąć wspólną ramką reprezentatywne operacje odczytowe, dry-runy oraz
  transakcje BIND, DNSSEC, RPZ, rekordów i cyklu życia stref.
- [x] Przeprowadzić audyt wizualny na serwerze produkcyjnym, w tym odświeżanie,
  duży plik RPZ, zapis rekordu i raport DNSSEC.
- [x] Usunąć zależność zamykania ramki głównego odświeżania od dodatkowego
  naciśnięcia klawisza i zabezpieczyć zachowanie testem regresji.
- [x] Zbudować końcowe wheel i DEB 4.10.0, zweryfikować ich sumy, metadane oraz
  brak plików `/etc/bind`, a następnie przetestować aktualizację z 4.9.0-1.
  Aktualizacja produkcyjna zachowała konfigurację BIND; jedyną współbieżną
  zmianę treści przypisano na podstawie czasu i dziennika do prawidłowego
  przebiegu timera CERT Polska RPZ. Walidacja BIND i audyt TUI zakończyły się
  powodzeniem.
- [x] Scalić gałąź, utworzyć tag `v4.10.0` i uruchomić zatwierdzony release.

Wydania `4.10.x` pozostają linią stabilizacyjną przeznaczoną na poprawki
błędów, bezpieczeństwa i pakietów. Rozszerzenia polityk DNSSEC/KASP oraz
wielojęzyczność są planowane dla ZoneCTL 5.0.

## ZoneCTL 4.11 — jakość, odporność i dokumentacja

- [x] Wprowadzić automatyczne formatowanie Ruff, lint i analizę statyczną do
  lokalnej oraz githubowej bramki jakości.
- [x] Dodać izolowane testy integracyjne rzeczywistych narzędzi BIND dla
  poprawnych i błędnych konfiguracji `inline-signing`.
- [x] Zweryfikować responsywność TUI na małym VT100, typowym xtermie i
  szerokim terminalu, w trybie UTF-8 i ASCII.
- [x] Opublikować po polsku i angielsku procedury odtwarzania po nieudanej
  transakcji, awarii BIND oraz utracie hosta.
- [x] Udokumentować i walidować przykłady wszystkich typów rekordów
  obsługiwanych przez formularze ZoneCTL.
- [x] Uzupełnić syntetyczną galerię o ACL/secondary, udaną transakcję i
  kontrolowany rollback, bez danych środowiska produkcyjnego.

### Bramka wydania ZoneCTL 4.11.0

- [x] Uruchomić pełne testy jednostkowe i integracyjne, Ruff, mypy, kontrolę
  prywatności oraz budowę wheel i pakietu DEB.
- [x] Scalić przygotowanie wydania, utworzyć tag `v4.11.0` i uruchomić
  zatwierdzony workflow publikacyjny.

## ZoneCTL 4.12 — audyt i obsługa transakcji

- [x] Przeprowadzić odczytowy audyt istniejących manifestów, backupów,
  identyfikatorów i historii oraz zdefiniować wersjonowany, prywatnościowy
  kontrakt `zonectl.audit/v1` w `docs/AUDIT_4_12_CONTRACT.md`.
- [x] Dodać bezpieczny magazyn kopert `zonectl.audit/v1`: allowlistę i
  walidację danych, blokadę międzyprocesową, append z `fsync`, stałe tryby
  `0750/0640`, ochronę przed symlinkami, diagnostykę uszkodzonych linii oraz
  jawny dry-run i atomowe, potwierdzane zastosowanie retencji.
- [x] Podłączyć bazowy `TransactionEngine` do par START/RESULT dla walidacji,
  weryfikacji, zastosowania pliku strefy i ręcznego rollbacku, zachowując
  dotychczasowe manifesty oraz polecenia historii bez zmian.
- [x] Dodać spójny rejestr audytowy operacji z czasem, strefą, rodzajem,
  wynikiem, identyfikatorem transakcji i informacją o rollbacku. Adaptery
  obejmują bazowy silnik oraz rodziny ACL/secondary, DNSSEC, RPZ i pełny cykl
  życia stref, zachowując dotychczasowe manifesty i mechanizmy rollbacku.
- [x] Udostępnić odczytowe CLI audytu z listą ostatnich operacji, szczegółami
  pary START/RESULT, filtrowaniem po strefie, statusie, rodzaju operacji i
  zakresie czasu oraz eksportem tekstowym i JSON.
- [x] Udostępnić odczytową przeglądarkę audytu w TUI z tym samym zakresem
  filtrów i bez zależności od dostępności konfiguracji BIND.
- [x] Przed zatwierdzeniem zapisu rekordów pokazywać zwarte podsumowanie zmian:
  pliki,
  rekordy, serial, planowane walidacje, backup oraz operacje BIND.
- [x] Zapewnić bezpieczny eksport audytu w JSON i formacie tekstowym oraz
  zdefiniować retencję bez ujawniania sekretów i materiału kluczy DNSSEC.
- [x] Dodać opcjonalne lokalne repozytorium Git jako dodatkową historię
  zarządzanych plików stref, nigdy jako zamiennik backupu transakcyjnego.
- [x] Domyślnie wykluczyć automatycznie aktualizowane strefy RPZ z opcjonalnej
  historii Git.
- [x] Opublikować syntetyczny zrzut przeglądarki audytu po pełnej kontroli
  kadrowania, metadanych i identyfikatorów produkcyjnych.
- [x] Objąć przeglądarkę, filtry i podsumowania testami prywatności, małych
  terminali oraz uszkodzonych wpisów audytu; eksport i retencja mają osobne
  testy warstwy CLI i magazynu.

### Bramka wydania ZoneCTL 4.12.0

- [ ] Uruchomić pełne testy jednostkowe i integracyjne, Ruff, mypy, kontrolę
  prywatności oraz budowę wheel i pakietu DEB.
- [ ] Zweryfikować instalację pakietu 4.12.0 na środowisku testowym bez zmian
  produkcyjnej konfiguracji BIND.
- [ ] Scalić przygotowanie wydania do `main`.
- [ ] Utworzyć tag `v4.12.0` i uruchomić zatwierdzony workflow publikacyjny
  dopiero po wszystkich wcześniejszych kontrolach.

## Rozwój po osiągnięciu pełnej funkcjonalności podstawowej

Poniższe rozszerzenia nie mogą opóźniać stabilizacji podstawowych operacji
ZoneCTL: zarządzania strefami i rekordami, DNSSEC, secondary, ACL, RPZ,
walidacji, backupu i rollbacku.

### Konfigurowalne polityki DNSSEC/KASP

- [ ] Wykrywać nazwane polityki `dnssec-policy` dostępne w konfiguracji BIND
  i prezentować je operatorowi bez ujawniania kluczy prywatnych.
- [ ] Umożliwić wybór całej, wcześniej zdefiniowanej polityki KASP podczas
  włączania DNSSEC zamiast prostego, podatnego na błędy wyboru algorytmu.
- [ ] Przed zatwierdzeniem pokazywać algorytm, model kluczy KSK/ZSK lub CSK,
  parametry publikacji, harmonogram rolloveru oraz zgodność z możliwościami
  używanej wersji BIND.
- [ ] Ostrzegać i domyślnie blokować polityki używające algorytmów
  przestarzałych, niezalecanych lub nieobsługiwanych przez strefę nadrzędną.
- [ ] Migrację aktywnej strefy pomiędzy politykami realizować wyłącznie jako
  osobną transakcję z planem, dry-runem, kontrolą DNSKEY/DS/KASP, okresem
  przejściowym i rollbackiem.
- [ ] Zachować `dnssec-policy default` jako bezpieczną i prostą opcję domyślną.

### Internationalization (i18n)

- [ ] Oddzielić komunikaty użytkownika od kodu programu.
- [ ] Zachować język polski jako domyślny i dodać język angielski.
- [ ] Obsłużyć tłumaczenia CLI, TUI, ostrzeżeń i błędów przez `gettext`.
- [ ] Dodać wybór języka w konfiguracji.
- [ ] Opcjonalnie wykrywać język z locale systemu.
- [ ] Testować kompletność katalogów tłumaczeń i oba warianty interfejsu.

## Pomysły po 4.4

- [x] Dodać lokalne repozytorium Git jako dodatkową historię zmian stref.
- [x] Nie traktować Git jako zamiennika backupu Veeam ani backupów
  transakcyjnych ZoneCTL.
- [x] Domyślnie wykluczyć automatycznie aktualizowaną strefę RPZ z historii
  Git.
### Pierwsze uruchomienie i import środowiska

- [x] Odczytowy raport gotowości klasyfikujący strefy jako zarządzane,
  legacy, zewnętrzne lub zablokowane.
- [x] Widok raportu w TUI pod klawiszem F2, bez automatycznego importu.
- [x] Lista kandydatów z planem F3 i bezpiecznym dry-run F4.
- [x] Kontrolowany import F6 z ponownym dry-run, potwierdzeniem nazwy,
  backupem, walidacją, aktywacją i rollbackiem.
- [x] Szczegółowa klasyfikacja blokad: DNSSEC, RPZ, secondary, duplikaty
  i pozostałe przypadki wymagające decyzji operatora.
- [x] Ekran F1 „O programie” zachowujący autorstwo i historię projektu bez
  odbierania miejsca panelom operacyjnym.
- [x] Osobny, odczytowy profil importu istniejących deklaracji DNSSEC:
  lista F5, plan F3 i dry-run F4 bez operacji na kluczach/KASP/DS.
- [x] Produkcyjny import deklaracji DNSSEC F6 z bramkami PASS przed i po
  `rndc reconfig`, porównaniem polityki/DNSKEY/DS oraz rollbackiem transakcji.
- [x] Zbiorczy audyt F7 gotowości pozostałych stref DNSSEC, bez zmian i bez
  importu masowego.
