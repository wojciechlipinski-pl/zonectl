#!/usr/bin/env python3
from __future__ import annotations
import ast, re, shutil, subprocess, sys
from datetime import datetime
from pathlib import Path

EXCLUDE={'.git','.venv','venv','__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','docs'}

def run(cmd, cwd, timeout=180):
    try:
        p=subprocess.run(cmd,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
        return p.returncode,p.stdout.strip()
    except Exception as e:
        return 1,f'{type(e).__name__}: {e}'

def root_dir():
    p=Path.cwd().resolve()
    for c in [p,*p.parents]:
        if (c/'.git').exists() or (c/'pyproject.toml').exists(): return c
    return p

def meta(root):
    txt=(root/'pyproject.toml').read_text(encoding='utf-8',errors='replace') if (root/'pyproject.toml').exists() else ''
    def find(key,default):
        m=re.search(rf'(?m)^\s*{key}\s*=\s*["\']([^"\']+)',txt)
        return m.group(1) if m else default
    return find('name',root.name),find('version','nieustalona')

def git(root,cmd,default):
    code,out=run(['git',*cmd],root)
    return out if code==0 and out else default

def sig(node):
    try: return ast.unparse(node)
    except Exception: return node.name

def scan(root):
    src=root/'src' if (root/'src').exists() else root
    modules=[]
    for p in sorted(src.rglob('*.py')):
        if any(x in EXCLUDE for x in p.parts): continue
        text=p.read_text(encoding='utf-8',errors='replace')
        todos=[(i,l.strip()) for i,l in enumerate(text.splitlines(),1) if re.search(r'\b(TODO|FIXME|HACK|XXX)\b',l,re.I)]
        try: tree=ast.parse(text)
        except SyntaxError as e:
            modules.append((p.relative_to(root),f'Błąd składni: {e}',[],[],todos)); continue
        imports=[]; defs=[]
        for n in tree.body:
            if isinstance(n,ast.Import): imports += [a.name for a in n.names]
            elif isinstance(n,ast.ImportFrom): imports.append((n.module or '')+': '+', '.join(a.name for a in n.names))
            elif isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
                methods=[]
                if isinstance(n,ast.ClassDef):
                    methods=[(m.name,m.lineno,ast.get_docstring(m) or '') for m in n.body if isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef))]
                    signature='class '+n.name
                else:
                    signature=('async def ' if isinstance(n,ast.AsyncFunctionDef) else 'def ')+n.name
                defs.append((signature,n.lineno,ast.get_docstring(n) or '',methods))
        modules.append((p.relative_to(root),ast.get_docstring(tree) or '',imports,defs,todos))
    return modules

def first(s,default='Brak docstringa.'):
    s=' '.join((s or '').split())
    return s if s else default

def write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text.rstrip()+'\n',encoding='utf-8')
    print('Utworzono:',path)

