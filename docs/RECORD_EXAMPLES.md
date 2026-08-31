# Przykłady rekordów DNS

[English](en/RECORD_EXAMPLES.md) | [Polski](RECORD_EXAMPLES.md)

Poniższe przykłady odpowiadają wszystkim typom rekordów, które formularze
ZoneCTL 4.11 potrafią dodawać i edytować. Używają wyłącznie domen
przykładowych, sieci dokumentacyjnych i fikcyjnego materiału DNSSEC.

W formularzu podaj osobno nazwę, typ, TTL i wartość RDATA. `@` oznacza apex
bieżącej strefy. Nazwy docelowe zakończone kropką są bezwzględnymi nazwami DNS.

| Typ | Nazwa | TTL | RDATA |
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

## Ważne zależności

- `CNAME` nie może współistnieć pod tą samą nazwą z innymi danymi.
- Lokalne cele `NS`, `MX` i `SRV` powinny mieć rekord `A` lub `AAAA`; serwer
  nazw należący do delegowanej strefy może również wymagać glue u rodzica.
- `PTR` umieszcza się w odpowiedniej strefie odwrotnej, a jego nazwa jest
  etykietą adresu w tej strefie.
- `SVCB` i `HTTPS` z priorytetem `0` działają w AliasMode i nie przyjmują
  dodatkowych parametrów. Przykłady powyżej używają ServiceMode.
- Rekord `SOA` jest obowiązkowy i unikalny w apexie. W strefach zarządzanych
  nie twórz drugiego SOA; edytuj istniejący rekord.
- `DNSKEY` i `DS` pokazano wyłącznie jako przykłady składni. Dla stref
  podpisywanych przez BIND KASP nie wklejaj ręcznie kluczy wygenerowanych
  przez ZoneCTL/BIND ani nie publikuj DS bez ukończenia kontroli delegacji.
- Wartości `SSHFP` i `TLSA` muszą pochodzić z rzeczywistego klucza lub
  certyfikatu. Fikcyjne odciski z tabeli nie zapewniają bezpieczeństwa.

Walidator formularza sprawdza składnię i zależności strefy, ale kandydat przed
COMMIT zawsze musi dodatkowo przejść `named-checkzone`.
