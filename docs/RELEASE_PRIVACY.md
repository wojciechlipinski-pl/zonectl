# Kontrola danych przed publikacją

Każdy publiczny commit, tag i pakiet ZoneCTL musi przejść kontrolę danych.
Przykłady używają wyłącznie nazw zarezerwowanych do dokumentacji oraz zakresów
adresowych `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24` i
`2001:db8::/32`.

## Obowiązkowa bramka

```bash
python -m pytest -q tests/test_public_example_privacy.py
git diff --cached --check
git diff --cached
```

Przed utworzeniem tagu należy dodatkowo wykonać pełny zestaw testów i sprawdzić,
że staging nie zawiera konfiguracji lokalnej, archiwów roboczych, kluczy,
tokenów, haseł ani nazw infrastruktury produkcyjnej.

Workflow `Public data guard` wykonuje test prywatności automatycznie przy każdym
pushu i pull requeście. Kontrola automatyczna nie zastępuje przeglądu staged
diffu przez operatora.

Jeżeli sekret został opublikowany, należy najpierw go unieważnić lub obrócić.
Usunięcie wartości w kolejnym commicie nie powoduje jej usunięcia z historii
Git.
