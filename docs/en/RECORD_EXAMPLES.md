# DNS record examples

[English](RECORD_EXAMPLES.md) | [Polski](../RECORD_EXAMPLES.md)

These examples cover every record type that ZoneCTL 4.11 forms can add and
edit. They use only example domains, documentation networks and fictional
DNSSEC material.

Enter owner, type, TTL and RDATA separately in the form. `@` represents the
current zone apex. A trailing dot makes a target an absolute DNS name.

| Type | Owner | TTL | RDATA |
|---|---|---:|---|
| `A` | `www` | `3600` | `192.0.2.10` |
| `AAAA` | `www` | `3600` | `2001:db8::10` |
| `CAA` | `@` | `3600` | `0 issue "ca.example"` |
| `CNAME` | `portal` | `3600` | `www.example.test.` |
| `DNSKEY` | `@` | `3600` | `257 3 13 YWJjZA==` |
| `DS` | `child` | `3600` | `12345 13 2 ABABABABABABABABABABABABABABABABABABABABABABABABABABABABABABABAB` |
| `HTTPS` | `@` | `3600` | `1 svc.example.test. alpn=h2,h3 port=443` |
| `MX` | `@` | `3600` | `10 mail.example.test.` |
| `NAPTR` | `@` | `3600` | `10 20 "U" "E2U+sip" "!^.*$!sip:info@example.test!" .` |
| `NS` | `@` | `3600` | `ns1.example.test.` |
| `PTR` | `10` | `3600` | `host.example.test.` |
| `SOA` | `@` | `3600` | `ns1.example.test. hostmaster.example.test. 2026083101 3600 900 1209600 300` |
| `SRV` | `_https._tcp` | `3600` | `10 20 443 service.example.test.` |
| `SSHFP` | `host` | `3600` | `4 2 ABABABABABABABABABABABABABABABABABABABABABABABABABABABABABABABAB` |
| `SVCB` | `_dns` | `3600` | `1 resolver.example.test. alpn=dot port=853` |
| `TLSA` | `_443._tcp.www` | `3600` | `3 1 1 ABABABABABABABABABABABABABABABABABABABABABABABABABABABABABABABAB` |
| `TXT` | `_acme-challenge` | `300` | `"synthetic-validation-token"` |

## Important relationships

- `CNAME` cannot coexist with other data at the same owner name.
- Local `NS`, `MX` and `SRV` targets should have an `A` or `AAAA` record; an
  in-bailiwick delegated name server may also require parent-zone glue.
- Place `PTR` in the appropriate reverse zone; its owner is the address label
  within that zone.
- Priority `0` puts `SVCB` and `HTTPS` in AliasMode, which accepts no extra
  parameters. The table uses ServiceMode instead.
- `SOA` is mandatory and unique at the apex. Edit the existing SOA in a
  managed zone rather than creating another one.
- `DNSKEY` and `DS` demonstrate syntax only. With BIND KASP, never paste
  ZoneCTL/BIND-generated keys manually or publish DS before completing the
  delegation checks.
- `SSHFP` and `TLSA` values must be derived from the actual key or certificate.
  The fictional fingerprints in the table provide no security.

The form validator checks syntax and zone relationships, but every candidate
must also pass `named-checkzone` before COMMIT.
