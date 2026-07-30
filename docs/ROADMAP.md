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

- [ ] Dodać test zapisu z widoku Pending Changes.
- [ ] Dodać test odświeżenia modelu po COMMIT.
- [x] Dodać test zachowania po nieudanym `named-checkzone`.
- [x] Dodać test zachowania po nieudanym `rndc reload`.
- [x] Potwierdzić automatyczny rollback pliku strefy po błędzie reloadu.
- [ ] Opisać procedurę ręcznego rollbacku po błędzie reloadu BIND.
- [ ] Ujednolicić prezentację błędów warstwy UI i core.

## Etap 2 — kontrola i historia zmian

- [ ] Dodać podgląd różnic w formacie unified diff przed COMMIT.
- [ ] Dodać eksport zmian przed COMMIT.
- [ ] Rozbudować historię zmian i transakcji.
- [ ] Dodać cofanie ostatniej zmiany w bieżącej sesji.
- [ ] Dodać tryb tylko do odczytu.
- [ ] Dodać mechanizm blokowania równoległej edycji.

## Etap 3 — operacje masowe i wiele stref

- [ ] Dodać rozbudowane filtrowanie rekordów.
- [ ] Dodać walidację wartości zależną od typu rekordu.
- [ ] Dodać operacje masowe `SELECT`, `SET` i `DELETE`.
- [ ] Zapisywać operację masową jako jedną transakcję.
- [ ] Dodać obsługę wielu stref w jednej sesji.
- [ ] Rozważyć integrację z repozytorium Git przechowującym strefy.

## Jakość techniczna

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
