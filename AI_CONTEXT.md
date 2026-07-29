# AI CONTEXT — ELKMAN-DNS

> Ten plik jest przeznaczony do przekazania pełnego kontekstu projektu
> nowej sesji AI lub nowemu programiście.
>
> Założenie: odbiorca nie pamięta żadnej wcześniejszej rozmowy.

## 1. Identyfikacja projektu

- Nazwa: **ELKMAN-DNS**
- Aktualna wersja: **3.2.3**
- Katalog roboczy: `/root/elkman-dns`
- Gałąź Git: `master`
- Aktualny commit: `66802d0`
- Ostatni commit: `66802d0 | 2026-07-29 17:22:47 +0200 | Wojciech Lipiński | Release 3.2.3: add F2 save support`
- Dokumentację wygenerowano: `2026-07-29T18:21:02+02:00`

## 2. Cel projektu

ELKMAN-DNS jest terminalową aplikacją Python przeznaczoną do obsługi
stref DNS zarządzanych przez BIND.

Projekt rozwijany jest w kierunku bezpiecznego edytora stref, który:

- wykrywa konfigurację i strefy BIND,
- odczytuje i prezentuje rekordy DNS,
- umożliwia wyszukiwanie rekordów,
- umożliwia dodawanie, edytowanie i usuwanie rekordów,
- śledzi zmiany oczekujące,
- wykonuje zapis w sposób transakcyjny,
- kontroluje numer seryjny SOA,
- weryfikuje poprawność strefy,
- przeładowuje strefę w BIND,
- informuje o wyniku operacji.

## 3. Stan wymagający zachowania

Wersja 3.2.3 wprowadziła obsługę zapisu klawiszem `F2`.

W niektórych terminalach F2 jest wysyłane jako sekwencja:

```text
ESC [ 12 ~
Dlatego w src/elkman_dns/ui/curses_app.py znajduje się własna obsługa
wejścia klawiatury. Nie wolno usuwać tej obsługi bez testu na docelowym
terminalu.

Zapis powinien być dostępny co najmniej:

z głównego widoku rekordów,
z widoku zmian oczekujących,
przez F2,
przez Ctrl+S.

Po COMMIT lub poprawnym NO-CHANGE model widoku powinien zostać
odświeżony.

4. Główne etapy rozwoju
3.1.0 — bazowa warstwa transakcyjna.
3.1.1 — wykrywanie braku zmian przed COMMIT.
3.1.2 — status transakcji w wynikach.
3.1.3 — kontrola załadowanego SOA dla inline-signing.
Sprint 3.2 — wspólna weryfikacja stref i komenda verify.
Sprinty 4.x — rozwój TUI, ZoneModel, rekordów, dialogów,
edytora i kontrolera.
3.2.0 — transakcyjny edytor stref i wykrywanie BIND.
3.2.3 — poprawna obsługa zapisu F2.

Szczegóły znajdują się w docs/CHANGELOG.md.

5. Najważniejsze obszary kodu
src/elkman_dns/cli.py — interfejs wiersza poleceń i uruchamianie.
src/elkman_dns/core/ — logika konfiguracji, wykrywania,
parsowania, modelu stref i zapisu.
src/elkman_dns/ui/ — interfejs curses.
src/elkman_dns/ui/records/ — kontroler, renderer, edytor,
dialog dodawania i skróty widoku rekordów.
tests/ — testy jednostkowe i regresyjne.
scripts/ — instalacja, wdrażanie, weryfikacja i narzędzia projektu.

Pełna lista klas i funkcji jest automatycznie generowana w
docs/MODULE_REFERENCE.md
6. Zasady bezpiecznego rozwijania
Nie edytować plików stref bez mechanizmu walidacji.
Nie przeładowywać BIND przed pomyślną walidacją.
Nie zwiększać SOA przy operacji NO-CHANGE.
Nie usuwać obsługi terminalowej sekwencji F2 bez testów regresyjnych.
Po zmianach wykonywać pełny zestaw testów.
Przed wdrożeniem sprawdzać git diff.
Każda większa zmiana powinna mieć osobny commit.
Aktualizować wersję, changelog i dokumentację przy wydaniu.
Nie zakładać zachowania inline-signing bez sprawdzenia załadowanego SOA.
Nie zgadywać architektury — sprawdzać bieżący kod.
7. Polecenia startowe nowej sesji
cd /root/elkman-dns
source .venv/bin/activate

git status
git log --oneline --decorate --graph -20
python -m pytest -q
python -m elkman_dns --help
Przed modyfikacją należy przeczytać:

AI_CONTEXT.md
docs/PROJECT_CONTEXT.md
docs/ARCHITECTURE.md
docs/MODULE_REFERENCE.md
docs/DECISIONS.md
docs/SESSION_HANDOFF.md
8. Stan Git podczas generowania
?? scripts/generate_docs.sh
9. Zdalne repozytoria
brak skonfigurowanego zdalnego repozytorium
10. Tagi
v3.2.0
v3.1.3
11. Wynik testów podczas generowania
........................................................................ [ 64%]
.......................................                                  [100%]
111 passed in 0.16s
12. Pierwsze pytania przed rozpoczęciem kolejnego zadania

Nowa sesja powinna ustalić:

Jaki jest dokładny cel bieżącej zmiany?
Czy zmiana dotyczy UI, modelu, parsera, zapisu czy wdrożenia?
Jak wygląda oczekiwane zachowanie?
Jakie zachowanie występuje obecnie?
Jak odtworzyć problem?
Czy istnieją testy obejmujące ten przypadek?
Czy zmiana wpływa na format pliku strefy lub SOA?
Czy wdrożenie ma być wykonane na serwerze produkcyjnym?
13. Aktualizacja tego dokumentu

Po każdej wersji uruchomić:

./scripts/generate_docs.sh --with-tests
