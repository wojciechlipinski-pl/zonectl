# Roadmap

Poniższe pozycje są propozycjami rozwoju. Nie oznaczają,
że zostały zatwierdzone lub rozpoczęte.

Najbliższe zadania
 Dodać test regresyjny parsera sekwencji F2.
 Dodać test zapisu z widoku Pending Changes.
 Dodać test odświeżenia modelu po COMMIT.
 Uzupełnić docstringi publicznych klas i metod.
 Ujednolicić obsługę błędów UI i warstwy core.
 Zweryfikować wszystkie skróty w różnych terminalach.
 Opisać procedurę rollbacku po błędzie reloadu BIND.
Rozwój funkcjonalny
 Cofanie ostatniej zmiany w bieżącej sesji.
 Historia zmian i transakcji.
 Eksport zmian przed COMMIT.
 Podgląd różnic w formacie unified diff.
 Obsługa wielu stref w jednej sesji.
 Rozbudowane filtrowanie rekordów.
 Walidacja wartości zależna od typu rekordu.
 Integracja z repozytorium Git przechowującym strefy.
 Tryb tylko do odczytu.
 Mechanizm blokowania równoległej edycji.
 Profile kontroli zdrowia zależne od przeznaczenia strefy.
 Profil RPZ: składnia, stan załadowania i świeżość lokalnego pliku.
Jakość
 Pokrycie testami krytycznych ścieżek zapisu.
 Statyczna analiza typów.
 Automatyczne formatowanie i lint.
 Testy integracyjne z odseparowaną instancją BIND.
 Testy zachowania po nieudanym named-checkzone.
 Testy zachowania po nieudanym rndc reload.
 Testy stref inline-signing.
Dokumentacja
 Przykłady obsługi każdego wspieranego typu rekordu.
 Zrzuty ekranów TUI.
 Instrukcja odtwarzania po awarii.
 Procedura wydania nowej wersji.
 Lista wspieranych wersji Pythona, BIND i systemów.
