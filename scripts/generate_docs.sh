#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCS_DIR="${PROJECT_ROOT}/docs"
RUN_TESTS=0

if [[ "${1:-}" == "--with-tests" ]]; then
    RUN_TESTS=1
fi

cd "${PROJECT_ROOT}"

if [[ ! -d ".git" ]]; then
    echo "BŁĄD: ${PROJECT_ROOT} nie jest repozytorium Git." >&2
    exit 1
fi

TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"

# Zachowaj poprzednią dokumentację zamiast ją bezpowrotnie nadpisywać.
if [[ -d "${DOCS_DIR}" ]]; then
    BACKUP_DIR="${PROJECT_ROOT}/.docs-backup-${TIMESTAMP}"
    cp -a "${DOCS_DIR}" "${BACKUP_DIR}"
    echo "Kopia poprzedniego katalogu docs: ${BACKUP_DIR}"
fi

if [[ -f "${PROJECT_ROOT}/AI_CONTEXT.md" ]]; then
    cp -a \
        "${PROJECT_ROOT}/AI_CONTEXT.md" \
        "${PROJECT_ROOT}/AI_CONTEXT.md.backup-${TIMESTAMP}"
fi

mkdir -p "${DOCS_DIR}"

export PROJECT_ROOT
export DOCS_DIR
export RUN_TESTS
export GENERATED_AT="$(date --iso-8601=seconds)"

python - <<'PY'
from __future__ import annotations

import ast
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(os.environ["PROJECT_ROOT"]).resolve()
DOCS = Path(os.environ["DOCS_DIR"]).resolve()
GENERATED_AT = os.environ["GENERATED_AT"]
RUN_TESTS = os.environ.get("RUN_TESTS") == "1"


def run(
    *args: str,
    check: bool = False,
    timeout: int = 60,
) -> str:
    try:
        result = subprocess.run(
            list(args),
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=check,
            timeout=timeout,
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError) as exc:
        return f"[nie udało się wykonać: {' '.join(args)}: {exc}]"


def write(name: str, content: str) -> None:
    path = ROOT / name if name == "AI_CONTEXT.md" else DOCS / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    print(f"Utworzono: {path.relative_to(ROOT)}")


def get_version() -> str:
    pyproject = ROOT / "pyproject.toml"

    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8", errors="replace")
        match = re.search(
            r'(?m)^\s*version\s*=\s*["\']([^"\']+)["\']',
            content,
        )
        if match:
            return match.group(1)

    init_file = ROOT / "src/elkman_dns/__init__.py"
    if init_file.exists():
        content = init_file.read_text(encoding="utf-8", errors="replace")
        match = re.search(
            r'__version__\s*=\s*["\']([^"\']+)["\']',
            content,
        )
        if match:
            return match.group(1)

    return "nieustalona"


VERSION = get_version()
HEAD = run("git", "rev-parse", "--short", "HEAD")
BRANCH = run("git", "branch", "--show-current") or "(detached HEAD)"
LAST_COMMIT = run(
    "git",
    "log",
    "-1",
    "--date=iso",
    "--pretty=format:%h | %ad | %an | %s",
)
STATUS = run("git", "status", "--short") or "czyste drzewo robocze"
REMOTE = run("git", "remote", "-v") or "brak skonfigurowanego zdalnego repozytorium"
TAGS = run("git", "tag", "--sort=-version:refname") or "brak tagów"


def project_tree() -> str:
    if shutil_which("tree"):
        return run(
            "tree",
            "-a",
            "-L",
            "4",
            "-I",
            ".git|.venv|__pycache__|.pytest_cache|.mypy_cache|.ruff_cache",
        )

    entries: list[str] = []
    excluded = {
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }

    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)

        if any(part in excluded for part in relative.parts):
            continue
        if len(relative.parts) > 4:
            continue

        marker = "/" if path.is_dir() else ""
        entries.append(f"{relative}{marker}")

    return "\n".join(entries)


def shutil_which(command: str) -> str | None:
    from shutil import which
    return which(command)


TREE = project_tree()


@dataclass
class Definition:
    kind: str
    name: str
    signature: str
    lineno: int
    doc: str
    children: list["Definition"]


@dataclass
class ModuleInfo:
    path: str
    doc: str
    definitions: list[Definition]
    imports: list[str]


def format_arg(arg: ast.arg) -> str:
    if arg.annotation:
        try:
            annotation = ast.unparse(arg.annotation)
            return f"{arg.arg}: {annotation}"
        except Exception:
            pass
    return arg.arg


