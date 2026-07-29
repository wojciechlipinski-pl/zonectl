# Rejestr decyzji architektonicznych

ADR-001: Standardowy układ pakietu Python

Status: przyjęta

Projekt został przeniesiony do układu:

src/elkman_dns/

Powody:

rozdzielenie kodu projektu od katalogu roboczego,
poprawne testowanie zainstalowanego pakietu,
zgodność ze współczesnymi narzędziami Python.
ADR-002: Transakcyjny zapis stref

Status: przyjęta

Zmiana strefy nie powinna oznaczać natychmiastowego, niekontrolowanego
nadpisania pliku.

Proces musi obejmować:

wykrycie zmian,
walidację,
zapis,
przeładowanie,
wynik operacji.
ADR-003: NO-CHANGE nie jest błędem

Status: przyjęta

Brak różnic pomiędzy stanem początkowym i końcowym powinien być
rozpoznawany przed COMMIT.

Nie należy wykonywać zbędnego zapisu ani zwiększać SOA.

ADR-004: Kontrola załadowanego SOA

Status: przyjęta

Dla stref inline-signing stan pliku i stan widoczny w działającym BIND
mogą wymagać dodatkowego sprawdzenia.

Dlatego projekt uwzględnia kontrolę numeru SOA załadowanego przez serwer.

ADR-005: Wydzielanie odpowiedzialności z CursesApp

Status: przyjęta

Wraz z rozwojem TUI wydzielono między innymi:

dialogi,
renderer rekordów,
skróty klawiszowe,
edytor rekordów,
dialog nowego rekordu,
kontroler widoku rekordów.

Celem jest ograniczenie klasy głównej i zwiększenie testowalności.

ADR-006: Własna interpretacja F2

Status: przyjęta

Niektóre terminale zwracają F2 jako wielobajtową sekwencję ESC zamiast
curses.KEY_F2.

Projekt rozpoznaje sekwencję ESC [ 12 ~, aby zapis działał na
docelowym terminalu.

Decyzję można zmienić dopiero po potwierdzeniu, że nowy mechanizm działa
we wszystkich wspieranych środowiskach.

Szablon kolejnej decyzji
## ADR-NNN: Nazwa decyzji

**Status:** proponowana / przyjęta / wycofana

### Kontekst

...

### Decyzja

...

### Konsekwencje

...
