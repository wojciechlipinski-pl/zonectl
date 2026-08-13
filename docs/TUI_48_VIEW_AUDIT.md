# Audyt widoków TUI względem koncepcji ZoneCTL 4.8

Stan odniesienia: commit `3b7c4d2`. Kryteria pochodzą z
`docs/TUI_VISUAL_CONTRACT.md` i opublikowanych grafik koncepcyjnych.

## Zgodne lub przebudowane

- ekran główny stref, responsywny panel oraz pełny ekran szczegółów strefy;
- ekran F1 „O programie”;
- raport pierwszego uruchomienia „Środowisko BIND” w układzie dwukolumnowym
  oraz listy importu BIND/DNSSEC;
- lista bezpiecznego onboardingu DNSSEC oraz zbiorczy audyt gotowości DNSSEC;
- status strefy DNSSEC: polityka, KASP, DS, delegacja i wskazówki operatora;
- wyniki importu: układ transakcji i stanu operacyjnego;
- widok rekordów DNS: lista, pełnowierszowe zaznaczenie, panel szczegółów i pasek MC.

## Pokrycie zakończone

- oczekujące zmiany, diff, eksport oraz operacje masowe;
- plany, wyniki i komunikaty operacyjne przez wspólny renderer 4.8;
- ACL, grupy secondary, przypisanie strefy i ich pełnoekranowe edytory;
- migracja deklaracji zarządzanej strefy;
- formularze dodawania i edycji rekordów z panelem podglądu;
- sesja wielu stref;
- komunikaty przewijane, błędy oraz ekrany tylko do odczytu.

Jednowierszowe pola tekstowe i potwierdzenia pozostają krótkotrwałymi dialogami,
a nie osobnymi ekranami biznesowymi. Dziedziczą kontekst ekranu znajdującego się
pod nimi.

Każdy przebudowany ekran ma zachować dotychczasowe bramki bezpieczeństwa,
model potwierdzeń oraz transakcyjny zapis. Zmieniany jest renderer i hierarchia
informacji, nie semantyka operacji.
