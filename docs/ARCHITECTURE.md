# Architektura

1. Widok ogólny
Użytkownik
    │
    ▼
CLI / Curses TUI
    │
    ▼
Kontrolery i dialogi rekordów
    │
    ▼
ZoneModel / ZoneEditSession
    │
    ├── parser pliku strefy
    ├── adapter dokumentu
    ├── serializer
    ├── obsługa SOA
    └── writer
            │
            ▼
        walidacja strefy
            │
            ▼
         zapis pliku
            │
            ▼
        przeładowanie BIND
2. Warstwa CLI
Odpowiada za:

uruchamianie programu,
interpretację argumentów,
polecenia diagnostyczne i weryfikacyjne,
przekazanie kontroli do właściwej warstwy.

Punkt wejścia należy potwierdzić w pyproject.toml oraz
src/elkman_dns/cli.py.

3. Warstwa UI

Główny interfejs znajduje się w:

src/elkman_dns/ui/

curses_app.py koordynuje ekrany aplikacji. Logika rekordów została
stopniowo wydzielona do:

src/elkman_dns/ui/records/

Celem tego podziału jest ograniczenie rozmiaru i odpowiedzialności
głównej klasy aplikacji curses.

4. Warstwa modelu i sesji
Model reprezentuje stan strefy widoczny dla interfejsu oraz zmiany
wykonane przez użytkownika.

Sesja edycji łączy:

stan początkowy,
stan zmodyfikowany,
wykrywanie zmian,
przygotowanie zapisu,
wynik transakcji,
ponowne wczytanie danych.
5. Warstwa dokumentu strefy

Plik strefy nie powinien być traktowany wyłącznie jako lista rekordów.
Może zawierać komentarze, dyrektywy i układ istotny dla administratora.

Dlatego projekt posiada elementy odpowiedzialne za:

analizę dokumentu strefy,
konwersję dokumentu do modelu edycyjnego,
konwersję modelu do dokumentu,
serializację końcową.
6. Warstwa zapisu

Proces zapisu powinien zachowywać kolejność:

wykrycie zmian
→ przygotowanie dokumentu
→ ustalenie SOA
→ serializacja
→ walidacja
→ bezpieczny zapis
→ reload BIND
→ potwierdzenie wyniku
→ odświeżenie modelu

Szczegółową implementację należy sprawdzać w:

src/elkman_dns/core/zone_edit_session.py
src/elkman_dns/core/zone_writer.py
src/elkman_dns/core/zone_serializer.py
src/elkman_dns/core/soa_serial.py
7. Obsługa klawiatury
Nie wszystkie terminale przekazują F2 jako curses.KEY_F2.

W wersji 3.2.3 projekt rozpoznaje także sekwencję:

ESC [ 12 ~

Ta logika jest elementem kompatybilności terminalowej, a nie
przypadkowym obejściem.

8. Zależności

Automatyczny wykaz importów oraz deklaracji znajduje się w
MODULE_REFERENCE.md.

9. Struktura repozytorium
.
├── CHANGELOG.md
├── CHANGELOG.md.bak-release-3.2.0
├── dist
│   ├── elkman_dns_toolkit-3.2.3-py3-none-any.whl
│   └── elkman_dns_toolkit-3.2.3.tar.gz
├── docs
├── .gitignore
├── groups.yaml.example
├── packaging
├── pyproject.toml
├── pyproject.toml.bak-3.1.1-credits
├── pyproject.toml.bak-release-3.2.0
├── README.md
├── requirements.txt
├── scripts
│   ├── deploy.sh
│   ├── elkman-dns
│   ├── generate_docs.sh
│   ├── lib.sh
│   └── verify.sh
├── src
│   ├── elkman_dns
│   │   ├── cli.py
│   │   ├── cli.py.bak-release-3.2.0
│   │   ├── core
│   │   │   ├── audit.py
│   │   │   ├── bind_config.py
│   │   │   ├── bind.py
│   │   │   ├── config.py
│   │   │   ├── discovery.py
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── runner.py
│   │   │   ├── soa_serial.py
│   │   │   ├── transaction.py
│   │   │   ├── zone_document_adapter.py
│   │   │   ├── zone_document.py
│   │   │   ├── zone_edit_session.py
│   │   │   ├── zone_file_parser.py
│   │   │   ├── zone_model.py
│   │   │   ├── zone_parser.py
│   │   │   ├── zone_serializer.py
│   │   │   └── zone_writer.py
│   │   ├── __init__.py
│   │   ├── __init__.py.bak-3.1.1-credits
│   │   ├── __init__.py.bak-release-3.2.0
│   │   ├── legacy_v220.py
│   │   └── ui
│   │       ├── credits.py
│   │       ├── credits.py.bak-release-3.2.0
│   │       ├── curses_app.py
│   │       ├── curses_app.py.bak-3.1.1-credits
│   │       ├── curses_app.py.bak-before-debug-indent-fix
│   │       ├── curses_app.py.bak-f2-global-parser
│   │       ├── curses_app.py.bak-pending-save-fix
│   │       ├── curses_app.py.bak-release-3.2.0
│   │       ├── curses_app.py.bak-save-hotkeys
│   │       ├── dialogs.py
│   │       ├── __init__.py
│   │       └── records
│   └── elkman_dns_toolkit.egg-info
│       ├── dependency_links.txt
│       ├── entry_points.txt
│       ├── PKG-INFO
│       ├── SOURCES.txt
│       └── top_level.txt
├── tests
│   ├── test_config_discovery.py
│   ├── test_discovery.py
│   ├── test_new_record_dialog.py
│   ├── test_record_controller.py
│   ├── test_record_editor.py
│   ├── test_record_renderer.py
│   ├── test_soa_serial.py
│   ├── test_ui_dialogs.py
│   ├── test_zone_document_adapter.py
│   ├── test_zone_edit_session.py
│   ├── test_zone_file_parser.py
│   ├── test_zone_model_delete.py
│   ├── test_zone_model.py
│   ├── test_zone_model_record_views.py
│   ├── test_zone_serializer.py
│   └── test_zone_writer.py
└── tools
    └── migrate
        ├── add_pending_changes_view.py
        ├── add_zone_edit_model.py
        ├── add_zone_record_parser.py
        ├── add_zone_record_search.py
        ├── add_zone_records_view.py
        ├── extract_curses_dialogs.py
        ├── fix_main_domain_search.py
        ├── fix_zone_record_search_input.py
        ├── integrate_zone_model_with_tui.py
        └── sprint_4_2_enter.py

14 directories, 82 files
