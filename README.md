# ZoneCTL

> **Transactional DNS Management Toolkit for BIND 9**

[English](README.md) | [Polski](README.pl.md)

ZoneCTL is a terminal application for safely administering authoritative BIND
zones. It provides both a CLI and a curses TUI. Every supported write workflow
is designed around a preview, validation, backup, explicit confirmation,
atomic replacement and rollback.

## Current release

**4.8.3 — guarded BIND ACL and secondary operations**

## Highlights

- inspect, validate and edit DNS records in a full-screen TUI;
- transactional zone-file updates with `named-checkzone` and BIND activation;
- create, disable, restore and quarantine zones through guarded workflows;
- safely enable and withdraw DNSSEC using BIND KASP state gates;
- migrate legacy declarations to one managed include file per zone;
- inventory, audit and transactionally edit BIND ACLs and secondary groups;
- assign primary zones to complete notify/transfer secondary pairs;
- create backups and JSON manifests for configuration-changing operations;
- use read-only plans and dry-runs before every material change.
- install or migrate the optional CERT Polska RPZ integration transactionally,
  with five-minute updates, validation, monitoring and rollback.

## Requirements

- Debian 13 or another compatible Linux distribution;
- Python 3.11 or newer;
- BIND 9.20 or newer;
- `named-checkconf`, `named-checkzone`, `rndc` and `dig`;
- root privileges for operations that modify BIND.

The Debian package declares a lower bound of BIND 9.20 rather than pinning an
exact patch version.

## Installation

Install the Debian package attached to the GitHub release:

```bash
sudo apt install ./zonectl_4.8.3-1_all.deb
zctl --version
```

The package installs only the supported `zctl` command. The historical
`elkman-dns` entry point is no longer installed.

Development setup:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
PYTHONPATH=src .venv/bin/python -m pytest -q
```

## Quick start

```bash
zctl --version
zctl tui
zctl domains
zctl domains --grouped
```

Commands without their explicit commit flags are plans or dry-runs and do not
modify BIND.

## Midnight Commander-style TUI

The TUI uses familiar function keys:

| Key | Action |
|---|---|
| `Insert` | add a zone, record or list item |
| `F2` | validate and save / proceed to plan |
| `F3` | view records, details, impact or diff |
| `F4` | edit the selected item |
| `F5` | manage a zone's secondary assignments |
| `F6` | manage declaration migration |
| `F8` / `Delete` | remove the selected item |
| `F9` | open BIND ACL and secondary administration |
| `F10` / `Esc` | return or exit |

## Zone lifecycle

```bash
zctl zone create --help
zctl zone disable --help
zctl zone restore --help
zctl zone quarantine --help
zctl zone quarantine-restore --help
zctl zone inventory
zctl zone safety
```

ZoneCTL can create and activate a primary zone, reversibly disable it, restore
it and move verified data into quarantine. Ordinary lifecycle operations are
blocked for automatic RPZ zones and zones using `dnssec-policy` or
`inline-signing`.

## Record editing and transactions

```bash
zctl tx check example.pl
zctl tx apply example.pl --source /root/example.pl.new
zctl tx apply example.pl --source /root/example.pl.new --commit
zctl tx backups example.pl
zctl tx history example.pl
```

Candidate zones are checked before installation. Backups and transaction
manifests are retained for audit and recovery.

The record view supports structured filters, for example:

```text
type:A ttl>=3600
name:www -value:192.0.2.10
name~"^_acme" type:TXT
status:modified
```

## DNSSEC lifecycle

```bash
zctl dnssec report example.pl
zctl dnssec check-ds example.pl
zctl dnssec enable-plan example.pl
zctl dnssec enable example.pl
zctl dnssec confirm-ds example.pl
zctl dnssec disable-plan example.pl
zctl dnssec withdrawal-backup example.pl
zctl dnssec withdrawal-check example.pl
zctl dnssec withdrawal-confirm example.pl
zctl dnssec disable-apply example.pl --stage insecure
zctl dnssec prepare-finalize-serial example.pl
zctl dnssec disable-apply example.pl --stage finalize
```

The DNSSEC report combines BIND configuration, KASP state, key files, DNSKEY,
RRSIG, the locally calculated SHA-256 DS and public DS visibility. Guidance
shows the workflow stage, progress, the earliest safe recheck and the next
operator action.

Enabling DNSSEC requires both `--commit` and `--activate`. DS publication is
never automated. Withdrawal is staged: first verify that DS disappeared,
confirm withdrawal to KASP, switch to the built-in `insecure` policy, wait for
hidden KASP states, prepare a strictly newer unsigned SOA serial, and only then
finalize the BIND declaration. Key material and recovery packages are retained.

## Managed zone declarations

ZoneCTL-created and migrated zones use:

```text
/etc/bind/zonectl-zones.conf
/etc/bind/zonectl-zones.d/<zone>.conf
```

The first file is an include-only index; each managed zone has its own
declaration file.

```bash
zctl zone migration-inventory
zctl zone migration-plan example.pl
zctl zone migration-apply example.pl
zctl zone migration-apply example.pl \
  --commit --activate --confirm example.pl
```

Migration preserves the complete zone block and does not change the zone file
or SOA serial. RPZ, DNSSEC and secondary zones require separate profiles and
are blocked from ordinary migration.

## ACL and secondary administration

```bash
zctl bind inventory
zctl bind audit
zctl bind secondary-report
zctl bind acl-plan trusted --entry localhost --entry 192.0.2.0/24
zctl bind acl-apply trusted --entry localhost --entry 192.0.2.0/24
zctl bind secondary-plan dns2-notify --address 192.0.2.53
zctl bind secondary-apply dns2-notify --address 192.0.2.53
zctl bind zone-secondary-plan example.pl --pair dns2 --pair he
zctl bind zone-secondary-apply example.pl --pair dns2 --pair he
```

Full-list ACL validation rejects invalid entries and duplicates. The `trusted`
ACL cannot be empty or lose `localhost`. Secondary assignments operate on
complete logical notify/transfer pairs, so a zone cannot accidentally receive
only half of the required configuration.

## Read-only mode

```ini
[toolkit]
read_only = yes
```

Read-only mode permits inspection and validation while independently blocking
all commit and rollback operations.

## Safety model

For supported changes ZoneCTL uses this sequence:

1. discover the active BIND configuration;
2. build and display a deterministic candidate diff;
3. validate the candidate in isolation;
4. require explicit commit and activation flags or TUI confirmation;
5. verify that source files have not changed since planning;
6. create a protected backup;
7. atomically replace the configuration;
8. run BIND validators and controlled activation;
9. verify service or zone state;
10. write an audit manifest or restore the previous state on failure.

ZoneCTL does not publish or delete registrar DS records and does not silently
delete DNSSEC keys or recovery packages.

## Documentation

- [English operations guide](docs/en/OPERATIONS.md)
- [Polish operations guide](docs/OPERATIONS.md)
- [Polish README](README.pl.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Module reference](docs/MODULE_REFERENCE.md)
- [Changelog](CHANGELOG.md)

## Testing

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q
```

Release 4.8.3 passes more than 700 automated tests, including isolated BIND
validation, forced rollback gates and production read-only secondary audits.

## License

See the Debian copyright metadata in
[`debian/copyright`](debian/copyright) for licensing terms.
