# Historia zmian

Dokument generowany z historii Git.

## Wydania

### Release 3.2.3: add F2 save support

- Data: `2026-07-29`
- Commit: `66802d0`
- Autor: `Wojciech Lipiński`

```text
pyproject.toml                           |  2 +-
 src/elkman_dns/__init__.py               |  2 +-
 src/elkman_dns/ui/curses_app.py          | 92 ++++++++++++++++++++++++++++++--
 src/elkman_dns/ui/records/keybindings.py |  1 +
 4 files changed, 90 insertions(+), 7 deletions(-)
```

### Release 3.2.0: transactional zone editor and BIND discovery

- Data: `2026-07-29`
- Commit: `7ac71d2`
- Autor: `Wojciech Lipiński`

```text
.gitignore                                   |  47 ++-
 CHANGELOG.md                                 |  28 ++
 install.sh                                   |  48 ---
 pyproject.toml                               |   2 +-
 scripts/deploy.sh                            | 119 ++++++
 scripts/lib.sh                               | 218 ++++++++++
 scripts/verify.sh                            |  43 ++
 src/elkman_dns/__init__.py                   |   2 +-
 src/elkman_dns/cli.py                        |   9 +-
 src/elkman_dns/core/config.py                | 360 ++++++++++++-----
 src/elkman_dns/core/discovery.py             | 574 +++++++++++++++++++++++++++
 src/elkman_dns/core/soa_serial.py            | 219 ++++++++++
 src/elkman_dns/core/zone_document.py         |  84 ++++
 src/elkman_dns/core/zone_document_adapter.py | 177 +++++++++
 src/elkman_dns/core/zone_edit_session.py     | 241 +++++++++++
 src/elkman_dns/core/zone_file_parser.py      | 457 +++++++++++++++++++++
 src/elkman_dns/core/zone_serializer.py       | 311 +++++++++++++++
 src/elkman_dns/core/zone_writer.py           | 196 +++++++++
 src/elkman_dns/ui/credits.py                 | 101 +++++
 src/elkman_dns/ui/curses_app.py              | 237 ++++++++++-
 tests/test_config_discovery.py               | 223 +++++++++++
 tests/test_discovery.py                      | 243 ++++++++++++
 tests/test_soa_serial.py                     | 102 +++++
 tests/test_zone_document_adapter.py          | 262 ++++++++++++
 tests/test_zone_edit_session.py              | 382 ++++++++++++++++++
 tests/test_zone_file_parser.py               | 200 ++++++++++
 tests/test_zone_serializer.py                | 185 +++++++++
 tests/test_zone_writer.py                    | 248 ++++++++++++
 uninstall.sh                                 |   7 -
 29 files changed, 5148 insertions(+), 177 deletions(-)
```

### Baseline 3.1.0 transaction layer

- Data: `2026-07-28`
- Commit: `0e7fb2f`
- Autor: `Wojciech Lipiński`

```text
README.md                                          |  78 +++
 groups.yaml.example                                |  17 +
 install.sh                                         |  48 ++
 uninstall.sh                                       |   7 +
 usr/local/bin/elkman-dns                           |   4 +
 usr/local/lib/elkman_dns_toolkit/__init__.py       |   2 +
 usr/local/lib/elkman_dns_toolkit/cli.py            | 161 +++++
 usr/local/lib/elkman_dns_toolkit/core/__init__.py  |   1 +
 usr/local/lib/elkman_dns_toolkit/core/audit.py     |  78 +++
 usr/local/lib/elkman_dns_toolkit/core/bind.py      |  72 ++
 usr/local/lib/elkman_dns_toolkit/core/config.py    | 125 ++++
 usr/local/lib/elkman_dns_toolkit/core/models.py    |  36 +
 usr/local/lib/elkman_dns_toolkit/core/runner.py    |  28 +
 .../lib/elkman_dns_toolkit/core/transaction.py     | 319 +++++++++
 usr/local/lib/elkman_dns_toolkit/legacy_v220.py    | 779 +++++++++++++++++++++
 usr/local/lib/elkman_dns_toolkit/ui/__init__.py    |   1 +
 usr/local/lib/elkman_dns_toolkit/ui/curses_app.py  | 309 ++++++++
 17 files changed, 2065 insertions(+)
```

## Pełna chronologia funkcjonalna

- `2026-07-29` — `66802d0` — **Release 3.2.3: add F2 save support**
- `2026-07-29` — `7ac71d2` — **Release 3.2.0: transactional zone editor and BIND discovery**
- `2026-07-29` — `168a4e5` — **Sprint 4.8: extract record view controller**
- `2026-07-29` — `a3be91e` — **Sprint 4.7: complete record change tracking and F2 editing**
- `2026-07-29` — `ff5093e` — **Sprint 4.7: support deleting DNS records**
- `2026-07-29` — `1998add` — **Sprint 4.6: add NewRecordDialog and improve record editor UX**
- `2026-07-28` — `7d9a41a` — **Sprint 4.5: extract RecordEditor from CursesApp**
- `2026-07-28` — `87d8d2a` — **Sprint 4.3: record editor and pending changes view**
- `2026-07-28` — `c4612ee` — **Sprint 4.4: centralize record view keybindings**
- `2026-07-28` — `6b00880` — **Sprint 4.0: ZoneModel and dialog extraction**
- `2026-07-28` — `61272e3` — **feat: add domain and record search**
- `2026-07-28` — `5a1ea88` — **feat: parse and display zone records**
- `2026-07-28` — `6131629` — **feat: add zone records view**
- `2026-07-28` — `ea7eef0` — **feat: add zone details view to TUI**
- `2026-07-28` — `bf92425` — **chore: ignore backup files**
- `2026-07-28` — `d37165e` — **feat: discover zones from BIND configuration**
- `2026-07-28` — `6ec23e9` — **Merge branch 'sprint-3.2.0'**
- `2026-07-28` — `93ef9e0` — **Sprint 3.2: add verify command and shared zone verification**
- `2026-07-28` — `d9b518e` — **Merge Sprint 3.1.3**
- `2026-07-28` — `96f4631` — **Sprint 3.1.3: verify loaded SOA serial for inline-signing zones**
- `2026-07-28` — `2e42b61` — **Merge Sprint 3.1.2: transaction status**
- `2026-07-28` — `ae227e3` — **Add transaction status to results**
- `2026-07-28` — `46b89b2` — **Merge Sprint 3.1.1: no-change detection**
- `2026-07-28` — `e37466c` — **Detect unchanged zone before commit**
- `2026-07-28` — `036b012` — **Refactor project to standard Python package layout**
- `2026-07-28` — `91246bb` — **Add project metadata and repository files**
- `2026-07-28` — `0e7fb2f` — **Baseline 3.1.0 transaction layer**

## Ważna zasada

Ten plik opisuje to, co znajduje się w Git. Nie należy dopisywać funkcji, których nie potwierdza kod lub historia repozytorium.
