# Przekazanie projektu do kolejnej sesji

Instrukcja dla nowej sesji AI

Najpierw przeczytaj:

AI_CONTEXT.md
docs/PROJECT_CONTEXT.md
docs/ARCHITECTURE.md
docs/MODULE_REFERENCE.md
docs/DECISIONS.md
docs/CHANGELOG.md

Następnie poproś o wynik:

cd /root/elkman-dns
git status
git log --oneline --decorate --graph -20
python -m pytest -q

Nie zakładaj, że dokumentacja jest nowsza od kodu. Porównaj:

wersję w dokumentacji,
wersję w pyproject.toml,
wersję w src/elkman_dns/__init__.py,
aktualny commit Git.
Stan przy generowaniu
Wersja: 3.2.3
Commit: aec45de
Gałąź: master
Ostatnia zmiana: aec45de | 2026-07-29 18:37:46 +0200 | Wojciech Lipiński | docs: add automatic project documentation generator
Gotowy tekst rozpoczynający nową rozmowę
Pracujemy nad projektem ELKMAN-DNS.

Repozytorium znajduje się w /root/elkman-dns.
Najpierw zapoznaj się z AI_CONTEXT.md oraz katalogiem docs/.
Aktualna wersja według dokumentacji to 3.2.3, ale potwierdź ją
w pyproject.toml, __init__.py i Git.

Nie zgaduj działania kodu. Opieraj się na aktualnej implementacji,
testach i historii Git.

Po zapoznaniu się z dokumentacją przeanalizuj:
git status
git log --oneline --decorate --graph -20
python -m pytest -q

Bieżące zadanie:
[TUTAJ WPISAĆ ZADANIE]
Informacje, które należy dopisać ręcznie przed zakończeniem sesji
Co zostało wykonane?
Jakie pliki zmieniono?
Jakie testy uruchomiono?
Jaki był wynik testów?
Czy wykonano wdrożenie?
Jaki commit kończy pracę?
Jakie problemy pozostały?
Jaki jest następny krok?
Ostatnie przekazanie ręczne
Data:
Cel sesji:
Wykonane zmiany:
Zmodyfikowane pliki:
Testy:
Wdrożenie:
Commit:
Otwarte problemy:
Następny krok:
