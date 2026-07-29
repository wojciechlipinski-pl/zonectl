# Dokumentacja ELKMAN-DNS

Pliki
../AI_CONTEXT.md — pełna pamięć projektu dla nowej sesji.
PROJECT_CONTEXT.md — cel i aktualny zakres projektu.
ARCHITECTURE.md — podział na warstwy i przepływ danych.
MODULE_REFERENCE.md — automatyczny wykaz modułów, klas, metod i funkcji.
CHANGELOG.md — historia zmian wygenerowana z Git.
ROADMAP.md — proponowane kierunki rozwoju.
DEVELOPER_GUIDE.md — instrukcja pracy z kodem.
OPERATIONS.md — uruchamianie, wdrażanie i diagnostyka.
DECISIONS.md — decyzje architektoniczne.
SESSION_HANDOFF.md — przekazanie prac do kolejnej sesji.
Aktualizacja
./scripts/generate_docs.sh

Z uruchomieniem testów:

./scripts/generate_docs.sh --with-tests

Przed regeneracją skrypt tworzy kopię istniejącego katalogu docs/.
