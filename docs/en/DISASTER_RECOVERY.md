# Disaster recovery

[English](DISASTER_RECOVERY.md) | [Polski](../DISASTER_RECOVERY.md)

This runbook covers recovery of a BIND server managed by ZoneCTL. ZoneCTL
transaction backups revert individual changes; they do not replace a full-host
backup containing `/etc/bind`, `/etc/zonectl`, `/var/lib/zonectl`,
`/var/log/zonectl` and `/var/backups/zonectl*`.

## First response

1. Stop planned DNS changes and do not run another `--commit`.
2. Record the incident time, the last operation and the result that exposed it.
3. Do not delete zone files, DNSSEC keys, manifests or backups.
4. Run read-only checks first. Select recovery for one zone, all of BIND or the
   complete host only after establishing the scope.

Collect a basic diagnostic bundle:

```bash
date --iso-8601=seconds
zctl --version
systemctl status bind9 --no-pager
named-checkconf -z
rndc status
journalctl -u bind9 --since "-30 minutes" --no-pager
zctl tx history --limit 20
```

Use `named` instead of `bind9` where applicable. Preserve the output away from
the affected host if its storage may be lost.

## Select the recovery path

- One zone failed after a ZoneCTL transaction: use transactional rollback.
- `named-checkconf -z` fails or BIND cannot start: restore configuration
  consistency without starting another transaction.
- The host or its disk is unavailable: restore the complete machine backup.
- DNSSEC withdrawal was in progress: preserve keys and the recovery package;
  do not change registrar DS data without repeating the checks.

## One zone — transactional rollback

Establish state and select a backup first:

```bash
zctl tx verify example.pl
zctl tx history example.pl --limit 20
zctl tx backups example.pl --limit 20
rndc zonestatus example.pl
dig @127.0.0.1 example.pl SOA +short
```

Copy the complete backup path printed by `zctl tx backups`; never select its
`.json` metadata file. Validate without changing the zone, then repeat with
explicit commit only after a successful dry-run:

```bash
zctl tx rollback example.pl --backup /complete/path/to/backup
zctl tx rollback example.pl --backup /complete/path/to/backup --commit
```

The committed rollback creates an additional `pre-rollback` backup of the
current file. Require status `ROLLBACK-COMMIT`, then repeat `zctl tx verify`,
`rndc zonestatus`, local SOA and BIND journal checks. The
[operator guide](OPERATIONS.md#transaction-history-and-recovery) explains the
transaction history and backup metadata.

## BIND cannot start

1. Preserve the current files and identify the first error:

   ```bash
   named-checkconf -z
   journalctl -u bind9 -b --no-pager
   ```

2. For a zone changed by ZoneCTL, use its last valid backup and run rollback
   without `--commit` first.
3. For a shared include, ACL, secondary or lifecycle declaration, keep the
   current files and use the matching backup and manifest from
   `/var/backups/zonectl-*`.
4. Require `named-checkconf -z` to pass before starting BIND.
5. Start and inspect BIND without making ZoneCTL changes:

   ```bash
   systemctl start bind9
   systemctl is-active bind9
   rndc status
   zctl domains
   ```

If files cannot be matched unambiguously with a manifest, stop manual recovery
and use a consistent full-machine backup.

## Host loss — full recovery

1. Restore into an isolated network, or keep BIND disabled, so two instances
   cannot answer simultaneously as the same authoritative server.
2. Restore one consistent point containing the OS, BIND configuration and all
   ZoneCTL directories listed at the beginning of this document.
3. Before admitting traffic, run:

   ```bash
   zctl --version
   dpkg-query -W -f='${Status} ${Version}\n' zonectl
   named-checkconf -z
   systemctl is-active bind9
   rndc status
   zctl domains
   ```

4. Compare local and authoritative SOA serials for every critical zone:

   ```bash
   rndc zonestatus example.pl
   dig @127.0.0.1 example.pl SOA +short
   dig @ns1.example.test example.pl SOA +short
   ```

5. Remove isolation or switch traffic only after validation. Keep the previous
   instance powered off but intact until verification is complete.

## DNSSEC and RPZ checks

For a signed zone, report state without forcing key rotation or withdrawal:

```bash
zctl dnssec report example.pl
dig @127.0.0.1 example.pl DNSKEY +dnssec
dig @127.0.0.1 example.pl SOA +dnssec
```

Confirm the `key-directory`, ownership and KASP state. During withdrawal,
preserve `/var/backups/zonectl-dnssec-withdrawal` and re-check public DS data
before any further step.

For managed RPZ, check its units, zone file and serial:

```bash
systemctl status zonectl-cert-rpz.timer --no-pager
systemctl status zonectl-cert-rpz.service --no-pager
named-checkconf -z
zctl bind environment-report
```

## Completion criteria

Recovery is complete only when:

- `named-checkconf -z` and required zone checks pass;
- BIND is active with no new load errors in its journal;
- SOA serials match the selected recovery point;
- DNSSEC reports show no missing keys or delegation mismatch;
- ZoneCTL history and manifests are available;
- the result, selected backup and every action are recorded in the incident
  report.

Exercise this runbook periodically on an isolated copy. A drill must not issue
`rndc` against production or expose the synthetic host to the production
network.
