# Odtwarzanie po awarii

[English](en/DISASTER_RECOVERY.md) | [Polski](DISASTER_RECOVERY.md)

Ten runbook opisuje odtwarzanie serwera BIND zarządzanego przez ZoneCTL.
Backupy transakcyjne ZoneCTL służą do cofania pojedynczych zmian. Nie
zastępują backupu całej maszyny obejmującego `/etc/bind`, `/etc/zonectl`,
`/var/lib/zonectl`, `/var/log/zonectl` i `/var/backups/zonectl*`.

## Zasady pierwszej reakcji

1. Zatrzymaj planowane zmiany DNS i nie wykonuj kolejnego `--commit`.
2. Zapisz czas awarii, ostatnią operację i wynik polecenia, które ją ujawniło.
3. Nie usuwaj plików stref, kluczy DNSSEC, manifestów ani backupów.
4. Najpierw wykonuj kontrole tylko do odczytu. Przywracanie rozpocznij dopiero
   po określeniu zakresu: jedna strefa, cały BIND albo cały host.

Zbierz podstawowy pakiet diagnostyczny:

```bash
date --iso-8601=seconds
zctl --version
systemctl status bind9 --no-pager
named-checkconf -z
rndc status
journalctl -u bind9 --since "-30 minutes" --no-pager
zctl tx history --limit 20
```

Jeżeli usługa nazywa się `named`, zastąp nią `bind9`. Zachowaj wyniki poza
odtwarzanym hostem, jeżeli istnieje ryzyko utraty jego dysku.

## Wybór ścieżki

- Błąd dotyczy jednej strefy po transakcji ZoneCTL: użyj ręcznego rollbacku.
- `named-checkconf -z` nie przechodzi lub BIND nie startuje: przywróć spójność
  konfiguracji BIND, nie uruchamiając kolejnych transakcji.
- Host albo jego dysk jest niedostępny: odtwórz pełną maszynę z backupu.
- Awaria wystąpiła podczas wycofywania DNSSEC: nie usuwaj kluczy ani pakietu
  odtworzeniowego i nie zmieniaj DS u rejestratora bez ponownej kontroli.

## Jedna strefa — rollback transakcyjny

Najpierw ustal stan i wybierz backup:

```bash
zctl tx verify example.pl
zctl tx history example.pl --limit 20
zctl tx backups example.pl --limit 20
rndc zonestatus example.pl
dig @127.0.0.1 example.pl SOA +short
```

Pełną procedurę, w tym wymagany dry-run, backup `pre-rollback` i kontrolę
serialu, opisuje rozdział [Ręczny rollback](OPERATIONS.md#ręczny-rollback).
Nie używaj pliku metadanych `.json` jako argumentu `--backup`.

## BIND nie uruchamia się

1. Nie nadpisuj konfiguracji „na próbę”. Ustal pierwszy błąd:

   ```bash
   named-checkconf -z
   journalctl -u bind9 -b --no-pager
   ```

2. Jeżeli błąd wskazuje strefę zmienioną przez ZoneCTL, skorzystaj z jej
   ostatniego poprawnego backupu i najpierw wykonaj rollback bez `--commit`.
3. Jeżeli uszkodzony jest wspólny include, ACL, secondary albo deklaracja
   cyklu życia strefy, zachowaj bieżące pliki i użyj backupu oraz manifestu
   odpowiadającego tej operacji z `/var/backups/zonectl-*`.
4. Przed uruchomieniem usługi wymagaj poprawnego wyniku:

   ```bash
   named-checkconf -z
   ```

5. Uruchom BIND i sprawdź stan bez wykonywania zmian ZoneCTL:

   ```bash
   systemctl start bind9
   systemctl is-active bind9
   rndc status
   zctl domains
   ```

Jeżeli nie można jednoznacznie powiązać plików z manifestem, przerwij ręczne
odtwarzanie i użyj spójnego backupu całej maszyny.

## Utrata hosta — odtworzenie pełne

1. Odtwórz maszynę w izolowanej sieci lub z zablokowaną usługą BIND, aby dwie
   instancje nie odpowiadały równocześnie jako ten sam serwer autorytatywny.
2. Odtwórz spójny punkt obejmujący system, konfigurację BIND oraz wszystkie
   katalogi ZoneCTL wymienione na początku dokumentu.
3. Przed dopuszczeniem ruchu sprawdź:

   ```bash
   zctl --version
   dpkg-query -W -f='${Status} ${Version}\n' zonectl
   named-checkconf -z
   systemctl is-active bind9
   rndc status
   zctl domains
   ```

4. Dla każdej krytycznej strefy porównaj serial lokalny i odpowiedzi serwerów
   autorytatywnych:

   ```bash
   rndc zonestatus example.pl
   dig @127.0.0.1 example.pl SOA +short
   dig @ns1.example.test example.pl SOA +short
   ```

5. Dopiero po poprawnej walidacji usuń izolację albo przełącz ruch na
   odtworzony host. Zachowaj poprzednią instancję wyłączoną, ale nienaruszoną,
   do zakończenia weryfikacji.

## Kontrole DNSSEC i RPZ

Po odtworzeniu strefy podpisanej uruchom raport, lecz nie wymuszaj rotacji ani
wycofania kluczy:

```bash
zctl dnssec report example.pl
dig @127.0.0.1 example.pl DNSKEY +dnssec
dig @127.0.0.1 example.pl SOA +dnssec
```

Sprawdź, czy odtworzono `key-directory`, prawa plików i stan KASP. Przy
trwającym wycofaniu zachowaj pakiet z
`/var/backups/zonectl-dnssec-withdrawal` i ponownie sprawdź publiczny DS przed
każdym dalszym krokiem.

Dla zarządzanej integracji RPZ sprawdź jednostki, plik strefy oraz jej serial:

```bash
systemctl status zonectl-cert-rpz.timer --no-pager
systemctl status zonectl-cert-rpz.service --no-pager
named-checkconf -z
zctl bind environment-report
```

## Kryteria zakończenia

Odtwarzanie jest zakończone dopiero, gdy:

- `named-checkconf -z` i kontrole wymaganych stref przechodzą poprawnie;
- BIND jest aktywny, a jego dziennik nie zawiera nowych błędów ładowania;
- seriale SOA są zgodne z oczekiwanym punktem odtworzenia;
- raporty DNSSEC nie wskazują utraty kluczy ani niespójności delegacji;
- historia i manifesty ZoneCTL są dostępne;
- wynik, użyty backup i wszystkie działania zostały zapisane w raporcie
  incydentu.

Runbook należy okresowo ćwiczyć na izolowanej kopii. Test nie może wykonywać
`rndc` wobec produkcji ani publikować syntetycznego hosta w sieci produkcyjnej.
