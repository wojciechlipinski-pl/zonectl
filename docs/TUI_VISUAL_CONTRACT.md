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
- ciemny turkus `#008787` dla klawiszy na jasnym pasku, gdy terminal zgłasza
  paletę 256 kolorów; przy mniejszej palecie dozwolony jest czytelny fallback;
- stały pasek klawiszy zgodny z Midnight Commanderem;
- pasek pokazuje wyłącznie działające akcje; `F8 Usuń` pojawi się dopiero po
  podłączeniu bezpiecznego, transakcyjnego cyklu usunięcia strefy;
- automatyczny powrót do widoku jednokolumnowego na małym terminalu.

## Terminal i typografia

- zalecane środowisko to `TERM=xterm-256color` i co najmniej 256 kolorów;
- aplikacja nie może samodzielnie nadpisywać `TERM`;
- krój oraz rozmiar fontu ustawia klient terminalowy, nie curses;
- wzorzec to czytelny font monospace 12–14 pt; pogrubienie jest semantyczne i
  dotyczy tytułów, nagłówków, zaznaczenia oraz kluczowych statusów, a nie całego
  interfejsu;
- test wizualny wydania obejmuje PuTTY/xterm-256color oraz wariant 8-kolorowy.

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
## Autorstwo i historia

Główny ekran zachowuje przestrzeń dla danych operacyjnych. Informacje o
autorstwie, udziale AI, historii projektu, wersji i repozytorium są stale
dostępne pod standardowym klawiszem `F1 — O programie`.

Ekran F1 stosuje ten sam kontrakt wizualny co widok główny: odwróconą belkę
tytułową, turkusowe nagłówki, dwukolumnowy układ na szerokim terminalu,
wariant responsywny dla małych okien oraz dolny pasek w stylu MC.
