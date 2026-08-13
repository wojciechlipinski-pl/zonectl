# AI_CONTEXT — zonectl

> Ten plik służy do wznowienia pracy w nowej sesji bez pamięci wcześniejszych rozmów.

## Stan projektu
- Projekt: **zonectl**
- Wersja: **4.8.0**
- Katalog: `/root/elkman-dns`
- Gałąź: `feature/4.8-bind-discovery-tui`
- Commit: `7f00d67`
- Ostatni commit: `7f00d67 | 2026-08-13 19:15:09 +0200 | Wojciech Lipiński | release: prepare ZoneCTL 4.8.0`
- Wygenerowano: `2026-08-13T19:16:42+02:00`

## Statystyki
- Moduły Python: **80**
- Klasy: **196**
- Funkcje: **94**
- Metody: **601**
- TODO/FIXME/HACK/XXX: **0**

## Start nowej sesji
Przeczytaj kolejno: `docs/AI_CONTEXT.md`, `docs/PROJECT_CONTEXT.md`, `docs/ARCHITECTURE.md`, `docs/MODULE_REFERENCE.md`, `docs/CHANGELOG.md`, `docs/DECISIONS.md`, `docs/SESSION_HANDOFF.md`.

Następnie wykonaj:
```bash
cd /root/elkman-dns
git status
git log --oneline --decorate --graph -20
python -m pytest -q
```
Nie zgaduj działania kodu. Potwierdzaj je w implementacji, testach i Git.

## Stan Git
```text
?? config/
?? elkman-dns.py
?? install.sh
?? uninstall.sh
?? zonectl-4.8-bind-onboarding-blocker-categories-20260813.tar.gz
?? zonectl-4.8-bind-onboarding-blocker-categories-20260813.tar.gz.sha256
?? zonectl-4.8-bind-onboarding-candidates-20260813.tar.gz
?? zonectl-4.8-bind-onboarding-candidates-20260813.tar.gz.sha256
?? zonectl-4.8-bind-onboarding-dnssec-guarded-import-20260813.tar.gz
?? zonectl-4.8-bind-onboarding-dnssec-guarded-import-20260813.tar.gz.sha256
?? zonectl-4.8-bind-onboarding-dnssec-plan-dry-run-20260813.tar.gz
?? zonectl-4.8-bind-onboarding-dnssec-plan-dry-run-20260813.tar.gz.sha256
?? zonectl-4.8-bind-onboarding-guarded-import-20260813.tar.gz
?? zonectl-4.8-bind-onboarding-guarded-import-20260813.tar.gz.sha256
?? zonectl-4.8-bind-onboarding-guarded-import-test-fix-20260813.tar.gz
?? zonectl-4.8-bind-onboarding-guarded-import-test-fix-20260813.tar.gz.sha256
?? zonectl-4.8-bind-onboarding-report-tui-20260813.tar.gz
?? zonectl-4.8-bind-onboarding-report-tui-20260813.tar.gz.sha256
?? zonectl-4.8-dnssec-onboarding-bulk-audit-20260813.tar.gz
?? zonectl-4.8-dnssec-onboarding-bulk-audit-20260813.tar.gz.sha256
?? zonectl-4.8-tui-about-authorship-20260813.tar.gz
?? zonectl-4.8-tui-about-authorship-20260813.tar.gz.sha256
?? zonectl-4.8-tui-about-concept-layout-20260813.tar.gz
?? zonectl-4.8-tui-about-concept-layout-20260813.tar.gz.sha256
?? zonectl-4.8-tui-onboarding-list-refresh-20260813.tar.gz
?? zonectl-4.8-tui-onboarding-list-refresh-20260813.tar.gz.sha256
```

## Wynik testów
```text
........................................................................ [ 11%]
........................................................................ [ 23%]
........................................................................ [ 35%]
........................................................................ [ 46%]
........................................................................ [ 58%]
........................................................................ [ 70%]
........................................................................ [ 82%]
........................................................................ [ 93%]
.....................................                                    [100%]
613 passed in 2.59s
```
