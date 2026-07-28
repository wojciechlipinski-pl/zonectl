#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "Uruchom instalator jako root: sudo ./install.sh" >&2
  exit 1
fi
SRC="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
LIB=/usr/local/lib/elkman_dns_toolkit
BIN=/usr/local/bin/elkman-dns
SBIN=/usr/local/sbin/elkman-dns
ETC=/etc/elkman-dns-toolkit
STATE=/var/lib/elkman-dns-toolkit
LOG=/var/log/elkman-dns-toolkit
STAMP="$(date +%Y%m%d-%H%M%S)"
command -v python3 >/dev/null 2>&1 || { echo "Brak python3" >&2; exit 1; }
for cmd in named-checkzone named-checkconf rndc dig; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "Brak wymaganego polecenia: $cmd" >&2; exit 1; }
done
python3 - <<'PY'
import curses
print("OK: Python i curses dostępne")
PY
if [ -e "$LIB" ]; then cp -a "$LIB" "${LIB}.bak-${STAMP}"; fi
if [ -e "$BIN" ] || [ -L "$BIN" ]; then cp -a "$BIN" "${BIN}.bak-${STAMP}"; fi
if [ -e "$SBIN" ] || [ -L "$SBIN" ]; then cp -a "$SBIN" "${SBIN}.bak-${STAMP}"; fi
mkdir -p /usr/local/lib /usr/local/bin /usr/local/sbin "$ETC" "$STATE/backups" "$STATE/transactions" "$STATE/locks" "$LOG"
chmod 0750 "$STATE" "$STATE/backups" "$STATE/transactions" "$STATE/locks" "$LOG"
touch "$LOG/audit.jsonl"
chmod 0640 "$LOG/audit.jsonl" 2>/dev/null || true
rm -rf "$LIB"
cp -a "$SRC/usr/local/lib/elkman_dns_toolkit" "$LIB"
install -m 0755 "$SRC/usr/local/bin/elkman-dns" "$BIN"
rm -f "$SBIN"
ln -s ../bin/elkman-dns "$SBIN"
if [ ! -e "$ETC/groups.yaml" ]; then
  install -m 0644 "$SRC/groups.yaml.example" "$ETC/groups.yaml"
fi
python3 -m compileall -q "$LIB"
version="$($BIN --version)"
case "$version" in *"3.1.0-sprint2-transaction"*) : ;; *) echo "BŁĄD testu instalacji: $version" >&2; exit 1;; esac
$BIN groups >/dev/null
$BIN tx --help >/dev/null

echo "Zainstalowano elkman DNS Toolkit 3.1.0-sprint2-transaction"
echo "Wersja: $version"
echo "Warstwa transakcyjna: elkman-dns tx --help"
echo "UWAGA: tx apply bez --commit wykonuje tylko dry-run."
