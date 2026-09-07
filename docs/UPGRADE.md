# Aktualizacja z GitHub Release

ZoneCTL udostępnia `scripts/install-latest-release.sh` do kontrolowanej
aktualizacji serwera produkcyjnego Debian. Najpierw wykonaj próbę odczytową:

```bash
sudo ./scripts/install-latest-release.sh --check
```

Jeżeli wszystkie kontrole zakończą się poprawnie, zainstaluj najnowsze
stabilne wydanie (bez draftów i prerelease):

```bash
sudo ./scripts/install-latest-release.sh
```

Możesz również wskazać konkretny stabilny tag:

```bash
sudo ./scripts/install-latest-release.sh --version v4.12.0
```

Skrypt pobiera pakiet Debian i `SHA256SUMS` z publicznego wydania
`wojciechlipinski-pl/zonectl`. Przed instalacją sprawdza sumę, nazwę, wersję
i architekturę pakietu oraz blokuje przypadkowy downgrade. Bezpośrednio przed
i po instalacji uruchamia `named-checkconf`, wymaga aktywnej usługi `bind9`,
a na końcu potwierdza wersję `zctl`. Nie modyfikuje bezpośrednio konfiguracji
BIND ani plików stref.

Wymagane polecenia: `curl`, `python3`, `sha256sum`, `dpkg`, `dpkg-deb`,
`dpkg-query`, `apt-get`, `flock`, `named-checkconf` i `systemctl`. Skrypt
uruchamiaj lokalnie na serwerze jako root lub przez `sudo`. Nie przekazuj
zdalnego skryptu bezpośrednio do powłoki roota przez `curl | sudo bash`.

## Nieudana kontrola końcowa

Jeżeli instalacja pakietu rozpoczęła się, ale kontrola końcowa nie przeszła:

```bash
dpkg-query -W zonectl
zctl --version
named-checkconf
systemctl status bind9 --no-pager
```

Skrypt nie wykonuje automatycznego downgrade'u. Poprzednią wersję instaluj
wyłącznie z osobno zweryfikowanego pakietu lub zaufanego źródła APT. Najpierw
ustal przyczynę błędu; pakiet ZoneCTL nie jest właścicielem `/etc/bind` i jego
instalacja nie powinna zmieniać konfiguracji ani stref.

`SHA256SUMS` opublikowany obok pakietu chroni przed uszkodzeniem transmisji.
Nie zastępuje weryfikacji repozytorium, tagu i workflow wydania, jeśli samo
konto GitHub znajduje się poza przyjętym modelem zaufania.
