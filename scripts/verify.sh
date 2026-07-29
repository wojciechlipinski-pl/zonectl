#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

# shellcheck source=lib.sh
. "$SCRIPT_DIR/lib.sh"

require_root

RELEASE_PATH="${1:-$CURRENT_LINK}"

if [ -L "$RELEASE_PATH" ]; then
    RELEASE_PATH="$(readlink -f "$RELEASE_PATH")"
fi

[ -d "$RELEASE_PATH" ] || die "Nie znaleziono wydania: $RELEASE_PATH"

VENV="$RELEASE_PATH/venv"
PYTHON="$VENV/bin/python"
CLI="$VENV/bin/elkman-dns"

log "Weryfikacja wydania"

[ -x "$PYTHON" ] || die "Brak interpretera Python"
ok "Python"

[ -x "$CLI" ] || die "Brak programu elkman-dns"
ok "CLI"

VERSION="$("$CLI" --version)"
echo "CLI: $VERSION"

"$PYTHON" - <<'PY'
import elkman_dns

print("Pakiet:", elkman_dns.__version__)
PY

ok "Import pakietu"

echo
ok "VERIFY OK"
