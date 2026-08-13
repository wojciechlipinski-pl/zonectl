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
- [ ] Umożliwić wybór grupy, serwerów NS, administratora SOA i parametrów
  czasowych SOA.
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
- [ ] Dodać konfigurowalny okres retencji przed trwałym usunięciem.
- [ ] Trwałe usunięcie udostępnić wyłącznie jako osobną operację
  administracyjną.

### Wymagania bezpieczeństwa 4.4

- [x] Dodać testy integracyjne tworzenia, wyłączania i przywracania z
  odseparowaną instancją BIND.
- [ ] Testować awarie `named-checkzone`, `named-checkconf`, `rndc reconfig`
  i weryfikacji załadowania.
- [ ] Potwierdzić rollback po awarii na każdym etapie cyklu życia strefy.
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
- [ ] Blokować usunięcie ostatniego wpisu administracyjnego, wpisu wymaganego
  przez aktywny transfer albo całej używanej ACL bez osobnego potwierdzenia i
  raportu skutków.
- [ ] Rejestrować w manifeście operatora, przyczynę, stan przed i po zmianie
  oraz listę stref, których dotyczyła modyfikacja ACL lub secondary.

## Jakość techniczna

- [x] Zachować względną nazwę właściciela i komentarz inline po edycji.
- [ ] Uzupełnić docstringi publicznych klas i metod.
- [ ] Rozszerzyć pokrycie testami krytycznych ścieżek zapisu.
- [ ] Dodać statyczną analizę typów.
- [ ] Dodać automatyczne formatowanie i lint.
- [x] Dodać testy integracyjne z odseparowaną konfiguracją i prawdziwymi
  narzędziami walidacyjnymi BIND, bez kontaktu z produkcyjnym `rndc`.
- [ ] Dodać testy stref `inline-signing`.
- [ ] Zweryfikować skróty klawiszowe w kolejnych typach terminali.
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
- [x] Dodać do raportu CLI etap procesu, postęp, lokalny termin następnej
  kontroli i jednoznaczną blokadę publikacji DS do osiągnięcia gotowości KASP.
- [x] Sprawdzać publikację DS oraz pełny łańcuch zaufania DNSSEC.
- [x] Dodać odczytową kontrolę DS przez wiele resolverów oraz zgodności DNSKEY
  i RRSIG na wszystkich serwerach autorytatywnych.
- [x] Dodać kontrolowane potwierdzenie publikacji DS w KASP, blokowane bez
  wyniku `PASS` z pełnej kontroli delegacji.
- [x] Dodać w TUI odczytowy ekran etapu DNSSEC, KASP, propagacji DS oraz
  zgodności serwerów autorytatywnych.
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

- [ ] Dodać przykłady obsługi każdego wspieranego typu rekordu.
- [ ] Dodać bezpieczne, syntetyczne zrzuty ekranów TUI generowane bez dostępu
  do konfiguracji produkcyjnej.
- [ ] Przygotować instrukcję odtwarzania po awarii.
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
- [ ] Dodać kreator pierwszego uruchomienia w TUI z podsumowaniem wykrytej
  konfiguracji i możliwością pominięcia importu.
- [ ] Przygotować plan importu istniejących stref, ACL, grup secondary i RPZ;
  nie modyfikować automatycznie obcych plików konfiguracyjnych.
- [ ] Każdy import wykonywać przez diff, backup, `named-checkconf`, dry-run,
  jawne potwierdzenie, manifest i rollback.

### Opcjonalna integracja CERT Polska RPZ

- [x] Zachować dotychczasowy pomiar wieku RPZ w sekundach/minutach i wykrywać
  istniejący timer oraz aktualizator jako tryb `EXTERNAL`.
- [x] Dodać odczytowy panel F3 integracji RPZ w TUI: tryb zarządzania, stan,
  wiek, serial, liczba węzłów, timer, usługa i ścieżka aktualizatora.
- [ ] Pokazywać wspólny stan `ACTIVE`, `DELAYED`, `STALE`, `FAILED` lub
  `DISABLED`, serial, liczbę węzłów, ostatni wynik usługi i następne uruchomienie.
- [ ] Dodać opcjonalny tryb `MANAGED`: instalacja aktualizatora i unitów systemd
  wyłącznie po planie, dry-runie oraz jawnym zatwierdzeniu.
- [ ] Zachować zalecany interwał pięciu minut, walidację `named-checkzone`,
  ochronę seriala, atomową podmianę, backup, kontrolowany reload i rollback.
- [ ] Nie przejmować istniejącego mechanizmu `EXTERNAL` bez osobnej migracji.

### Bezpieczne materiały demonstracyjne

Materiały promocyjne i koncepcyjne zostały przygotowane. Deterministyczny
generator danych demonstracyjnych został przesunięty poza krytyczny zakres 4.8.

- [ ] (później) Dodać deterministyczny generator demonstracyjnego stanu TUI, który nie
  czyta `/etc/bind`, `/var/lib/bind`, nazw hostów ani danych operatora.