def function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    parts: list[str] = []

    positional = list(node.args.posonlyargs) + list(node.args.args)
    defaults_offset = len(positional) - len(node.args.defaults)

    for index, arg in enumerate(positional):
        text = format_arg(arg)
        if index >= defaults_offset:
            default = node.args.defaults[index - defaults_offset]
            try:
                text += f" = {ast.unparse(default)}"
            except Exception:
                text += " = ..."
        parts.append(text)

    if node.args.vararg:
        parts.append("*" + format_arg(node.args.vararg))
    elif node.args.kwonlyargs:
        parts.append("*")

    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        text = format_arg(arg)
        if default is not None:
            try:
                text += f" = {ast.unparse(default)}"
            except Exception:
                text += " = ..."
        parts.append(text)

    if node.args.kwarg:
        parts.append("**" + format_arg(node.args.kwarg))

    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    signature = f"{prefix} {node.name}({', '.join(parts)})"

    if node.returns:
        try:
            signature += f" -> {ast.unparse(node.returns)}"
        except Exception:
            pass

    return signature


def parse_definition(
    node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
) -> Definition:
    doc = ast.get_docstring(node) or ""

    if isinstance(node, ast.ClassDef):
        bases: list[str] = []
        for base in node.bases:
            try:
                bases.append(ast.unparse(base))
            except Exception:
                bases.append("?")

        signature = f"class {node.name}"
        if bases:
            signature += f"({', '.join(bases)})"

        children = [
            parse_definition(child)
            for child in node.body
            if isinstance(
                child,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            )
        ]

        return Definition(
            kind="class",
            name=node.name,
            signature=signature,
            lineno=node.lineno,
            doc=doc,
            children=children,
        )

    return Definition(
        kind="function",
        name=node.name,
        signature=function_signature(node),
        lineno=node.lineno,
        doc=doc,
        children=[],
    )


