#!/usr/bin/env bash
set -Eeuo pipefail

readonly REPOSITORY="wojciechlipinski-pl/zonectl"
readonly API_ROOT="${ZONECTL_UPDATE_API_ROOT:-https://api.github.com/repos/${REPOSITORY}}"
readonly LOCK_FILE="${ZONECTL_UPDATE_LOCK_FILE:-/run/lock/zonectl-release-upgrade.lock}"

CHECK_ONLY=0
ALLOW_DOWNGRADE=0
REQUESTED_TAG=""
WORK_DIR=""
INSTALL_STARTED=0
INSTALLED_VERSION=""

usage() {
    cat <<'EOF'
Usage: sudo ./install-latest-release.sh [OPTIONS]

Download, verify and install a stable ZoneCTL Debian release from GitHub.

Options:
  --check                 verify availability without installing
  --version vX.Y.Z        install this stable release instead of latest
  --allow-downgrade       permit installing an older package version
  -h, --help              show this help
EOF
}

die() {
    printf 'ERROR: %s\n' "$*" >&2
    return 1
}

log() {
    printf '==> %s\n' "$*"
}

cleanup() {
    if [ -n "$WORK_DIR" ] && [ -d "$WORK_DIR" ]; then
        rm -rf -- "$WORK_DIR"
    fi
}

report_failure() {
    status=$?
    if [ "$INSTALL_STARTED" -eq 1 ]; then
        printf '\nERROR: installation started but final verification failed.\n' >&2
        printf 'ZoneCTL does not automatically downgrade packages.\n' >&2
        printf 'Inspect: dpkg-query -W zonectl; zctl --version; named-checkconf; systemctl status bind9\n' >&2
        if [ -n "$INSTALLED_VERSION" ]; then
            printf 'Previous package version was: %s\n' "$INSTALLED_VERSION" >&2
            printf 'Reinstall it only from a separately verified package or trusted APT source.\n' >&2
        fi
    fi
    return "$status"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --check) CHECK_ONLY=1 ;;
        --version)
            [ "$#" -ge 2 ] || die "--version requires a tag"
            REQUESTED_TAG="$2"
            shift
            ;;
        --allow-downgrade) ALLOW_DOWNGRADE=1 ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown option: $1" ;;
    esac
    shift
done

[ "$(id -u)" -eq 0 ] || die "run this script as root (sudo)"

for command in curl python3 sha256sum dpkg dpkg-deb dpkg-query apt-get flock; do
    command -v "$command" >/dev/null 2>&1 || die "required command not found: $command"
done

exec 9>"$LOCK_FILE"
flock -n 9 || die "another ZoneCTL upgrade is already running"

WORK_DIR="$(mktemp -d /tmp/zonectl-release-upgrade.XXXXXX)"
trap cleanup EXIT
trap report_failure ERR

if [ -n "$REQUESTED_TAG" ]; then
    case "$REQUESTED_TAG" in
        v[0-9]*.[0-9]*.[0-9]*) ;;
        *) die "invalid release tag: $REQUESTED_TAG" ;;
    esac
    RELEASE_URL="${API_ROOT}/releases/tags/${REQUESTED_TAG}"
else
    RELEASE_URL="${API_ROOT}/releases/latest"
fi

log "Reading release metadata"
curl --fail --silent --show-error --location \
    --retry 3 --retry-all-errors \
    -H 'Accept: application/vnd.github+json' \
    -H 'X-GitHub-Api-Version: 2022-11-28' \
    "$RELEASE_URL" >"$WORK_DIR/release.json"

mapfile -t RELEASE_DATA < <(python3 - "$WORK_DIR/release.json" <<'PY'
import json
import re
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    release = json.load(stream)

tag = release.get("tag_name", "")
if release.get("draft") or release.get("prerelease"):
    raise SystemExit("release is not stable")
match = re.fullmatch(r"v(\d+\.\d+\.\d+)", tag)
if not match:
    raise SystemExit(f"unexpected release tag: {tag!r}")
version = match.group(1)
expected = {
    "SHA256SUMS",
    f"zonectl_{version}-1_all.deb",
}
assets = {
    asset.get("name"): asset.get("browser_download_url")
    for asset in release.get("assets", [])
}
missing = sorted(expected - assets.keys())
if missing:
    raise SystemExit("missing release assets: " + ", ".join(missing))
print(tag)
print(version)
print(assets["SHA256SUMS"])
print(assets[f"zonectl_{version}-1_all.deb"])
PY
)