def main():
    root=root_dir(); docs=root/'docs'; with_tests='--with-tests' in sys.argv
    if docs.exists():
        backup=root/f'.docs-backup-{datetime.now():%Y%m%d-%H%M%S}'
        shutil.copytree(docs,backup); print('Kopia:',backup)
    for d in [docs,docs/'api',docs/'diagrams',docs/'images']: d.mkdir(parents=True,exist_ok=True)
    name,version=meta(root); modules=scan(root); now=datetime.now().astimezone().isoformat(timespec='seconds')
    branch=git(root,['branch','--show-current'],'(brak)'); head=git(root,['rev-parse','--short','HEAD'],'(brak)')
    last=git(root,['log','-1','--date=iso','--pretty=format:%h | %ad | %an | %s'],'(brak)')
    status=git(root,['status','--short'],'czyste drzewo robocze')
    log=git(root,['log','--all','--date=short','--pretty=format:%ad\t%h\t%s','-100'],'brak historii Git')
    test='Nie uruchamiano testów.'
    if with_tests:
        _,test=run([sys.executable,'-m','pytest','-q'],root,300)
    classes=sum(1 for _,_,_,ds,_ in modules for d in ds if d[0].startswith('class '))
    funcs=sum(1 for _,_,_,ds,_ in modules for d in ds if d[0].startswith(('def ','async def ')))
    methods=sum(len(d[3]) for _,_,_,ds,_ in modules for d in ds)
    todos=sum(len(t) for *_,t in modules)

    write(docs/'AI_CONTEXT.md',f'''# AI_CONTEXT — {name}

> Ten plik służy do wznowienia pracy w nowej sesji bez pamięci wcześniejszych rozmów.

## Stan projektu
- Projekt: **{name}**
- Wersja: **{version}**
- Katalog: `{root}`
- Gałąź: `{branch}`
- Commit: `{head}`
- Ostatni commit: `{last}`
- Wygenerowano: `{now}`

## Statystyki
- Moduły Python: **{len(modules)}**
- Klasy: **{classes}**
- Funkcje: **{funcs}**
- Metody: **{methods}**
- TODO/FIXME/HACK/XXX: **{todos}**

## Start nowej sesji
Przeczytaj kolejno: `docs/AI_CONTEXT.md`, `docs/PROJECT_CONTEXT.md`, `docs/ARCHITECTURE.md`, `docs/MODULE_REFERENCE.md`, `docs/CHANGELOG.md`, `docs/DECISIONS.md`, `docs/SESSION_HANDOFF.md`.

Następnie wykonaj:
```bash
cd {root}
git status
git log --oneline --decorate --graph -20
python -m pytest -q
```
Nie zgaduj działania kodu. Potwierdzaj je w implementacji, testach i Git.

## Stan Git
```text
{status}
```

## Wynik testów
```text
{test}
```
''')

    write(docs/'PROJECT_CONTEXT.md',f'''# Kontekst projektu

| Pole | Wartość |
|---|---|
| Projekt | {name} |
| Wersja | `{version}` |
| Gałąź | `{branch}` |
| Commit | `{head}` |
| Wygenerowano | `{now}` |

Pełny wykaz klas, funkcji i metod znajduje się w `MODULE_REFERENCE.md`.
''')

    arch=f'# Architektura\n\n> Wygenerowano z importów AST: `{now}`.\n\n'
    for path,doc,imports,defs,t in modules:
        arch+=f'## `{path}`\n\n{first(doc)}\n\n'
        if imports: arch+='**Importy:**\n\n'+''.join(f'- `{x}`\n' for x in imports[:50])+'\n'
    write(docs/'ARCHITECTURE.md',arch)

    ref=f'# Dokumentacja modułów\n\n> Wygenerowano z AST: `{now}`.\n\n'
    for path,doc,imports,defs,t in modules:
        ref+=f'## `{path}`\n\n{first(doc)}\n\n'
        if not defs: ref+='Brak klas i funkcji na poziomie modułu.\n\n'
        for signature,line,docstring,methods_ in defs:
            ref+=f'### `{signature}`\n\nLinia: `{line}`\n\n{first(docstring)}\n\n'
            if methods_:
                ref+='**Metody:**\n\n'+''.join(f'- `{n}` — linia {ln}; {first(ds).lower()}\n' for n,ln,ds in methods_)+'\n'
    write(docs/'MODULE_REFERENCE.md',ref)

    todo='# TODO / FIXME / HACK / XXX\n\n'
    if not todos: todo+='Nie znaleziono znaczników.\n'
    for path,_,_,_,items in modules:
        if items:
            todo+=f'## `{path}`\n\n'+''.join(f'- linia `{ln}` — `{txt}`\n' for ln,txt in items)+'\n'
    write(docs/'TODO.md',todo)

    ch=f'# Historia zmian\n\n> Wygenerowano z Git: `{now}`.\n\n'
    for line in log.splitlines():
        p=line.split('\t',2)
        ch += f'- `{p[0]}` — `{p[1]}` — {p[2]}\n' if len(p)==3 else f'- {line}\n'
    write(docs/'CHANGELOG.md',ch)

    defaults={
      'ROADMAP.md':'# Roadmap\n\n- [ ] Określić zakres następnej wersji.\n- [ ] Przenieść istotne pozycje z `TODO.md`.\n',
      'DECISIONS.md':'# Rejestr decyzji architektonicznych\n\n## Szablon ADR\n\n```markdown\n## ADR-NNN: Nazwa\n**Status:** proponowana / przyjęta / wycofana\n### Kontekst\n...\n### Decyzja\n...\n### Konsekwencje\n...\n```\n',
      'OPERATIONS.md':'# Operacje\n\nPrzed wdrożeniem: `git status`, pełne testy oraz przegląd skryptów w `scripts/`.\n',
      'DEVELOPER_GUIDE.md':f'# Podręcznik dewelopera\n\n```bash\ncd {root}\nsource .venv/bin/activate\npython -m pytest -q\n./scripts/update_project_docs.sh --with-tests\n```\n',
      'SESSION_HANDOFF.md':f'# Przekazanie projektu\n\n- Projekt: `{name}`\n- Wersja: `{version}`\n- Commit: `{head}`\n\n## Uzupełnij ręcznie\n- Cel sesji:\n- Wykonane zmiany:\n- Testy:\n- Wdrożenie:\n- Otwarte problemy:\n- Następny krok:\n'
    }
    for fn,content in defaults.items():
        p=docs/fn
        if not p.exists(): write(p,content)

    write(docs/'README.md','''# Dokumentacja projektu

- `AI_CONTEXT.md` — pamięć projektu dla nowej sesji.
- `PROJECT_CONTEXT.md` — bieżący kontekst.
- `ARCHITECTURE.md` — moduły i importy.
- `MODULE_REFERENCE.md` — klasy, funkcje i metody.
- `CHANGELOG.md` — historia Git.
- `TODO.md` — znaczniki TODO/FIXME/HACK/XXX.
- `ROADMAP.md` — plan rozwoju.
- `DEVELOPER_GUIDE.md` — praca z kodem.
- `OPERATIONS.md` — operacje i wdrożenie.
- `DECISIONS.md` — decyzje architektoniczne.
- `SESSION_HANDOFF.md` — przekazanie prac.

## Aktualizacja
```bash
./scripts/update_project_docs.sh --with-tests
```
''')
    print('\nGotowe:',docs)

if __name__=='__main__': main()