- [ ] Przygotować porównawczy zestaw publikacyjny: dwa wierne, zanonimizowane
  zrzuty bieżącego TUI oraz dwa obrazy jednoznacznie opisane jako koncepcja
  docelowego interfejsu.
- [ ] Wygenerować ekrany: lista stref, rekordy, DNSSEC, ACL, secondary oraz
  wynik transakcji.
- [ ] Zapisać obrazy w `docs/images/` i osadzić je w obu wersjach README.
- [ ] Dodać test wykrywający w obrazach/metadanych i plikach demonstracyjnych
  zabronione nazwy produkcyjne.

### Docelowy wygląd TUI

Szczegółowe kryteria zgodności z opublikowanymi grafikami określa
`docs/TUI_VISUAL_CONTRACT.md`.

- [x] Rozpocząć przebudowę ekranu głównego na responsywny układ panelowy: lista stref,
  zaznaczenie aktywnego wiersza oraz panel szczegółów wybranej strefy.
- [ ] Ujednolicić widoki planu, dry-runu, ostrzeżenia, sukcesu i rollbacku,
  zachowując tę samą hierarchię informacji i semantykę kolorów.
- [ ] Stosować stałe paski tytułu i klawiszy funkcyjnych oraz skróty w stylu
  Midnight Commandera: F3 podgląd, F4 edycja, Insert dodawanie, F8/Delete
  usuwanie i F10 powrót.
- [x] Ujednolicić ekran główny z kontraktem wizualnym: turkusowe zaznaczenie,
  nagłówki kolumn, separatory sekcji i pasek klawiszy w stylu MC.
- [ ] Pokazywać najważniejszy stan operacji, blokady bezpieczeństwa, postęp i
  następny krok bez konieczności analizowania surowego raportu.
- [ ] Zapewnić poprawne skalowanie, zawijanie i przewijanie na małych
  terminalach, bez utraty dostępu do potwierdzeń i komunikatów błędów.
- [ ] Traktować grafiki koncepcyjne wyłącznie jako wzorzec projektu; publiczne
  zrzuty oznaczane jako działająca aplikacja muszą pochodzić z rzeczywistego
  renderera ZoneCTL na danych demonstracyjnych.

### Zabezpieczenia ACL i secondary

- [ ] Blokować usunięcie ostatniego wpisu administracyjnego oraz wpisu
  wymaganego przez aktywny transfer.
- [ ] Wymagać rozszerzonego potwierdzenia przy opróżnianiu używanej ACL lub
  odłączaniu ostatniej pary secondary od strefy.
- [ ] Rozszerzyć manifest o operatora, przyczynę, stan przed i po operacji oraz
  pełną listę dotkniętych stref.

### Testy awarii i jakość

- [ ] Dodać macierz wymuszonych awarii dla zapisu, walidacji, aktywacji i
  rollbacku cyklu życia stref, ACL oraz secondary.
- [ ] Sprawdzać zachowanie właściciela, grupy i trybu pliku po sukcesie oraz
  rollbacku.
- [ ] Uzupełnić docstringi publicznego API i zwiększyć pokrycie krytycznych
  ścieżek zapisu.

### Automatyzacja GitHub i pakietów

- [ ] Dodać GitHub Actions uruchamiające testy bez dostępu do produkcyjnego
  BIND.
- [ ] Automatycznie budować wheel i pakiet Debian oraz uruchamiać Lintian.
- [ ] Publikować artefakty dopiero dla podpisanego lub jawnie zatwierdzonego
  tagu wydania.

## Przyszłe rozszerzenie — internationalization (i18n)

- [ ] Oddzielić komunikaty użytkownika od kodu programu.
- [ ] Zachować język polski jako domyślny i dodać język angielski.
- [ ] Obsłużyć tłumaczenia CLI, TUI, ostrzeżeń i błędów przez `gettext`.
- [ ] Dodać wybór języka w konfiguracji.
- [ ] Opcjonalnie wykrywać język z locale systemu.
- [ ] Testować kompletność katalogów tłumaczeń i oba warianty interfejsu.

## Pomysły po 4.4

- [ ] Rozważyć lokalne repozytorium Git jako dodatkową historię zmian stref.
- [ ] Nie traktować Git jako zamiennika backupu Veeam ani backupów
  transakcyjnych ZoneCTL.
- [ ] Domyślnie wykluczyć automatycznie aktualizowaną strefę RPZ z historii
  Git.
### Pierwsze uruchomienie i import środowiska

- [x] Odczytowy raport gotowości klasyfikujący strefy jako zarządzane,
  legacy, zewnętrzne lub zablokowane.
- [x] Widok raportu w TUI pod klawiszem F2, bez automatycznego importu.
- [x] Lista kandydatów z planem F3 i bezpiecznym dry-run F4.
- [x] Kontrolowany import F6 z ponownym dry-run, potwierdzeniem nazwy,
  backupem, walidacją, aktywacją i rollbackiem.
