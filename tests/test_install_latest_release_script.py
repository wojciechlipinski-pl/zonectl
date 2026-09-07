import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install-latest-release.sh"


def _executable(path: Path, text: str) -> None:
    path.write_text("#!/usr/bin/env bash\nset -eu\n" + text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def updater_env(tmp_path: Path) -> tuple[dict[str, str], Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    deb = tmp_path / "zonectl_4.12.0-1_all.deb"
    deb.write_bytes(b"synthetic Debian package fixture\n")
    digest = hashlib.sha256(deb.read_bytes()).hexdigest()
    sums = tmp_path / "SHA256SUMS"
    sums.write_text(f"{digest}  {deb.name}\n", encoding="ascii")
    release = tmp_path / "release.json"
    release.write_text(
        json.dumps(
            {
                "tag_name": "v4.12.0",
                "draft": False,
                "prerelease": False,
                "assets": [
                    {
                        "name": "SHA256SUMS",
                        "browser_download_url": "https://assets.invalid/SHA256SUMS",
                    },
                    {
                        "name": deb.name,
                        "browser_download_url": f"https://assets.invalid/{deb.name}",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    _executable(fake_bin / "id", 'printf "0\\n"\n')
    _executable(
        fake_bin / "curl",
        r"""
if [ "${FAKE_CURL_FAIL:-0}" = 1 ]; then exit 22; fi
output=""; url=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --output) output="$2"; shift ;;
        http*) url="$1" ;;
    esac
    shift
done
case "$url" in
    */releases/latest|*/releases/tags/*) source="$FAKE_RELEASE_JSON" ;;
    */SHA256SUMS) source="$FAKE_SUMS" ;;
    *.deb) source="$FAKE_DEB" ;;
    *) exit 22 ;;
esac
if [ -n "$output" ]; then cp "$source" "$output"; else cat "$source"; fi
""",
    )
    _executable(
        fake_bin / "dpkg-deb",
        r"""
case "${@: -1}" in
    Package) printf '%s\n' "${FAKE_PACKAGE:-zonectl}" ;;
    Version) printf '%s\n' "${FAKE_PACKAGE_VERSION:-4.12.0-1}" ;;
    Architecture) printf '%s\n' "${FAKE_ARCHITECTURE:-all}" ;;
    *) exit 2 ;;
esac
""",
    )
    _executable(
        fake_bin / "dpkg-query",
        '[ -n "${FAKE_INSTALLED_VERSION:-}" ] || exit 1\nprintf "%s" "$FAKE_INSTALLED_VERSION"\n',
    )
    _executable(
        fake_bin / "dpkg",
        'case "$3" in gt) [ "${FAKE_DPKG_GT:-0}" = 1 ] ;; eq) [ "${FAKE_DPKG_EQ:-0}" = 1 ] ;; *) exit 2 ;; esac\n',
    )
    _executable(
        fake_bin / "apt-get",
        'printf "%s\\n" "$*" >>"$FAKE_STATE/apt-get"\n[ "${FAKE_APT_FAIL:-0}" != 1 ]\n',
    )
    _executable(
        fake_bin / "named-checkconf",
        r"""
count_file="$FAKE_STATE/named-count"; count=0
[ ! -f "$count_file" ] || count="$(cat "$count_file")"
count=$((count + 1)); printf '%s\n' "$count" >"$count_file"
[ "${FAKE_NAMED_FAIL_CALL:-0}" != "$count" ]
""",
    )
    _executable(fake_bin / "systemctl", '[ "${FAKE_BIND_ACTIVE:-1}" = 1 ]\n')
    _executable(
        fake_bin / "zctl", 'printf "zctl %s\\n" "${FAKE_ZCTL_VERSION:-4.12.0}"\n'
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "ZONECTL_UPDATE_API_ROOT": "https://api.invalid/repos/zonectl",
            "ZONECTL_UPDATE_LOCK_FILE": str(tmp_path / "upgrade.lock"),
            "FAKE_RELEASE_JSON": str(release),
            "FAKE_SUMS": str(sums),
            "FAKE_DEB": str(deb),
            "FAKE_STATE": str(state),
            "FAKE_INSTALLED_VERSION": "4.11.0-1",
        }
    )
    return env, state


def _run(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_check_mode_verifies_without_installing(
    updater_env: tuple[dict[str, str], Path],
) -> None:
    env, state = updater_env
    result = _run(env, "--check")
    assert result.returncode == 0, result.stderr
    assert "Verified stable release v4.12.0; no changes made" in result.stdout
    assert not (state / "apt-get").exists()


def test_successful_upgrade_runs_pre_and_post_checks(
    updater_env: tuple[dict[str, str], Path],
) -> None:
    env, state = updater_env
    result = _run(env)
    assert result.returncode == 0, result.stderr
    assert "Upgrade complete: zctl 4.12.0 (4.12.0-1)" in result.stdout
    assert (state / "named-count").read_text(encoding="ascii").strip() == "2"
    assert "install --yes" in (state / "apt-get").read_text(encoding="utf-8")


@pytest.mark.parametrize("field", ["draft", "prerelease"])
def test_non_stable_release_is_rejected(
    updater_env: tuple[dict[str, str], Path], field: str
) -> None:
    env, _ = updater_env
    release_path = Path(env["FAKE_RELEASE_JSON"])
    data = json.loads(release_path.read_text(encoding="utf-8"))
    data[field] = True
    release_path.write_text(json.dumps(data), encoding="utf-8")
    result = _run(env, "--check")
    assert result.returncode != 0
    assert "release is not stable" in result.stderr


def test_missing_deb_asset_is_rejected(
    updater_env: tuple[dict[str, str], Path],
) -> None:
    env, _ = updater_env
    release_path = Path(env["FAKE_RELEASE_JSON"])
    data = json.loads(release_path.read_text(encoding="utf-8"))
    data["assets"] = data["assets"][:1]
    release_path.write_text(json.dumps(data), encoding="utf-8")
    result = _run(env, "--check")
    assert result.returncode != 0
    assert "missing release assets" in result.stderr


@pytest.mark.parametrize(
    ("variable", "value", "message"),
    [
        ("FAKE_PACKAGE", "other", "unexpected package"),
        ("FAKE_PACKAGE_VERSION", "9.9.9-1", "unexpected package version"),
        ("FAKE_ARCHITECTURE", "amd64", "unexpected package architecture"),
    ],
)
def test_unexpected_deb_metadata_is_rejected(
    updater_env: tuple[dict[str, str], Path],
    variable: str,
    value: str,
    message: str,
) -> None:
    env, state = updater_env
    env[variable] = value
    result = _run(env)
    assert result.returncode != 0
    assert message in result.stderr
    assert not (state / "apt-get").exists()


def test_invalid_checksum_stops_before_install(
    updater_env: tuple[dict[str, str], Path],
) -> None:
    env, state = updater_env
    Path(env["FAKE_SUMS"]).write_text(
        f"{'0' * 64}  zonectl_4.12.0-1_all.deb\n", encoding="ascii"
    )
    result = _run(env)
    assert result.returncode != 0
    assert not (state / "apt-get").exists()


def test_downgrade_is_refused_by_default(
    updater_env: tuple[dict[str, str], Path],
) -> None:
    env, state = updater_env
    env["FAKE_DPKG_GT"] = "1"
    result = _run(env)
    assert result.returncode != 0
    assert "downgrade refused" in result.stderr
    assert not (state / "apt-get").exists()


def test_network_failure_does_not_install(
    updater_env: tuple[dict[str, str], Path],
) -> None:
    env, state = updater_env
    env["FAKE_CURL_FAIL"] = "1"
    assert _run(env).returncode != 0
    assert not (state / "apt-get").exists()


def test_bind_failure_before_installation_is_safe(
    updater_env: tuple[dict[str, str], Path],
) -> None:
    env, state = updater_env
    env["FAKE_NAMED_FAIL_CALL"] = "1"
    result = _run(env)
    assert result.returncode != 0
    assert not (state / "apt-get").exists()
    assert "installation started" not in result.stderr


def test_inactive_bind_stops_before_installation(
    updater_env: tuple[dict[str, str], Path],
) -> None:
    env, state = updater_env
    env["FAKE_BIND_ACTIVE"] = "0"
    result = _run(env)
    assert result.returncode != 0
    assert "bind9 is not active before upgrade" in result.stderr
    assert not (state / "apt-get").exists()


def test_apt_failure_prints_recovery_guidance(
    updater_env: tuple[dict[str, str], Path],
) -> None:
    env, state = updater_env
    env["FAKE_APT_FAIL"] = "1"
    result = _run(env)
    assert result.returncode != 0
    assert (state / "apt-get").exists()
    assert "installation started but final verification failed" in result.stderr


def test_unexpected_zctl_version_prints_recovery_guidance(
    updater_env: tuple[dict[str, str], Path],
) -> None:
    env, state = updater_env
    env["FAKE_ZCTL_VERSION"] = "4.11.0"
    result = _run(env)
    assert result.returncode != 0
    assert (state / "apt-get").exists()
    assert "unexpected zctl version" in result.stderr
    assert "does not automatically downgrade" in result.stderr


def test_failed_post_install_check_prints_recovery_guidance(
    updater_env: tuple[dict[str, str], Path],
) -> None:
    env, state = updater_env
    env["FAKE_NAMED_FAIL_CALL"] = "2"
    result = _run(env)
    assert result.returncode != 0
    assert (state / "apt-get").exists()
    assert "installation started but final verification failed" in result.stderr
    assert "does not automatically downgrade" in result.stderr
    assert "Previous package version was: 4.11.0-1" in result.stderr


def test_lock_contention_is_rejected(updater_env: tuple[dict[str, str], Path]) -> None:
    env, _ = updater_env
    holder = subprocess.Popen(["flock", env["ZONECTL_UPDATE_LOCK_FILE"], "sleep", "10"])
    try:
        result = _run(env, "--check")
    finally:
        holder.terminate()
        holder.wait(timeout=5)
    assert result.returncode != 0
    assert "another ZoneCTL upgrade is already running" in result.stderr
