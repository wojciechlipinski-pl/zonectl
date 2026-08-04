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
- [ ] Wykonać backup konfiguracji BIND i materiału kluczowego przed zmianą.
- [ ] Aktywować `dnssec-policy default` oraz `inline-signing` transakcyjnie,
  z walidacją `named-checkconf`, kontrolowanym `rndc reconfig` i rollbackiem.
- [ ] Monitorować utworzenie kluczy, podpisanie strefy i stan rekordów DNSKEY.
- [ ] Wyświetlać rekord DS przeznaczony do przekazania rejestratorowi.
- [ ] Sprawdzać publikację DS oraz pełny łańcuch zaufania DNSSEC.
- [ ] Dodać osobną, wieloetapową i bezpieczną procedurę wyłączenia DNSSEC.
- [ ] Chronić operatora przed przedwczesnym dodaniem lub usunięciem DS.
- [ ] Pokryć włączanie, rotację, awarie i rollback testami integracyjnymi BIND.

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
