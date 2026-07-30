# Changelog

## 4.2.0 - 2026-07-30

### Added

- unified diff preview before committing zone changes
- protected export of pending changes without modifying the active zone
- persistent transaction manifest history with CLI history and detail views
- undo of the latest change in the current editing session
- global read-only mode for diagnostics and restricted operator access
- exclusive per-zone editing locks with operator, host, PID and start-time metadata
- automatic recovery from stale editing-lock files after process failure

### Changed

- transaction results now use one presentation layer in CLI and TUI
- edited records preserve relative owner notation and inline comments
- the TUI clearly marks read-only sessions and hides write actions
- read-only sessions can inspect a zone without blocking other readers
- operational documentation now includes manual BIND rollback and editing-lock procedures

### Fixed

- failed `named-checkzone` validation cannot modify the active zone
- failed `rndc reload` restores the original zone file
- transaction audit completion no longer duplicates rollback metadata
- modal TUI messages wait for an explicit key press

### Safety

- concurrent writable sessions for the same zone are rejected
- `apply --commit` and `rollback --commit` are blocked in read-only mode
- transaction failure, rollback and Pending Changes commit paths have dedicated tests

## 4.1.2 - 2026-07-30

### Fixed

- function keys no longer close the main TUI unexpectedly
- F1-F5 sequences used by PuTTY's Linux terminal mode are recognized
- F10 now exits the main TUI intentionally; `q` and `Esc` remain available

## 4.1.1 - 2026-07-30

### Added

- configurable health profiles for zones
- RPZ health checks based on syntax, BIND load status and file age
- RPZ-specific status presentation in the TUI

### Changed

- `cert-rpz.local` no longer requires public SOA or DNSSEC checks
- package implementation moved to the `zonectl` namespace
- system paths migrated to the ZoneCTL directory layout

### Compatibility

- the `elkman-dns` command remains available with a deprecation warning
- the `elkman_dns` Python namespace remains as a compatibility shim

## 3.2.0 - 2026-07-29

### Added

- source-preserving BIND zone editor
- automatic discovery of primary zones from the active BIND configuration
- `ZoneDocument`, `ZoneDocumentAdapter` and `ZoneEditSession`
- transactional saving directly from the TUI
- automatic SOA serial increment
- save confirmation and detailed transaction result view
- project credits in the main TUI view
- release-based deployment under `/opt/elkman-dns/releases`

### Changed

- BIND configuration is now the primary source of truth for zone names and files
- `zones.conf` is now an optional override and compatibility layer
- CLI and TUI display the package version dynamically
- TUI receives `ToolkitConfig` and uses `TransactionEngine`
- package version updated to `3.2.0`

### Removed

- legacy root-level `install.sh`
- legacy root-level `uninstall.sh`
- hard-coded application versions in CLI and TUI
- model-specific identifier from project credits

## 3.1.0 - 2026-07-28

### Added

- transaction layer
- zone validation
- atomic zone installation
- automatic backup
- rollback support
- audit log
- transaction history
- dry-run mode
- BIND reload verification