def scan_modules() -> list[ModuleInfo]:
    modules: list[ModuleInfo] = []
    src_root = ROOT / "src"

    if not src_root.exists():
        return modules

    for path in sorted(src_root.rglob("*.py")):
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            modules.append(
                ModuleInfo(
                    path=str(path.relative_to(ROOT)),
                    doc=f"Błąd analizy składni: {exc}",
                    definitions=[],
                    imports=[],
                )
            )
            continue

        imports: list[str] = []

        for node in tree.body:
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = ", ".join(alias.name for alias in node.names)
                imports.append(f"{module}: {names}")

        definitions = [
            parse_definition(node)
            for node in tree.body
            if isinstance(
                node,
                (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
            )
        ]

        modules.append(
            ModuleInfo(
                path=str(path.relative_to(ROOT)),
                doc=ast.get_docstring(tree) or "",
                definitions=definitions,
                imports=imports,
            )
        )

    return modules


MODULES = scan_modules()


def first_sentence(text: str, fallback: str = "Brak docstringa.") -> str:
    text = " ".join(text.strip().split())
    if not text:
        return fallback

    match = re.match(r"(.+?[.!?])(?:\s|$)", text)
    return match.group(1) if match else text


def module_reference() -> str:
    lines = [
        "# Dokumentacja modułów, klas i funkcji",
        "",
        f"> Wygenerowano automatycznie: `{GENERATED_AT}`.",
        "",
        "Dokument jest wynikiem analizy AST aktualnego kodu w katalogu `src/`.",
        "Pokazuje deklaracje, a nie pełną semantykę implementacji.",
        "",
    ]

    if not MODULES:
        lines.append("Nie znaleziono modułów Python w katalogu `src/`.")
        return "\n".join(lines)

    for module in MODULES:
        lines.extend(
            [
                f"## `{module.path}`",
                "",
                first_sentence(module.doc, "Brak docstringa modułu."),
                "",
            ]
        )

        if module.imports:
            lines.append("**Najważniejsze importy:**")
            lines.append("")
            for item in module.imports[:30]:
                lines.append(f"- `{item}`")
            lines.append("")

        if not module.definitions:
            lines.append("Brak publicznych deklaracji klas lub funkcji.")
            lines.append("")
            continue

        for definition in module.definitions:
            lines.extend(
                [
                    f"### `{definition.signature}`",
                    "",
                    f"Lokalizacja: linia `{definition.lineno}`.",
                    "",
                    first_sentence(definition.doc),
                    "",
                ]
            )

            if definition.children:
                lines.append("**Metody:**")
                lines.append("")
                for method in definition.children:
                    visibility = "prywatna" if method.name.startswith("_") else "publiczna"
                    lines.append(
                        f"- `{method.signature}` — linia {method.lineno}, "
                        f"{visibility}; {first_sentence(method.doc).lower()}"
                    )
                lines.append("")

    return "\n".join(lines)


def commit_history(limit: int = 100) -> list[dict[str, str]]:
    fmt = "%H%x1f%h%x1f%ad%x1f%an%x1f%s%x1e"
    output = run(
        "git",
        "log",
        "--all",
        "--date=short",
        f"--pretty=format:{fmt}",
        f"-{limit}",
    )

    commits: list[dict[str, str]] = []
    for record in output.split("\x1e"):
        record = record.strip()
        if not record:
            continue

        fields = record.split("\x1f")
        if len(fields) != 5:
            continue

        full, short, date, author, subject = fields
        commits.append(
            {
                "full": full,
                "short": short,
                "date": date,
                "author": author,
                "subject": subject,
            }
        )

    return commits


COMMITS = commit_history()


def changelog() -> str:
    lines = [
        "# Historia zmian",
        "",
        "Dokument generowany z historii Git.",
        "",
        "## Wydania",
        "",
    ]

    releases = [
        commit for commit in COMMITS
        if commit["subject"].lower().startswith("release ")
        or "baseline 3.1.0" in commit["subject"].lower()
    ]

    if not releases:
        lines.append("Brak commitów oznaczonych jako wydania.")
        lines.append("")
    else:
        for commit in releases:
            lines.extend(
                [
                    f"### {commit['subject']}",
                    "",
                    f"- Data: `{commit['date']}`",
                    f"- Commit: `{commit['short']}`",
                    f"- Autor: `{commit['author']}`",
                    "",
                ]
            )

            stat = run(
                "git",
                "show",
                "--stat",
                "--oneline",
                "--format=",
                commit["full"],
            )
            if stat:
                lines.extend(["```text", stat, "```", ""])

    lines.extend(
        [
            "## Pełna chronologia funkcjonalna",
            "",
        ]
    )

    for commit in COMMITS:
        lines.append(
            f"- `{commit['date']}` — `{commit['short']}` — "
            f"**{commit['subject']}**"
        )

    lines.extend(
        [
            "",
            "## Ważna zasada",
            "",
            "Ten plik opisuje to, co znajduje się w Git. "
            "Nie należy dopisywać funkcji, których nie potwierdza kod "
            "lub historia repozytorium.",
        ]
    )

    return "\n".join(lines)


TEST_RESULT = "Nie uruchamiano testów podczas generowania dokumentacji."

if RUN_TESTS:
    TEST_RESULT = run(
        sys.executable,
        "-m",
        "pytest",
        "-q",
        timeout=300,
    )


AI_CONTEXT = f"""# AI CONTEXT — ELKMAN-DNS

> Ten plik jest przeznaczony do przekazania pełnego kontekstu projektu
> nowej sesji AI lub nowemu programiście.
>
> Założenie: odbiorca nie pamięta żadnej wcześniejszej rozmowy.

## 1. Identyfikacja projektu

- Nazwa: **ELKMAN-DNS**
- Aktualna wersja: **{VERSION}**
- Katalog roboczy: `{ROOT}`
- Gałąź Git: `{BRANCH}`
- Aktualny commit: `{HEAD}`
- Ostatni commit: `{LAST_COMMIT}`
- Dokumentację wygenerowano: `{GENERATED_AT}`

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
cd {ROOT}
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
{STATUS}
9. Zdalne repozytoria
{REMOTE}
10. Tagi
{TAGS}
11. Wynik testów podczas generowania
{TEST_RESULT}
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

"""

PROJECT_CONTEXT = f"""# Kontekst projektu

Podstawowe dane
Pole	Wartość
Projekt	ELKMAN-DNS
Wersja	{VERSION}
Gałąź	{BRANCH}
Commit	{HEAD}
Katalog	{ROOT}
Wygenerowano	{GENERATED_AT}
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
"""

ARCHITECTURE = f"""# Architektura

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

W wersji {VERSION} projekt rozpoznaje także sekwencję:

ESC [ 12 ~

Ta logika jest elementem kompatybilności terminalowej, a nie
przypadkowym obejściem.

8. Zależności

Automatyczny wykaz importów oraz deklaracji znajduje się w
MODULE_REFERENCE.md.

9. Struktura repozytorium
{TREE}

"""

ROADMAP = """# Roadmap

Poniższe pozycje są propozycjami rozwoju. Nie oznaczają,
że zostały zatwierdzone lub rozpoczęte.

Najbliższe zadania
 Dodać test regresyjny parsera sekwencji F2.
 Dodać test zapisu z widoku Pending Changes.
 Dodać test odświeżenia modelu po COMMIT.
 Uzupełnić docstringi publicznych klas i metod.
 Ujednolicić obsługę błędów UI i warstwy core.
 Zweryfikować wszystkie skróty w różnych terminalach.
 Opisać procedurę rollbacku po błędzie reloadu BIND.
Rozwój funkcjonalny
 Cofanie ostatniej zmiany w bieżącej sesji.
 Historia zmian i transakcji.
 Eksport zmian przed COMMIT.
 Podgląd różnic w formacie unified diff.
 Obsługa wielu stref w jednej sesji.
 Rozbudowane filtrowanie rekordów.
 Walidacja wartości zależna od typu rekordu.
 Integracja z repozytorium Git przechowującym strefy.
 Tryb tylko do odczytu.
 Mechanizm blokowania równoległej edycji.
Jakość
 Pokrycie testami krytycznych ścieżek zapisu.
 Statyczna analiza typów.
 Automatyczne formatowanie i lint.
 Testy integracyjne z odseparowaną instancją BIND.
 Testy zachowania po nieudanym named-checkzone.
 Testy zachowania po nieudanym rndc reload.
 Testy stref inline-signing.
Dokumentacja
 Przykłady obsługi każdego wspieranego typu rekordu.
 Zrzuty ekranów TUI.
 Instrukcja odtwarzania po awarii.
 Procedura wydania nowej wersji.
 Lista wspieranych wersji Pythona, BIND i systemów.
"""

DEVELOPER_GUIDE = f"""# Podręcznik dewelopera

Przygotowanie środowiska
cd {ROOT}

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

"""

OPERATIONS = f"""# Instrukcja operacyjna

Uruchomienie
cd {ROOT}
source .venv/bin/activate
python -m elkman_dns --help

Dokładne polecenie produkcyjne należy sprawdzić w pyproject.toml
i skryptach wdrożeniowych.

Weryfikacja projektu
./scripts/verify.sh

Jeżeli skrypt istnieje i ma prawa wykonania:

chmod +x scripts/verify.sh
./scripts/verify.sh
Wdrożenie

Historia projektu wskazuje na skrypt:

scripts/deploy.sh

Przed jego wykonaniem:

git status
git log -1 --oneline
python -m pytest -q

Następnie przeczytać skrypt:

less scripts/deploy.sh

Nie uruchamiać skryptu wdrożeniowego bez sprawdzenia:

katalogów docelowych,
użytkownika systemowego,
kopii zapasowej,
praw dostępu,
konfiguracji BIND,
komend wykonywanych jako root.
Kontrola strefy po zapisie

Przykładowe polecenia:

rndc zonestatus NAZWA_STREFY
dig @127.0.0.1 SOA NAZWA_STREFY +short

W odpowiedzi dig numer seryjny SOA jest zwykle trzecim polem
po nazwie głównego serwera i adresie administratora.

Diagnostyka
journalctl -u bind9 --since '-15 minutes'
rndc status
rndc zonestatus NAZWA_STREFY
named-checkzone NAZWA_STREFY /sciezka/do/pliku.strefy

Nazwy usługi mogą różnić się zależnie od systemu, np. bind9 lub named.

Procedura przed zmianą produkcyjną
Wykonać kopię pliku strefy.
Sprawdzić aktualny SOA z BIND.
Sprawdzić stan Git projektu.
Uruchomić testy.
Wprowadzić zmianę.
Zweryfikować wynik aplikacji.
Sprawdzić plik strefy.
Sprawdzić SOA załadowany przez BIND.
Sprawdzić logi.
W razie błędu przywrócić kopię i ponownie załadować strefę.
"""

DECISIONS = """# Rejestr decyzji architektonicznych

ADR-001: Standardowy układ pakietu Python

Status: przyjęta

Projekt został przeniesiony do układu:

src/elkman_dns/

Powody:

rozdzielenie kodu projektu od katalogu roboczego,
poprawne testowanie zainstalowanego pakietu,
zgodność ze współczesnymi narzędziami Python.
ADR-002: Transakcyjny zapis stref

Status: przyjęta

Zmiana strefy nie powinna oznaczać natychmiastowego, niekontrolowanego
nadpisania pliku.

Proces musi obejmować:

wykrycie zmian,
walidację,
zapis,
przeładowanie,
wynik operacji.
ADR-003: NO-CHANGE nie jest błędem

Status: przyjęta

Brak różnic pomiędzy stanem początkowym i końcowym powinien być
rozpoznawany przed COMMIT.

Nie należy wykonywać zbędnego zapisu ani zwiększać SOA.

ADR-004: Kontrola załadowanego SOA

Status: przyjęta

Dla stref inline-signing stan pliku i stan widoczny w działającym BIND
mogą wymagać dodatkowego sprawdzenia.

Dlatego projekt uwzględnia kontrolę numeru SOA załadowanego przez serwer.

ADR-005: Wydzielanie odpowiedzialności z CursesApp

Status: przyjęta

Wraz z rozwojem TUI wydzielono między innymi:

dialogi,
renderer rekordów,
skróty klawiszowe,
edytor rekordów,
dialog nowego rekordu,
kontroler widoku rekordów.

Celem jest ograniczenie klasy głównej i zwiększenie testowalności.

ADR-006: Własna interpretacja F2

Status: przyjęta

Niektóre terminale zwracają F2 jako wielobajtową sekwencję ESC zamiast
curses.KEY_F2.

Projekt rozpoznaje sekwencję ESC [ 12 ~, aby zapis działał na
docelowym terminalu.

Decyzję można zmienić dopiero po potwierdzeniu, że nowy mechanizm działa
we wszystkich wspieranych środowiskach.

Szablon kolejnej decyzji
## ADR-NNN: Nazwa decyzji

**Status:** proponowana / przyjęta / wycofana

### Kontekst

...

### Decyzja

...

### Konsekwencje

...

"""

SESSION_HANDOFF = f"""# Przekazanie projektu do kolejnej sesji

Instrukcja dla nowej sesji AI

Najpierw przeczytaj:

AI_CONTEXT.md
docs/PROJECT_CONTEXT.md
docs/ARCHITECTURE.md
docs/MODULE_REFERENCE.md
docs/DECISIONS.md
docs/CHANGELOG.md

Następnie poproś o wynik:

cd {ROOT}
git status
git log --oneline --decorate --graph -20
python -m pytest -q

Nie zakładaj, że dokumentacja jest nowsza od kodu. Porównaj:

wersję w dokumentacji,
wersję w pyproject.toml,
wersję w src/elkman_dns/__init__.py,
aktualny commit Git.
Stan przy generowaniu
Wersja: {VERSION}
Commit: {HEAD}
Gałąź: {BRANCH}
Ostatnia zmiana: {LAST_COMMIT}
Gotowy tekst rozpoczynający nową rozmowę
Pracujemy nad projektem ELKMAN-DNS.

Repozytorium znajduje się w /root/elkman-dns.
Najpierw zapoznaj się z AI_CONTEXT.md oraz katalogiem docs/.
Aktualna wersja według dokumentacji to {VERSION}, ale potwierdź ją
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

"""

DOCS_README = """# Dokumentacja ELKMAN-DNS

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
"""

write("AI_CONTEXT.md", AI_CONTEXT)
write("README.md", DOCS_README)
write("PROJECT_CONTEXT.md", PROJECT_CONTEXT)
write("ARCHITECTURE.md", ARCHITECTURE)
write("MODULE_REFERENCE.md", module_reference())
write("CHANGELOG.md", changelog())
write("ROADMAP.md", ROADMAP)
write("DEVELOPER_GUIDE.md", DEVELOPER_GUIDE)
write("OPERATIONS.md", OPERATIONS)
write("DECISIONS.md", DECISIONS)
write("SESSION_HANDOFF.md", SESSION_HANDOFF)
PY

echo
echo "Dokumentacja została utworzona."
echo
echo "Wygenerowane pliki:"
find "${DOCS_DIR}" -maxdepth 1 -type f -printf ' %P\n' | sort
echo " AI_CONTEXT.md"
echo
echo "Sprawdź zmiany:"
echo " git status --short"
echo " git diff -- AI_CONTEXT.md docs/ scripts/generate_docs.sh"
