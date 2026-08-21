# Changelog

## 4.8.3 - 2026-08-21

### Added

- read-only ACL and secondary impact reports with affected roles, zones,
  candidate differences, dependency blockers and explicit risk levels
- operational secondary audits verifying authoritative SOA answers and serial
  agreement while keeping RPZ zones in their separate profile
- isolated rollback drills using the real `named-checkconf` validator without
  contacting production `rndc`

### Changed

- ACL, secondary-group and zone-assignment commits require an operator reason
- the TUI presents impact, risk and AA/SOA health before guarded changes
- the shared TUI text editor now handles the initial value, cursor movement,
  Home, End, Delete and xterm/PuTTY escape sequences consistently

### Safety

- high-risk removal of the final administration, query, recursion, transfer or
  notify endpoint is blocked before backup and configuration writes
- post-activation gates verify the active configuration and secondary SOA/AA
  state, with automatic rollback on failure
- audit manifests use an explicit field allowlist, redact secret material and
  record SHA-256, entries, UID, GID and file mode before and after operations
- forced-failure tests cover validation, activation, semantic and operational
  gates, successful rollback and `ROLLBACK-FAILED`

### Verified

- production validation used impact analysis, a no-change plan, dry-run,
  secondary health audit and configuration checksums without modifying BIND
- the DNSSEC test zone reached a fully active chain of trust with all KASP
  states and DS at `omnipresent`
- more than 700 automated tests pass before release packaging

## 4.8.2 - 2026-08-18

### Changed

- the read-only RPZ panel now distinguishes `ACTIVE`, `DELAYED`, `STALE`,
  `FAILED` and `DISABLED`, shows the previous and next timer runs, and gives a
  contextual operator recommendation
- a new read-only `bind rpz-managed-plan` command describes the future managed
  installation and blocks silent takeover of an existing external updater
- `bind rpz-external-migration-plan` inventories external artifacts by metadata
  and SHA-256 and designs a reversible cutover without stopping the live timer
- an isolated RPZ migration dry-run validates copied updater and unit candidates,
  the active zone and BIND configuration without writing system paths or switching timers
- the guarded RPZ migration transaction requires commit, activation and exact
  zone confirmation, verifies source hashes and restores the external timer on failure
- the post-activation gate verifies managed timer state, service result, RPZ
  serial and freshness, external timer shutdown and continued BIND availability
- environment discovery and the TUI automatically prefer installed ZoneCTL
  RPZ units and report `MANAGED` after a successful migration
- fresh installation rebases only the published `$ORIGIN hole.cert.pl.` onto
  the private RPZ zone, preserving relative triggers and the public sinkhole
- inaccessible root-owned MANAGED paths are reported as conflicts instead of
  raising `PermissionError` in read-only planning

### Verified

- a live external CERT Polska RPZ updater was migrated to `MANAGED`; the new
  timer remained enabled and active, the service returned `success`, the RPZ
  serial advanced, BIND stayed active and the previous timer was disabled
- DNSSEC workflows can advance through readiness refresh, DS publication
  checks and guarded KASP confirmation directly from the contextual TUI action
- the DNSSEC screen rediscovers the active BIND declaration after every
  operation, preventing a successfully enabled zone from remaining displayed
  as `UNSIGNED`
- fresh installation was verified on Debian 13: guarded commit, BIND load,
  277k+ nodes, active timer, successful updater, freshness gate and a real RPZ
  rewrite to the CERT Polska sinkhole

## 4.8.1 - 2026-08-13

### Changed

- replaced production DNS names in public examples, documentation, defaults
  and tests with reserved example domains
- added a mandatory release privacy checklist and an automated GitHub Actions
  public-data guard

### Safety

- a regression test rejects known production DNS namespaces in public project
  materials
- the release process now requires a staged-diff privacy review before tags
  and packages are published

### Verified

- the public-name audit returned no findings
- 614 automated tests passed before release preparation

