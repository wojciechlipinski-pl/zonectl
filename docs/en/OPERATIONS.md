# Operations guide

[English](OPERATIONS.md) | [Polski](../OPERATIONS.md)

For incident triage and complete host restoration, see the separate
[disaster-recovery runbook](DISASTER_RECOVERY.md).

This guide describes safe operating procedures for ZoneCTL 4.7. Examples use
`example.pl`; replace it with the intended zone only after reviewing the plan.

## Core rules

- Run BIND-changing commands as `root`.
- Check the active ZoneCTL version, Git state and BIND service before a change.
- Run a plan or dry-run first.
- Never combine unrelated production changes in one transaction.
- Retain transaction backups and manifests until external DNS checks pass.
- Do not manually alter KASP key files.
- ZoneCTL never changes registrar DS records automatically.

Basic checks:

```bash
zctl --version
named-checkconf
systemctl is-active bind9
rndc status
```

## Read-only mode

Enable the global write lock while diagnosing a server or granting an operator
inspection-only access:

```ini
[toolkit]
read_only = yes
```

The TUI still displays zones, status, pending changes and transaction history.
Commit and rollback operations return `READ-ONLY`. Validation without commit
remains available.

## Concurrent editing lock

ZoneCTL uses `flock` metadata under `/var/lib/zonectl/edit-locks`. A second
writer cannot open the same zone. Kernel locks are released automatically if a
process crashes; read-only sessions do not acquire edit locks.

## Verify a zone

```bash
zctl tx verify example.pl
rndc zonestatus example.pl
dig @127.0.0.1 example.pl SOA +short
```

For authoritative checks use `+norecurse`. Compare SOA serials on every
configured secondary after a change.

## Transaction history and recovery

```bash
zctl tx history example.pl --limit 20
zctl tx show TRANSACTION_ID
zctl tx history example.pl --events --limit 20
zctl tx backups example.pl
```

Each committed operation has its own backup and JSON manifest. A failed write
stops subsequent work and reports whether rollback completed. Multi-zone
sessions use separate transactions per zone and do not claim cross-zone
atomicity.

## Record changes

```bash
zctl tx check example.pl
zctl tx apply example.pl --source /root/example.pl.new
zctl tx apply example.pl --source /root/example.pl.new --commit
```

The normal flow is:

1. inspect current zone status;
2. prepare a candidate;
3. validate syntax and zone-wide consistency;
4. inspect the diff;
5. explicitly commit;
6. verify BIND and authoritative answers.

Zone-wide validation checks apex SOA/NS, CNAME conflicts and loops, duplicate
records, local targets and required glue. The final candidate also passes
`named-checkzone`.

## Zone lifecycle

### Create

```bash
zctl zone create-plan example.pl \
  --primary-ns ns1.example.net. \
  --admin hostmaster.example.net. \
  --ns ns1.example.net. \
  --ns ns2.example.net. \
  --ipv4 192.0.2.10 \
  --www
```

Creation uses a zone file plus a dedicated declaration in
`/etc/bind/zonectl-zones.d`. The managed index contains one include per zone.
The TUI wizard provides the same preview and confirmation sequence.

### Disable, restore and quarantine

```bash
zctl zone disable --help
zctl zone restore --help
zctl zone quarantine --help
zctl zone quarantine-restore --help
zctl zone inventory
zctl zone safety
```

Disable is reversible. Quarantine first builds and verifies a package, then
removes working copies. Restore requires an explicitly selected package.
Ordinary lifecycle operations reject RPZ and DNSSEC-managed zones.

## Migrating legacy declarations

Inventory and plans are read-only:

```bash
zctl zone migration-inventory
zctl zone migration-plan example.pl
zctl zone migration-apply example.pl
```

Commit only after reviewing all three diffs:

```bash
zctl zone migration-apply example.pl \
  --commit --activate --confirm example.pl
```

The transaction backs up `named.conf.local`, the managed index and the target
declaration, writes atomically, runs `named-checkconf`, calls `rndc reconfig`
and verifies `rndc zonestatus`. It preserves the zone file and SOA serial.
Automatic RPZ, secondary and DNSSEC declarations are blocked from this generic
migration profile.

## ACL inventory and audit

```bash
zctl bind inventory
zctl bind inventory --json
zctl bind audit
```

The audit detects malformed addresses and prefixes, duplicate entries,
unresolved references and incomplete secondary definitions. Reports are
read-only.

### Plan and apply an ACL

Replacement/cleanup workflow:

```bash
zctl bind acl-plan trusted \
  --replace 198.51.100/24=198.51.100.0/24

zctl bind acl-apply trusted \
  --replace 198.51.100/24=198.51.100.0/24
```

Full target list workflow:

```bash
zctl bind acl-plan trusted \
  --entry localhost \
  --entry 192.0.2.0/24

zctl bind acl-apply trusted \
  --entry localhost \
  --entry 192.0.2.0/24 \
  --commit --activate --confirm trusted
```

Full-list validation supports IPv4, IPv6, CIDR, negation and named ACL
elements. It rejects invalid entries and duplicates. `trusted` must retain
`localhost` and cannot be empty.

In the TUI press `F9`, select the ACL, then use `F3` for impact and `F4` for
the editor. `Insert` adds, `F4` edits, `F8/Delete` removes and `F2` proceeds to
the plan and dry-run.

## Secondary groups

### Report and edit addresses

```bash
zctl bind secondary-report
zctl bind secondary-plan dns2-notify --address 192.0.2.53
zctl bind secondary-apply dns2-notify --address 192.0.2.53
zctl bind secondary-apply dns2-notify \
  --address 192.0.2.53 \
  --commit --activate --confirm dns2-notify
```

