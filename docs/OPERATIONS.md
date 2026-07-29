# Instrukcja operacyjna

Uruchomienie
cd /root/elkman-dns
source .venv/bin/activate
python -m elkman_dns --help

Dokładne polecenie produkcyjne należy sprawdzić w pyproject.toml
i skryptach wdrożeniowych.

Weryfikacja projektu
./scripts/verify.sh

Jeżeli skrypt istnieje i ma prawa wykonania:

chmod +x scripts/verify.sh
./scripts/verify.sh
Wdrożenie

Historia projektu wskazuje na skrypt:

scripts/deploy.sh

Przed jego wykonaniem:

git status
git log -1 --oneline
python -m pytest -q

Następnie przeczytać skrypt:

less scripts/deploy.sh

Nie uruchamiać skryptu wdrożeniowego bez sprawdzenia:

katalogów docelowych,
użytkownika systemowego,
kopii zapasowej,
praw dostępu,
konfiguracji BIND,
komend wykonywanych jako root.
Kontrola strefy po zapisie

Przykładowe polecenia:

rndc zonestatus NAZWA_STREFY
dig @127.0.0.1 SOA NAZWA_STREFY +short

W odpowiedzi dig numer seryjny SOA jest zwykle trzecim polem
po nazwie głównego serwera i adresie administratora.

Diagnostyka
journalctl -u bind9 --since '-15 minutes'
rndc status
rndc zonestatus NAZWA_STREFY
named-checkzone NAZWA_STREFY /sciezka/do/pliku.strefy

Nazwy usługi mogą różnić się zależnie od systemu, np. bind9 lub named.

Procedura przed zmianą produkcyjną
Wykonać kopię pliku strefy.
Sprawdzić aktualny SOA z BIND.
Sprawdzić stan Git projektu.
Uruchomić testy.
Wprowadzić zmianę.
Zweryfikować wynik aplikacji.
Sprawdzić plik strefy.
Sprawdzić SOA załadowany przez BIND.
Sprawdzić logi.
W razie błędu przywrócić kopię i ponownie załadować strefę.