## 4.8.0 - 2026-08-13

### Added

- read-only discovery of existing BIND configuration, managed declarations,
  legacy zones, DNSSEC zones and external RPZ integrations
- guarded first-run onboarding with plans, dry-runs, backups, validation,
  activation checks and rollback
- dedicated DNSSEC onboarding gates preserving policy, keys, KASP and the
  public chain of trust
- bulk read-only DNSSEC readiness audit and detailed blocker categories
- live CERT Polska RPZ freshness, timer, service, serial and node reporting

### Changed

- the complete TUI now follows the ZoneCTL 4.8 two-panel visual contract,
  including zones, records, environment, DNSSEC and transaction results
- context-sensitive footers expose only actions that are currently available
- onboarding lists refresh after every completed import

### Safety

- discovery and readiness reports never modify BIND
- legacy and DNSSEC imports remain separate, explicitly confirmed workflows
- existing external RPZ automation is detected and monitored without being
  overwritten or silently adopted
- managed CERT Polska RPZ installation is deliberately deferred until its
  root/systemd transaction and rollback have independent production tests

### Verified

- all legacy primary declarations were imported to per-zone managed files
  without changing their zone data or served SOA serials
- an active DNSSEC zone was imported with unchanged DNSKEY, DS, KASP policy
  and authoritative responses
- the production CERT Polska RPZ timer remained active and externally managed
- 613 automated tests passed before release preparation

## 4.7.0 - 2026-08-12

### Added

- inventory, planning and transactional migration of legacy zone declarations
  to one managed file per zone
- BIND ACL and secondary-group inventory, audit and impact reporting
- validated full-list ACL and secondary-group editing in CLI and TUI
- transactional assignment of primary zones to complete notify/transfer pairs
- Debian package metadata and the single supported `zctl` entry point

### Changed

- TUI exposes BIND access administration under `F9` and zone secondary
  assignment under `F5`
- ACL and secondary editors use the Midnight Commander key model
- managed declarations are indexed by `/etc/bind/zonectl-zones.conf`

### Safety

- all configuration writes use a plan, isolated `named-checkconf`, backup,
  atomic replacement, controlled `rndc reconfig`, manifest and rollback
- RPZ, DNSSEC and secondary declarations remain blocked from ordinary legacy
  migration
- `trusted` cannot be empty or lose `localhost`; invalid and duplicate ACL
  entries are rejected
- zone assignment always changes complete notify/transfer pairs

### Verified

- `nursery.example.pl` was migrated transactionally without changing its zone file,
  SOA serial or availability
- production `trusted` was corrected transactionally and passed the BIND audit
- production secondary groups and zone assignments passed read-only validation
- 556 automated tests passed before release preparation

## 4.6.0 - 2026-08-11

### Added

- read-only DNSSEC report covering BIND configuration, KASP, keys, DNSKEY,
  RRSIG, calculated DS and public DS visibility
- transactional DNSSEC enablement with planning, dry-run, backups, validation,
  activation checks and rollback
- multi-resolver DS verification and controlled KASP confirmation of published
  or withdrawn DS state
- verified recovery packages and a staged `insecure`/`finalize` DNSSEC
  withdrawal workflow
- DNSSEC status and guarded lifecycle actions in the TUI
- safe SOA serial preparation before serving an unsigned zone to secondaries

### Changed

- TUI shortcuts follow the Midnight Commander model: `Insert`, `F3`, `F4`,
  `F8`/`Delete`, `F2` and `F10`
- DNSSEC reports provide workflow stage, progress, earliest next check and a
  precise operator action
- long TUI messages wrap and scroll instead of being truncated

### Safety

- RPZ zones are blocked independently in CLI and TUI DNSSEC write workflows
- DNSSEC withdrawal cannot proceed until DS disappearance and required KASP
  states are confirmed by fresh checks
