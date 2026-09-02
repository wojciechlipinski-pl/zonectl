from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install-latest-release.sh"


def script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_updater_uses_stable_github_release_and_expected_assets() -> None:
    text = script_text()

    assert "/releases/latest" in text
    assert 'release.get("draft") or release.get("prerelease")' in text
    assert "SHA256SUMS" in text
    assert 'f"zonectl_{version}-1_all.deb"' in text


def test_updater_verifies_package_before_installing() -> None:
    text = script_text()

    checksum = text.index("sha256sum --check")
    metadata = text.index('dpkg-deb -f "$DEB_PATH" Package')
    install = text.index("apt-get install --yes")
    assert checksum < metadata < install
    assert '[ "$PACKAGE" = "zonectl" ]' in text
    assert '[ "$ARCHITECTURE" = "all" ]' in text


def test_updater_has_production_guards_and_post_install_checks() -> None:
    text = script_text()

    assert 'flock -n 9' in text
    assert "--allow-downgrade" in text
    assert "named-checkconf" in text
    assert 'systemctl is-active --quiet bind9' in text
    assert 'ACTUAL_VERSION="$(zctl --version)"' in text
    assert "DEBIAN_FRONTEND=noninteractive" in text


def test_updater_supports_check_only_mode() -> None:
    text = script_text()

    assert "--check" in text
    assert 'if [ "$CHECK_ONLY" -eq 1 ]' in text
    assert "no changes made" in text
