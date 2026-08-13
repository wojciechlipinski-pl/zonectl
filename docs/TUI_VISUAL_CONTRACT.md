# Kontrakt wizualny TUI ZoneCTL 4.8

Opublikowane grafiki `03-concept-main-4.8.png` oraz
`04-concept-transaction-4.8.png` są specyfikacją kierunku interfejsu 4.8.
Implementacja może upraszczać ornamenty zależne od terminala, ale nie może
zmieniać poniższej hierarchii ani modelu interakcji.

## Ekran główny

- odwrócony, stały pasek tytułu z wersją i nazwą widoku;
- lista stref w górnej części oraz pełnowierszowe zaznaczenie aktywnej pozycji;
- szczegóły zaznaczonej strefy w dolnej części, oddzielone poziomą linią;
- dolny panel podzielony na dane strefy i stan operacyjny;
- cyjan dla nagłówków, zielony dla powodzenia, żółty dla ostrzeżenia i czerwony
  dla błędu lub blokady;
- stały pasek klawiszy zgodny z Midnight Commanderem;
- pasek pokazuje wyłącznie działające akcje; `F8 Usuń` pojawi się dopiero po
  podłączeniu bezpiecznego, transakcyjnego cyklu usunięcia strefy;
- automatyczny powrót do widoku jednokolumnowego na małym terminalu.

## Wynik transakcji

- jednoznaczny nagłówek rodzaju operacji i jej wyniku;
- po lewej identyfikacja transakcji oraz lista etapów;
- po prawej duży komunikat sukcesu, blokady albo rollbacku;
- operator ma widzieć walidację, backup i rollback bez analizowania logu;
- identyczna semantyka kolorów jak na ekranie głównym.

## Kryterium wydania

Przed wydaniem 4.8 należy porównać rzeczywiste ekrany aplikacji z grafikami
koncepcyjnymi. Odstępstwo w układzie, hierarchii lub klawiszach wymaga jawnej
decyzji projektowej, a nie przypadkowej ewolucji renderera.