- finalization is blocked unless the source SOA serial is strictly newer than
  the serial currently served from the inline-signed zone
- key material and verified recovery packages are retained after finalization

### Verified

- DNSSEC enablement was completed and externally validated for `services.example.pl`
- DNSSEC withdrawal was completed for `legacy.example.pl`; all seven
  authoritative servers served unsigned serial `2026081101`, no authoritative
  DNSKEY remained, and DS was absent through three public resolvers
- 475 automated tests passed before release preparation

## 4.5.0 - 2026-07-31

### Added

- full-screen TUI wizard for creating and activating primary DNS zones
- shared high-contrast active-field styling for zone and record forms
- visible `▶` marker and current-field label with a monochrome fallback

### Changed

- the main TUI exposes zone creation under the `n` shortcut
- zone creation reuses the validated 4.4 lifecycle planner and transaction
- zone, add-record and edit-record forms now share consistent navigation cues

### Safety

- the wizard validates all values and displays the generated zone plan before
  asking for an explicit COMMIT confirmation
- cancellation leaves BIND configuration and zone files unchanged
- 330 automated tests pass before release preparation

## 4.4.0 - 2026-07-31

### Added

- side-effect-free plans and transactional CLI creation of primary zones
- one managed BIND declaration file per ZoneCTL-created zone
- transactional bootstrap of the managed BIND include structure
- reversible zone disable and restore operations with manifests and rollback
- protected quarantine packages containing zone data, declarations, metadata
  and SHA-256 checksums
- non-destructive restore from an explicitly selected quarantine package
- read-only inventory of disabled zones and every retained quarantine package
- zone safety report for RPZ, DNSSEC policy and inline-signing profiles

### Changed

- zone files inherit owner and group from the parent BIND zone directory
- lifecycle operations use explicit dry-run by default and require `--commit`
- production recovery guidance documents the role of Veeam VM backups
- the development branch now reflects the 4.4 zone-lifecycle scope

### Safety

- creation validates with `named-checkzone` and `named-checkconf` before BIND
  activation, then confirms the loaded zone with `rndc zonestatus`
- failures restore files and configuration to the pre-transaction state
- quarantine requires prior disablement, `--commit` and the full zone name
- automatic RPZ zones cannot enter ordinary lifecycle operations
- DNSSEC-policy and inline-signing zones are reported and conservatively
  blocked from ordinary lifecycle operations
- integration tests use real BIND validators in isolated temporary
  configurations without contacting the production `rndc`

### Verified

- the complete create, activate, disable, restore, quarantine and
  quarantine-restore sequence was exercised against BIND on `tanatos`
- recovery packages remain intact after restoration
- 325 automated tests pass before release preparation

## 4.3.0 - 2026-07-31

### Added

- advanced record filters with field matching, negation, regular expressions
  and TTL comparisons
- strict type-aware validation for IPv4, IPv6 and supported DNS record data
- zone-level consistency checks for SOA, NS, CNAME conflicts, loops,
  duplicates and missing local targets
- session-scoped bulk `SELECT`, `SET` and `DELETE` operations
- unified bulk-operation preview, confirmation and single-step undo
- transaction metadata describing bulk filters, actions and record counts
- multi-zone TUI sessions with persistent per-zone editing buffers
- validate-all workflow before committing changed zones in a multi-zone session

### Changed

- bulk changes are recorded as one transaction and presented by `zctl tx show`
- the main TUI supports selecting zones with Space and opening a multi-zone
  session with `m`
- record edits preserve relative owner notation and inline comments
- validation errors block changes while warnings require explicit confirmation

### Safety

- invalid record values and inconsistent zone structures are rejected before
  candidate installation
- all changed zones are validated before the first multi-zone COMMIT
- each zone retains its own lock, backup, manifest and rollback boundary
- multi-zone processing stops after the first failed transaction
- multi-zone sessions never claim cross-zone atomicity

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
