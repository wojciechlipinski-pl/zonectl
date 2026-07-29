#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

# shellcheck source=lib.sh
. "$SCRIPT_DIR/lib.sh"

require_root

require_command python3
require_command git

SOURCE_DIR="$(realpath "${1:-$(pwd)}")"

[ -f "$SOURCE_DIR/pyproject.toml" ] \
    || die "Nie znaleziono pyproject.toml"

VERSION="$(read_project_version "$SOURCE_DIR")"

log "Rozpoczynam wdrożenie elkman-dns ${VERSION}"

prepare_system_directories

RELEASE_DIR="${RELEASES_DIR}/${VERSION}"

if [ -d "$RELEASE_DIR" ]; then
    die "Wydanie ${VERSION} już istnieje."
fi

cd "$SOURCE_DIR"

if [ -x "$SOURCE_DIR/.venv/bin/python" ]; then
    PYTHON="$SOURCE_DIR/.venv/bin/python"
else
    PYTHON="$(command -v python3)"
fi


log "Uruchamiam testy"

"$PYTHON" -m pytest

ok "Testy zakończone"

log "Czyszczenie artefaktów"

rm -rf build dist *.egg-info

log "Budowanie pakietu"

"$PYTHON" -m build

WHEEL="$(find dist -maxdepth 1 -name '*.whl' | head -1)"

[ -n "$WHEEL" ] || die "Nie zbudowano wheel"

ok "$WHEEL"

log "Tworzenie release"

mkdir -p "$RELEASE_DIR"

"$PYTHON" -m venv "$RELEASE_DIR/venv"

"$RELEASE_DIR/venv/bin/pip" install \
    --upgrade \
    pip \
    wheel

"$RELEASE_DIR/venv/bin/pip" install \
    "$WHEEL"

write_release_metadata \
    "$RELEASE_DIR" \
    "$VERSION" \
    "$SOURCE_DIR"

ok "Release przygotowany"

echo
echo "Nowe wydanie:"
echo "  $RELEASE_DIR"

echo
echo "Następny etap:"
echo "  verify + switch"

log "Weryfikacja nowego wydania"

"$SCRIPT_DIR/verify.sh" "$RELEASE_DIR"

CURRENT_TARGET="$(active_release_path || true)"

cleanup_on_error() {
    warn "Wdrożenie nie powiodło się"

    rm -rf "$RELEASE_DIR"

    if [ -n "${CURRENT_TARGET:-}" ] && [ -d "$CURRENT_TARGET" ]; then
        restore_release_links "$CURRENT_TARGET"
    fi
}

trap cleanup_on_error ERR

log "Przełączanie aktywnego wydania"

switch_release "$RELEASE_DIR"

log "Końcowa weryfikacja"

"$SCRIPT_DIR/verify.sh"

print_release_summary "$VERSION" "$RELEASE_DIR"

ok "Wdrożenie zakończone pomyślnie"

trap - ERR
