from pathlib import Path
import tomllib

import zonectl


ROOT = Path(__file__).resolve().parents[1]


def test_release_version_is_consistent_across_public_artifacts() -> None:
    metadata = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    version = metadata["project"]["version"]

    assert version == "4.10.1"
    assert zonectl.__version__ == version
    assert (ROOT / "debian/changelog").read_text(encoding="utf-8").startswith(
        f"zonectl ({version}-1) "
    )
    assert f"## {version} - 2026-08-31" in (
        ROOT / "CHANGELOG.md"
    ).read_text(encoding="utf-8")
    assert f"**{version} —" in (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"**{version} —" in (ROOT / "README.pl.md").read_text(
        encoding="utf-8"
    )
    assert f'"ZoneCTL {version}"' in (
        ROOT / "debian/zctl.1"
    ).read_text(encoding="utf-8")
