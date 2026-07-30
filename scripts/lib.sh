#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="zonectl"

APP_ROOT="/opt/zonectl"
RELEASES_DIR="${APP_ROOT}/releases"
CURRENT_LINK="${APP_ROOT}/current"
PREVIOUS_LINK="${APP_ROOT}/previous"

BIN_LINK="/usr/local/bin/zctl"
LEGACY_BIN_LINK="/usr/local/bin/elkman-dns"

CONFIG_DIR="/etc/elkman-dns-toolkit"
STATE_DIR="/var/lib/elkman-dns-toolkit"
LOG_DIR="/var/log/elkman-dns-toolkit"
BACKUP_DIR="/var/backups/elkman-dns"
DNSSEC_DS_DIR="${STATE_DIR}/ds"

log() {
    printf '\n==> %s\n' "$*"
}

ok() {
    printf 'OK: %s\n' "$*"
}

warn() {
    printf 'UWAGA: %s\n' "$*" >&2
}

die() {
    printf 'BŁĄD: %s\n' "$*" >&2
    exit 1
}

require_root() {
    if [ "$(id -u)" -ne 0 ]; then
        die "Uruchom skrypt jako root."
    fi
}

require_command() {
    local command_name="$1"

    if ! command -v "$command_name" >/dev/null 2>&1; then
        die "Brak wymaganego polecenia: $command_name"
    fi
}

read_project_version() {
    local source_dir="$1"

    python3 - "$source_dir/pyproject.toml" <<'PY'
from pathlib import Path
import sys
import tomllib

path = Path(sys.argv[1])
data = tomllib.loads(path.read_text(encoding="utf-8"))
print(data["project"]["version"])
PY
}

prepare_system_directories() {
    mkdir -p \
        "$RELEASES_DIR" \
        "$CONFIG_DIR" \
        "$STATE_DIR/backups" \
        "$STATE_DIR/transactions" \
        "$STATE_DIR/locks" \
        "$DNSSEC_DS_DIR" \
        "$BACKUP_DIR" \
        "$LOG_DIR"

    chmod 0755 \
        "$APP_ROOT" \
        "$RELEASES_DIR"

    chmod 0750 \
        "$CONFIG_DIR" \
        "$STATE_DIR" \
        "$STATE_DIR/backups" \
        "$STATE_DIR/transactions" \
        "$STATE_DIR/locks" \
        "$DNSSEC_DS_DIR" \
        "$BACKUP_DIR" \
        "$LOG_DIR"

    touch "$LOG_DIR/audit.jsonl"
    chmod 0640 "$LOG_DIR/audit.jsonl"
}

active_release_path() {
    if [ -L "$CURRENT_LINK" ]; then
        readlink -f "$CURRENT_LINK"
    fi
}

previous_release_path() {
    if [ -L "$PREVIOUS_LINK" ]; then
        readlink -f "$PREVIOUS_LINK"
    fi
}

relative_release_target() {
    local release_path="$1"

    printf 'releases/%s\n' "$(basename "$release_path")"
}

atomic_symlink() {
    local target="$1"
    local destination="$2"
    local temporary="${destination}.new.$$"

    rm -f "$temporary"
    ln -s "$target" "$temporary"
    mv -Tf "$temporary" "$destination"
}

switch_release() {
    local new_release="$1"
    local old_release=""

    if [ ! -d "$new_release" ]; then
        die "Katalog wydania nie istnieje: $new_release"
    fi

    if [ -L "$CURRENT_LINK" ]; then
        old_release="$(readlink -f "$CURRENT_LINK" || true)"
    fi

    if [ -n "$old_release" ] &&
       [ "$old_release" != "$new_release" ] &&
       [ -d "$old_release" ]; then
        atomic_symlink \
            "$(relative_release_target "$old_release")" \
            "$PREVIOUS_LINK"
    fi

    atomic_symlink \
        "$(relative_release_target "$new_release")" \
        "$CURRENT_LINK"

    atomic_symlink \
        "${CURRENT_LINK}/venv/bin/zctl" \
        "$BIN_LINK"
    atomic_symlink \
        "${CURRENT_LINK}/venv/bin/elkman-dns" \
        "$LEGACY_BIN_LINK"
}

restore_release_links() {
    local old_current="${1:-}"
    local old_previous="${2:-}"

    if [ -n "$old_current" ] && [ -d "$old_current" ]; then
        atomic_symlink \
            "$(relative_release_target "$old_current")" \
            "$CURRENT_LINK"
    else
        rm -f "$CURRENT_LINK"
    fi

    if [ -n "$old_previous" ] && [ -d "$old_previous" ]; then
        atomic_symlink \
            "$(relative_release_target "$old_previous")" \
            "$PREVIOUS_LINK"
    else
        rm -f "$PREVIOUS_LINK"
    fi

    if [ -L "$CURRENT_LINK" ]; then
        atomic_symlink \
            "${CURRENT_LINK}/venv/bin/zctl" \
            "$BIN_LINK"
    else
        rm -f "$BIN_LINK" "$LEGACY_BIN_LINK"
    fi
}

write_release_metadata() {
    local release_dir="$1"
    local version="$2"
    local source_dir="$3"

    local commit="unknown"
    local dirty="unknown"

    if git -C "$source_dir" rev-parse --is-inside-work-tree \
        >/dev/null 2>&1; then

        commit="$(git -C "$source_dir" rev-parse HEAD)"

        if git -C "$source_dir" diff --quiet &&
           git -C "$source_dir" diff --cached --quiet; then
            dirty="false"
        else
            dirty="true"
        fi
    fi

    cat > "$release_dir/RELEASE" <<META
APP_NAME=${APP_NAME}
VERSION=${version}
GIT_COMMIT=${commit}
GIT_DIRTY=${dirty}
BUILD_DATE=$(date --iso-8601=seconds)
PYTHON_VERSION=$(python3 --version 2>&1)
BUILD_HOST=$(hostname -f 2>/dev/null || hostname)
META

    printf '%s\n' "$version" > "$release_dir/VERSION"
}

print_release_summary() {
    local version="$1"
    local release_dir="$2"

    printf '\n'
    printf '%s\n' '----------------------------------------'
    printf 'ZoneCTL %s\n' "$version"
    printf '%s\n' '----------------------------------------'
    printf 'Wydanie:   %s\n' "$release_dir"
    printf 'Aktywne:   %s\n' "$CURRENT_LINK"
    printf 'Polecenie: %s\n' "$BIN_LINK"
}
