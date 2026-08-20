# Plan zabezpieczeń ACL i secondary

Status: etapy 1–3 wdrożone — odczytowy raport wpływu `bind access-impact`,
integracja z plannerami, klasyfikacja przypisań stref oraz bramka blokująca
zwykły commit ryzyka `HIGH`, w tym odłączenie ostatniej pary secondary.
Manifesty wykonanych transakcji zapisują operatora, uzasadnienie, ryzyko,
role, strefy oraz sumy SHA-256 i wpisy przed/po operacji.
Po aktywacji transakcja ponownie odczytuje konfigurację i porównuje stan z
planem; rozbieżność uruchamia rollback, ponowny `rndc reconfig` i kontrolę
przywrócenia pliku źródłowego.
Operacyjna bramka secondary porównuje autorytatywność i SOA dotkniętych stref.
Brak `AA`, brak SOA albo serial wyższy niż primary uruchamia rollback; niższy
serial secondary pozostaje stanem `PENDING`, ponieważ transfer może trwać.
Polecenie `bind secondary-health` uruchamia tę samą kontrolę bez zapisu,
aktywacji ani tworzenia manifestu i może ograniczyć audyt do wskazanej pary.
Commit z CLI wymaga niepustego `--reason`; dry-run nie wymaga uzasadnienia,
a TUI zapisuje w manifeście kanał i rodzaj zatwierdzonej operacji.
Dry-run pozostaje dostępny, a obejście awaryjne nie jest jeszcze udostępnione.

## Stan obecny

ZoneCTL zapewnia już plan, diff, dry-run, `named-checkconf`, kontrolę konfliktu
pliku, backup, atomowy zapis, `rndc reconfig` i rollback. Lista ACL nie może być
pusta, `trusted` zachowuje dodatni wpis `localhost`, a grupa secondary musi
zawierać co najmniej jeden poprawny adres IP.

Brakuje natomiast semantycznej oceny wpływu zmiany na działające strefy.
Poprawna składniowo konfiguracja może nadal odciąć administrację, transfer
strefy albo wszystkie serwery secondary.

## Wspólny raport wpływu — tylko do odczytu

Przed przygotowaniem planu zapisu należy zbudować niezmienny raport zawierający:

- nazwę i rodzaj definicji oraz plik źródłowy;
- wpisy przed zmianą i po zmianie;
- dodane i usunięte wpisy;
- wszystkie dyrektywy i strefy odwołujące się do definicji;
- role: administracja, query, recursion, notify, transfer lub primaries;
- liczbę stref i nazwy dotkniętych stref;
- klasyfikację ryzyka i listę bramek blokujących;
- wymagany poziom potwierdzenia operatora.

Raport musi korzystać z pełnego drzewa aktywnych `include`, a nie z wyszukiwania
tekstowego w jednym pliku.

Poziom ryzyka opisuje rozważaną różnicę, a nie sam fakt używania definicji:
`NONE` oznacza brak zmiany, `LOW` zmianę bez usuwania wpisów, `MEDIUM` usuwanie
z używanej listy, `HIGH` usuwanie z roli administracyjnej albo pozostawienie
globalnej ACL query/recursion bez żadnego klienta zdalnego, a `INDETERMINATE`
brak możliwości wiarygodnej oceny.

## Bramka ACL

Operację należy zablokować przed zapisem, gdy:

- kandydat usuwa ostatni dodatni wpis z ACL używanej administracyjnie;
- kandydat usuwa wpis wymagany przez aktywne `allow-transfer`, `allow-notify`,
  `allow-update`, `allow-control`, `allow-recursion` lub `allow-query-cache`;
- po rozwinięciu odwołań ACL powstaje cykl albo nierozpoznana zależność;
- wpływu nie można jednoznacznie obliczyć.

Zmiana używanej ACL, która nie jest blokowana, wymaga pokazania wszystkich
dotkniętych stref i wpisania pełnej nazwy ACL. Opróżnianie używanej ACL nie
może być dostępne jako zwykłe potwierdzenie `tak/nie`.

## Bramka grup secondary

Operację należy zablokować przed zapisem, gdy:

- usuwa ostatni adres z grupy używanej przez aktywną strefę;
- rozdziela parę notify/transfer albo pozostawia parę niekompletną;
- odłącza ostatnią poprawną parę secondary od strefy, która wcześniej ją miała;
- dotyczy RPZ lub innego profilu zarządzanego osobnym mechanizmem;
- kandydat nie pozwala jednoznacznie wskazać dotkniętych stref.

Świadome odłączenie ostatniej pary powinno wymagać osobnego trybu awaryjnego,
pełnej nazwy strefy oraz jawnej przyczyny zapisanej w manifeście. Nie należy
udostępniać go w zwykłym edytorze listy.

## Bramka po aktywacji

Samo powodzenie `rndc reconfig` jest niewystarczające. Po aktywacji należy:

- potwierdzić `rndc zonestatus` każdej dotkniętej strefy;
- porównać serial SOA primary sprzed i po zmianie;
- dla zmiany notify/transfer potwierdzić dostępność skonfigurowanych secondary
  i zgodność seriala w ograniczonym czasie;
- dla ACL administracyjnej wykonać bezpieczną kontrolę kanału zarządzania;
- uruchomić automatyczny rollback, jeżeli obowiązkowa kontrola nie przejdzie.

Brak odpowiedzi z hosta zewnętrznego musi być odróżniony od błędu lokalnej
konfiguracji i prowadzić do jednoznacznego statusu, nie fałszywego `COMMIT`.

## Manifest i audyt

Manifest powinien dodatkowo zawierać:

- operatora systemowego (`uid`, nazwa użytkownika) i czas lokalny/UTC;
- obowiązkową przyczynę dla operacji podwyższonego ryzyka;
- SHA-256, właściciela, grupę i tryb każdego pliku przed i po operacji;
- raport wpływu, usunięte/dodane wpisy i listę dotkniętych stref;
- wyniki wszystkich bramek przed i po aktywacji;
- stan końcowy: commit, rollback albo rollback-failed.

Manifest nie może przechowywać kluczy prywatnych, sekretów TSIG ani treści
spoza plików objętych transakcją.

## Kolejność implementacji

1. Odczytowy model zależności i raport wpływu wraz z testami parsera.
2. Bramka ACL w plannerze — bez zmian w transakcji i TUI.
3. Bramka grup secondary oraz przypisań stref — plan, dry-run i blokada
   zwykłego commitu ryzyka `HIGH`.
4. Rozszerzone potwierdzenia TUI i równoważne parametry CLI.
5. Rozszerzony manifest z kontrolą braku sekretów — wdrożony; automatyczna
   bramka prywatności manifestu pozostaje częścią dalszych testów wydania.
6. Bramki powdrożeniowe i wymuszone testy rollbacku.
7. Próba na izolowanej konfiguracji BIND, następnie jedna kontrolowana zmiana
   produkcyjna o małym wpływie.

## Minimalna macierz testów

- usunięcie nieużywanego wpisu — dozwolone;
- usunięcie wpisu wymaganego przez aktywną rolę — zablokowane;
- niejednoznaczne lub cykliczne odwołanie ACL — zablokowane;
- usunięcie jednego z wielu secondary — dozwolone po potwierdzeniu;
- usunięcie ostatniego secondary lub ostatniej pary — zablokowane;
- konflikt pliku między planem i zapisem — bez zmian;
- błąd `named-checkconf`, `rndc reconfig` i każdej bramki po aktywacji — rollback;
- zachowanie właściciela, grupy, trybu i niezmienionych plików;
- manifest kompletny oraz wolny od sekretów i danych spoza transakcji.
