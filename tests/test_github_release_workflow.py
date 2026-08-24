from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_release_is_manual_and_requires_explicit_inputs() -> None:
    text = workflow_text()

    assert "workflow_dispatch:" in text
    assert "push:" not in text
    assert "pull_request:" not in text
    assert "package_run_id:" in text
    assert "confirmation:" in text
    assert 'expected_confirmation="publish $RELEASE_TAG"' in text


def test_release_matches_tag_version_commit_and_successful_package_run() -> None:
    text = workflow_text()

    assert 'test "$RELEASE_TAG" = "v$version"' in text
    assert 'run_name" = "Package build"' in text
    assert 'run_result" = "success"' in text
    assert 'run_sha" = "$tag_sha"' in text
    assert "sha256sum --check SHA256SUMS" in text
    assert 'dpkg-deb -f "$deb" Version' in text


def test_release_has_write_permission_only_on_publish_job() -> None:
    text = workflow_text()

    assert "permissions:\n  contents: read" in text
    assert "  actions: read" in text
    assert "publish:\n    name:" in text
    assert "    permissions:\n      contents: write" in text
    assert "      actions: read" in text
    assert "gh release create" in text
    assert "--verify-tag" in text
    assert "gh release view" in text


def test_release_uses_verified_artifact_and_node24_checkout() -> None:
    text = workflow_text()

    assert "actions/checkout@v5" in text
    assert "gh run download" in text
    assert "--name zonectl-packages" in text
    assert "/etc/bind" not in text
    assert "rndc" not in text.casefold()
    assert "systemctl" not in text.casefold()
