# Migracje projektu ZoneCTL

Każda migracja:
- ma unikalny numer,
- sprawdza warunki wejściowe,
- tworzy kopie zmienianych plików,
- jest bezpieczna przy ponownym uruchomieniu,
- uruchamia testy,
- nie wykonuje automatycznie `git commit`.
