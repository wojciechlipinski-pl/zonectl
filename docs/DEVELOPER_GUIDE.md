# Podręcznik dewelopera

Przygotowanie środowiska
cd /root/elkman-dns

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e .

Jeżeli projekt definiuje zależności deweloperskie w pyproject.toml,
należy użyć odpowiedniego extra, np.:python -m pip install -e '.[dev]'

Nie należy zakładać istnienia extra dev bez sprawdzenia pliku.

Uruchamianie testów
python -m pytest -q

Test pojedynczego modułu:

python -m pytest -q tests/test_zone_edit_session.py

Test według nazwy:

python -m pytest -q -k 'save'
Analiza przed zmianą
git status
git diff
git log --oneline --decorate -20

Następnie należy znaleźć:

moduł odpowiedzialny za zachowanie,
testy tego modułu,
miejsca wywołania funkcji,
zależności pomiędzy UI i core.

Przykładowo:
grep -R "def save" -n src tests
grep -R "ZoneEditSession" -n src tests
grep -R "KEY_F2" -n src tests
Standard zmiany
Odtworzyć błąd.
Dodać lub wskazać test regresyjny.
Wprowadzić najmniejszą potrzebną zmianę.
Uruchomić test modułu.
Uruchomić cały zestaw testów.
Sprawdzić git diff.
Przetestować ręcznie w terminalu.
Zaktualizować dokumentację.
Utworzyć czytelny commit.
Konwencja commitów

Przykłady:

fix: correctly parse F2 escape sequence
feat: add AAAA record validation
refactor: extract zone save coordinator
test: cover pending changes commit
docs: update transaction architecture
Release 3.2.4: terminal input regression fixes
Dodawanie nowej funkcji dotyczącej rekordów

Przed implementacją trzeba przeanalizować:

parser wejściowy,
ZoneModel,
dialog lub edytor,
renderer,
serializer,
walidację,
testy parsera,
testy modelu,
testy serializatora,
testy UI lub kontrolera.

Nie wystarczy dodać pola do formularza. Zmiana musi przejść całą ścieżkę
od wczytania do ponownego zapisania strefy.

Aktualizacja wersji

Należy sprawdzić co najmniej:

pyproject.toml
src/elkman_dns/__init__.py
CHANGELOG.md
AI_CONTEXT.md
docs/CHANGELOG.md

Po zmianie:

./scripts/generate_docs.sh --with-tests
git diff
