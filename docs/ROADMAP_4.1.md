# ZoneCTL 4.1 — Rebranding & Bulk Operations

## Tożsamość

- Projekt: **ZoneCTL**
- CLI: `zctl`
- Pakiet Python: `zonectl`
- Tagline: **Transactional DNS Management Toolkit**

## Zakres

### Rebranding

Status: **zrealizowane w 4.1.0**

- nazwa produktu,
- komenda `zctl`,
- przestrzeń nazw Python,
- README i dokumentacja,
- generator dokumentacji,
- komunikaty TUI i `--version`,
- migracja istniejącej instalacji.

### Bulk Operations

Status: **planowane — po etapie bezpieczeństwa zapisu**

Planowana składnia:

```text
SELECT type=A AND ttl=3600
SET ttl=7200

SELECT type=A AND value=192.0.2.10
SET value=192.0.2.20

SELECT type=TXT AND name~="^_old"
DELETE
```

Operacje masowe mają korzystać z istniejącego modelu zmian i jednej transakcji zapisu.

### Profile kontroli zdrowia stref

Status: **zrealizowane w 4.1.1**

Nie wszystkie strefy powinny być oceniane jak publiczne strefy
autorytatywne. ZoneCTL otrzyma jawny `health_profile`, wybierany w
konfiguracji pojedynczej strefy.

Pierwszym dodatkowym profilem będzie `rpz` dla lokalnych stref Response
Policy Zone, takich jak `cert-rpz.local`, aktualizowanych automatycznie
z listy CERT Polska/NASK.

Planowana konfiguracja:

```ini
[cert-rpz.local]
health_profile = rpz
rpz_max_age = 600
dns2 = no
he = no
notify = no
```

Profil `rpz` będzie kontrolował:

- istnienie pliku strefy,
- poprawność składni przez `named-checkzone`,
- załadowanie strefy przez BIND,
- wiek pliku względem `rpz_max_age`.

Nie będzie wymagał publicznie dostępnego SOA, DNSSEC ani synchronizacji
z DNS2/HE. TUI powinien prezentować status przeznaczenia i świeżości,
np. `PASS RPZ AGE 03m`, zamiast fałszywego `FAIL DNSSEC`.

Architektura profili powinna umożliwić późniejsze dodanie kolejnych
rodzajów kontroli bez wpisywania wyjątków zależnych od nazwy domeny.

### Dokumentacja PL/EN i internacjonalizacja

Status: **przyszłe rozszerzenie — poza zakresem 4.1.2**

ZoneCTL pozostaje obecnie projektem niepublikowanym, dlatego zmiana nie
jest wymagana w bieżącym wydaniu. Architektura powinna jednak umożliwić
późniejsze udostępnienie programu użytkownikom polsko- i anglojęzycznym.

Plan dokumentacji:

- polski pozostaje podstawowym językiem dokumentacji operacyjnej,
- powstaje `README.en.md` oraz angielskie instrukcje instalacji i użycia,
- publiczna dokumentacja CLI i architektury jest dostępna w wersji PL/EN,
- dokumentacja generowana automatycznie nie jest dublowana bez potrzeby.

Plan internacjonalizacji programu:

- teksty CLI i TUI zostają oddzielone od logiki programu,
- tłumaczenia korzystają ze standardowego mechanizmu `gettext`,
- język można wybrać w konfiguracji, np. `language = pl`,
- domyślnie używany jest język polski, a drugim językiem jest angielski,
- opcjonalnie język może być wykrywany z locale systemu,
- testy sprawdzają kompletność tłumaczeń i brak tekstów zaszytych w UI.
