#!/bin/sh
set -eu
[ "$(id -u)" -eq 0 ] || { echo "Uruchom jako root." >&2; exit 1; }
rm -f /usr/local/bin/elkman-dns
if [ -L /usr/local/sbin/elkman-dns ]; then rm -f /usr/local/sbin/elkman-dns; fi
rm -rf /usr/local/lib/elkman_dns_toolkit
echo "Odinstalowano elkman DNS Toolkit 3.0.0-sprint1. Kopii *.bak-* nie usunięto."