The report connects definitions with their notify or transfer roles and lists
every affected zone. An address-list change is validated in an isolated BIND
configuration before the production transaction.

### Assign a zone to secondary pairs

```bash
zctl bind zone-secondary-plan example.pl --pair dns2 --pair he
zctl bind zone-secondary-apply example.pl --pair dns2 --pair he
zctl bind zone-secondary-apply example.pl \
  --pair dns2 --pair he \
  --commit --activate --confirm example.pl
```

A logical pair contains both notify and transfer groups. ZoneCTL updates
`also-notify` and `allow-transfer` together. Incomplete pairs, secondary zones
and RPZ are rejected. In zone details press `F5` for the equivalent TUI flow.

## DNSSEC: enablement

### Inspect and plan

```bash
zctl dnssec report example.pl
zctl dnssec enable-plan example.pl
zctl dnssec enable example.pl
```

The report reads BIND configuration, `rndc` KASP status, key files, DNSKEY,
RRSIG and public DS. The plan may migrate the writable source zone into
`/var/lib/bind/Primary`, add `dnssec-policy`, enable inline signing and set the
key directory.

### Activate signing

```bash
zctl dnssec enable example.pl \
  --commit --activate
```

Wait until ZoneCTL reports authoritative DNSKEY and RRSIG readiness. Check all
authoritative servers and multiple public resolvers:

```bash
zctl dnssec check-ds example.pl
```

Only then publish the exact SHA-256 DS at the registrar. After it is visible
and matches through all configured resolvers, confirm it to KASP:

```bash
zctl dnssec confirm-ds example.pl \
  --commit --acknowledge-published
```

Never confirm a DS merely because it was submitted to the registrar; require a
fresh public `PASS` result.

## DNSSEC: safe withdrawal

Withdrawal deliberately takes time. Do not bypass KASP gates.

### 1. Plan and create recovery material

```bash
zctl dnssec disable-plan example.pl
zctl dnssec withdrawal-backup example.pl
zctl dnssec withdrawal-backup example.pl --commit
```

Retain the verified package and its manifest.

### 2. Remove DS at the registrar

ZoneCTL cannot perform this step. After registrar removal, repeatedly check:

```bash
zctl dnssec withdrawal-check example.pl
```

Proceed only at `READY_FOR_WITHDRAWN`, when every configured resolver reports
that DS is absent.

### 3. Confirm withdrawal to KASP

```bash
zctl dnssec withdrawal-confirm example.pl \
  --commit --acknowledge-withdrawn
```

This is the only ZoneCTL command that calls `rndc dnssec -checkds withdrawn`.
It reruns the public check immediately before the call.

### 4. Enter the insecure policy stage

```bash
zctl dnssec disable-apply example.pl --stage insecure
zctl dnssec disable-apply example.pl \
  --stage insecure --commit --activate
```

Wait for KASP to remove DNSKEY and signatures. Follow the next-check timestamp
shown by `zctl dnssec report`.

### 5. Prepare an unsigned SOA serial

The unsigned source serial must be strictly greater than the signed serial
currently served to secondaries:

```bash
zctl dnssec prepare-finalize-serial example.pl
zctl dnssec prepare-finalize-serial example.pl --commit
```

This updates only the source file; it does not reload BIND.

### 6. Finalize

```bash
zctl dnssec disable-apply example.pl --stage finalize
zctl dnssec disable-apply example.pl \
  --stage finalize --commit --activate
```

Finalization requires hidden KASP DNSKEY and DS states plus a safe source SOA
serial. It removes DNSSEC directives, reloads BIND and verifies the unsigned
zone. Keys and recovery packages remain untouched.

### 7. External verification

```bash
rndc zonestatus example.pl
dig @ns1.example.net example.pl SOA +norecurse +short
dig @ns2.example.net example.pl DNSKEY +dnssec +norecurse
dig @1.1.1.1 example.pl DS +short
```

Confirm that all authoritative servers serve the new unsigned serial, no
DNSKEY remains and public resolvers return no DS.

## Debian package operations

Build:

```bash
dh clean --with python3 --buildsystem=pybuild
dpkg-buildpackage -b -us -uc
lintian ../zonectl_4.7.0-1_all.deb
```

Install or upgrade:

```bash
apt install ./zonectl_4.7.0-1_all.deb
/usr/bin/zctl --version
```

The package does not own `/etc/bind` or transaction backup directories, and
its maintainer scripts do not reconfigure BIND.

## Optional local zone-file Git history

This additional history is disabled by default. It accepts only files selected
for managed zones by ZoneCTL, rejects RPZ profiles and refuses any repository
with a configured remote. Enable it explicitly in `[toolkit]`:

```ini
git_history_enabled = yes
git_history_directory = /var/lib/zonectl/git-history
```

Always inspect the dry-run before confirming a write:

```bash
zctl git-history init
zctl git-history init --commit --confirm INITIALIZE
zctl git-history snapshot example.test
zctl git-history snapshot example.test --commit --confirm example.test
zctl git-history status
zctl git-history log --limit 20
```

Take a snapshot only after the transaction and BIND verification succeed.
Local Git is not used for rollback and never replaces transaction or full-host
backups.

## Post-change checklist

```bash
named-checkconf
systemctl is-active bind9
rndc status
zctl bind audit
```

For zone changes also verify `rndc zonestatus`, SOA answers on all
authoritative servers and, where applicable, DNSSEC validation through more
than one public resolver.

## Incident rule

If a transaction reports `ROLLBACK-FAILED`, stop further automation. Preserve
the manifest and backup, inspect ownership and permissions, validate the
restored candidate manually, then reload BIND only after `named-checkconf`
passes. Never delete key material or recovery packages while investigating.
