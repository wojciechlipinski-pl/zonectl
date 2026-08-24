from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "package-build.yml"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_package_build_uses_clean_debian_and_read_only_permissions() -> None:
    text = workflow_text()

    assert "container: debian:trixie-slim" in text
    assert "permissions:\n  contents: read" in text
    assert "/etc/bind/named.conf" not in text
    assert "systemctl" not in text.casefold()
    assert "rndc" not in text.casefold()


def test_package_build_creates_and_validates_both_artifact_formats() -> None:
    text = workflow_text()

    assert "python3 -m build --wheel --no-isolation" in text
    assert "dpkg-buildpackage --build=binary --no-sign" in text
    assert "lintian ../zonectl_*.changes" in text
    assert "dpkg-deb -f" in text
    assert "./usr/bin/zctl$" in text
    assert "./etc/bind/" in text


def test_package_build_checksums_and_uploads_without_publishing() -> None:
    text = workflow_text()

    assert "sha256sum --check SHA256SUMS" in text
    assert "actions/upload-artifact@v4" in text
    assert "retention-days: 14" in text
    assert "actions/create-release" not in text
    assert "gh release" not in text
    assert "twine upload" not in text
