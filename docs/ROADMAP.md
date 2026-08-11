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
- [ ] Aktualizować `/etc/bind/zonectl-zones.conf` jako indeks zawierający
  dokładnie jeden `include` dla każdej deklaracji zarządzanej przez ZoneCTL.
- [ ] Wymagać backupu `named.conf.local`, indeksu i deklaracji, walidacji
  `named-checkconf`, kontrolowanego `rndc reconfig`, potwierdzenia
  `rndc zonestatus` oraz pełnego rollbacku po błędzie.
- [x] Domyślnie blokować migrację RPZ, secondary i stref DNSSEC; obsłużyć je
  dopiero przez jawne, osobne profile migracyjne.
- [ ] Udostępnić dry-run i migrację pojedynczej strefy w CLI oraz TUI, bez
  automatycznej migracji zbiorczej produkcyjnej konfiguracji.

### Zarządzanie ACL i serwerami secondary

- [ ] Zinwentaryzować źródła definicji ACL BIND oraz ich użycie w
  `allow-query`, `allow-recursion`, `allow-transfer`, `allow-notify`,
  `also-notify` i `primaries`.
- [ ] Dodać odczytowy widok listy zaufanych sieci i hostów (`trusted`) wraz z
  plikiem źródłowym, numerem linii i miejscami użycia każdej ACL.
- [ ] Dodać edycję `trusted` w CLI i TUI z walidacją adresów IPv4, IPv6,
  prefiksów CIDR, negacji oraz nazw dozwolonych elementów ACL.
- [ ] Dodać zarządzanie nazwanymi grupami serwerów secondary/slave używanymi
  przez `also-notify`, `allow-transfer`, `allow-notify` i `primaries`, bez
  powielania adresów w deklaracjach poszczególnych stref.
- [ ] Udostępnić przypisywanie strefy do grupy secondary oraz odczytowy raport
  pokazujący, które strefy korzystają z danego serwera lub grupy.
- [ ] Każdą zmianę ACL wykonywać przez planowany diff, backup, atomowy zapis,
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
- [ ] Dodać zrzuty ekranów TUI.
- [ ] Przygotować instrukcję odtwarzania po awarii.
- [ ] Opisać procedurę wydania nowej wersji.
- [ ] Prowadzić listę wspieranych wersji Pythona, BIND i systemów.
- [ ] Przygotować publiczną dokumentację w języku polskim i angielskim.
- [ ] Dodać `README.en.md` oraz angielskie instrukcje instalacji i CLI.

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
