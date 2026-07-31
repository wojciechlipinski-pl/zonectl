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

- [ ] Dodać kreator nowej domeny w TUI i odpowiadające mu polecenie CLI.
- [x] Walidować nazwę domeny i odrzucać strefy już istniejące.
- [ ] Umożliwić wybór grupy, serwerów NS, administratora SOA i parametrów
  czasowych SOA.
- [x] Generować minimalny plik strefy z SOA, NS i poprawnym serialem.
- [ ] Opcjonalnie dodawać rekordy A/AAAA dla apexu i `www`.
- [ ] Dodawać deklarację `primary` do zarządzanego fragmentu konfiguracji
  BIND bez modyfikowania obcych sekcji.
- [ ] Przed aktywacją wykonywać `named-checkzone` i `named-checkconf`.
- [ ] Aktywować strefę przez kontrolowane `rndc reconfig` i potwierdzać jej
  załadowanie.
- [x] Zapisywać manifest utworzenia, backup konfiguracji i wynik każdego
  etapu.
- [x] Automatycznie wycofywać plik oraz konfigurację po błędzie aktywacji.

### Wyłączanie i przywracanie

- [ ] Dodać odwracalną operację wyłączenia strefy bez usuwania jej danych.
- [ ] Przed wyłączeniem zapisywać plik strefy, konfigurację i manifest.
- [ ] Usuwać deklarację strefy z aktywnej konfiguracji przez transakcję.
- [ ] Potwierdzać przez BIND, że wyłączona strefa nie jest już obsługiwana.
- [ ] Prowadzić listę stref wyłączonych wraz z datą, operatorem i przyczyną.
- [ ] Umożliwić przywrócenie wyłączonej strefy po pełnej walidacji.

### Kwarantanna i usuwanie

- [ ] Wymagać wcześniejszego wyłączenia strefy przed jej usunięciem.
- [ ] Wymagać podwójnego potwierdzenia, w tym wpisania pełnej nazwy domeny.
- [ ] Przenosić dane do chronionej kwarantanny zamiast wykonywać bezpośrednie
  i nieodwracalne usunięcie.
- [ ] Zapisywać sumy kontrolne, manifest i kompletny pakiet odtworzeniowy.
- [ ] Umożliwić odtworzenie strefy z kwarantanny.
- [ ] Dodać konfigurowalny okres retencji przed trwałym usunięciem.
- [ ] Trwałe usunięcie udostępnić wyłącznie jako osobną operację
  administracyjną.

### Wymagania bezpieczeństwa 4.4

- [ ] Dodać testy integracyjne tworzenia, wyłączania i przywracania z
  odseparowaną instancją BIND.
- [ ] Testować awarie `named-checkzone`, `named-checkconf`, `rndc reconfig`
  i weryfikacji załadowania.
- [ ] Potwierdzić rollback po awarii na każdym etapie cyklu życia strefy.
- [ ] Wykluczyć przypadkowe zarządzanie automatyczną strefą RPZ jak zwykłą
  domeną.
- [ ] Uwzględnić strefy DNSSEC i `inline-signing`.
- [ ] Udokumentować współpracę z backupem Veeam jako głównym zabezpieczeniem
  maszyny wirtualnej.

## Jakość techniczna

- [x] Zachować względną nazwę właściciela i komentarz inline po edycji.
- [ ] Uzupełnić docstringi publicznych klas i metod.
- [ ] Rozszerzyć pokrycie testami krytycznych ścieżek zapisu.
- [ ] Dodać statyczną analizę typów.
- [ ] Dodać automatyczne formatowanie i lint.
- [ ] Dodać testy integracyjne z odseparowaną instancją BIND.
- [ ] Dodać testy stref `inline-signing`.
- [ ] Zweryfikować skróty klawiszowe w kolejnych typach terminali.

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