[ "${#RELEASE_DATA[@]}" -eq 4 ] || die "invalid release metadata"
TAG="${RELEASE_DATA[0]}"
VERSION="${RELEASE_DATA[1]}"
SUMS_URL="${RELEASE_DATA[2]}"
DEB_URL="${RELEASE_DATA[3]}"
DEB_NAME="zonectl_${VERSION}-1_all.deb"
DEB_PATH="$WORK_DIR/$DEB_NAME"

log "Downloading ZoneCTL ${VERSION}"
curl --fail --silent --show-error --location --retry 3 --retry-all-errors \
    "$SUMS_URL" --output "$WORK_DIR/SHA256SUMS"
curl --fail --silent --show-error --location --retry 3 --retry-all-errors \
    "$DEB_URL" --output "$DEB_PATH"

log "Verifying SHA-256"
EXPECTED_SUM="$(awk -v file="$DEB_NAME" '$2 == file || $2 == "*" file {print $1}' "$WORK_DIR/SHA256SUMS")"
[ -n "$EXPECTED_SUM" ] || die "$DEB_NAME is absent from SHA256SUMS"
printf '%s  %s\n' "$EXPECTED_SUM" "$DEB_NAME" | (cd "$WORK_DIR" && sha256sum --check -)

PACKAGE="$(dpkg-deb -f "$DEB_PATH" Package)"
PACKAGE_VERSION="$(dpkg-deb -f "$DEB_PATH" Version)"
ARCHITECTURE="$(dpkg-deb -f "$DEB_PATH" Architecture)"
[ "$PACKAGE" = "zonectl" ] || die "unexpected package: $PACKAGE"
[ "$PACKAGE_VERSION" = "${VERSION}-1" ] || die "unexpected package version: $PACKAGE_VERSION"
[ "$ARCHITECTURE" = "all" ] || die "unexpected package architecture: $ARCHITECTURE"

INSTALLED_VERSION="$(dpkg-query -W -f='${Version}' zonectl 2>/dev/null || true)"
if [ -n "$INSTALLED_VERSION" ]; then
    log "Installed: $INSTALLED_VERSION; available: $PACKAGE_VERSION"
    if dpkg --compare-versions "$INSTALLED_VERSION" gt "$PACKAGE_VERSION" \
        && [ "$ALLOW_DOWNGRADE" -ne 1 ]; then
        die "downgrade refused; use --allow-downgrade only after explicit review"
    fi
    if dpkg --compare-versions "$INSTALLED_VERSION" eq "$PACKAGE_VERSION"; then
        log "ZoneCTL ${VERSION} is already installed"
        exit 0
    fi
else
    log "ZoneCTL is not currently installed"
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
    log "Verified stable release $TAG; no changes made"
    exit 0
fi

command -v named-checkconf >/dev/null 2>&1 || die "named-checkconf is required for production validation"
command -v systemctl >/dev/null 2>&1 || die "systemctl is required for production validation"

log "Validating BIND before upgrade"
named-checkconf
systemctl is-active --quiet bind9 || die "bind9 is not active before upgrade"

log "Installing $DEB_NAME"
INSTALL_STARTED=1
DEBIAN_FRONTEND=noninteractive apt-get install --yes "$DEB_PATH"

log "Validating installation"
ACTUAL_VERSION="$(zctl --version)"
[ "$ACTUAL_VERSION" = "zctl $VERSION" ] || die "unexpected zctl version: $ACTUAL_VERSION"
named-checkconf
systemctl is-active --quiet bind9 || die "bind9 is not active after upgrade"

log "Upgrade complete: $ACTUAL_VERSION ($PACKAGE_VERSION)"
INSTALL_STARTED=0
