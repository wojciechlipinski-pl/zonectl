# Kontekst projektu

Podstawowe dane
Pole	Wartość
Projekt	ELKMAN-DNS
Wersja	3.2.3
Gałąź	master
Commit	66802d0
Katalog	/root/elkman-dns
Wygenerowano	2026-07-29T18:21:02+02:00
Problem rozwiązywany przez projekt

Ręczne modyfikowanie plików stref BIND jest podatne na błędy:

błędną składnię,
nieprawidłowy numer SOA,
zapis do niewłaściwego pliku,
przeładowanie niepoprawnej strefy,
utratę informacji o wprowadzonych zmianach.

ELKMAN-DNS oddziela interfejs użytkownika od modelu strefy, parsowania,
serializacji i zapisu. Celem jest kontrolowany proces od odczytu do
potwierdzonego załadowania strefy.

Obecne możliwości

Możliwości należy każdorazowo potwierdzać kodem i testami. Historia Git
wskazuje na implementację następujących obszarów:

wykrywanie stref z konfiguracji BIND,
widok szczegółów strefy,
parsowanie i prezentację rekordów,
wyszukiwanie domen i rekordów,
ZoneModel,
dialogi curses,
edytor rekordów,
widok zmian oczekujących,
dodawanie rekordów,
usuwanie rekordów,
śledzenie zmian,
kontroler widoku rekordów,
parser pełnego pliku strefy,
dokumentową reprezentację strefy,
adapter dokumentu,
serializer,
writer,
sesję edycji,
obsługę SOA,
wdrażanie i weryfikację,
zapis przez F2 i Ctrl+S.
Ważne ograniczenia
Dokumentacja klas generowana przez AST pokazuje deklaracje,
ale nie zastępuje przeglądu implementacji.
Nie należy zakładać pełnej obsługi każdego typu rekordu DNS
bez sprawdzenia parsera, serializatora i testów.
Nie należy zakładać poprawnego działania w każdym emulatorze terminala.
Przed wdrożeniem trzeba sprawdzić konfigurację konkretnego BIND.
