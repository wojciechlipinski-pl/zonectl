# Safe screenshot specification

This document defines how public ZoneCTL screenshots must be produced. The
generator and images are planned for release 4.8.

## Mandatory isolation

Screenshot generation must not read production BIND configuration, zone
files, KASP state, environment-specific paths, the system hostname or operator
identity. It must run from deterministic fixtures in a temporary directory.

## Allowed example data

- zones: `example.test`, `demo.example`, `sample.invalid`;
- name servers: `ns1.example.test`, `ns2.example.test`;
- IPv4: `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`;
- IPv6: `2001:db8::/32`;
- documentation-only DNSSEC keys and DS values generated from fixtures;
- generic operator name `demo-operator`;
- temporary paths below `/tmp/zonectl-demo`.

No real domain, server name, public address, email address, username, key,
token, transaction identifier or production filesystem path may appear.

## Planned images

| File | View | Required content |
|---|---|---|
| `tui-main.png` | main zone list | mixed PASS/WARN states and example zones |
| `records-editor.png` | record editor | synthetic A, AAAA, MX, TXT and CAA records |
| `dnssec-status.png` | DNSSEC workflow | safe propagation stage and fictional DS |
| `bind-access.png` | ACL/secondary | documentation networks and logical pairs |
| `transaction-result.png` | transaction | plan, validation, backup and successful commit |
| `rollback-result.png` | controlled failure | rollback completed without production details |

## Presentation rules

- use one stable terminal size and font;
- retain the actual ZoneCTL color palette and key labels;
- do not manually redraw behavior that differs from the application;
- strip PNG metadata before committing;
- provide meaningful English alt text in `README.md` and Polish alt text in
  `README.pl.md`;
- regenerate images through a documented command rather than editing them by
  hand.

## Release gate

Before publication, scan source fixtures, rendered text and PNG metadata for
known production identifiers. Review every image at full resolution. A failed
privacy scan or visual review blocks the screenshot commit and the release.
