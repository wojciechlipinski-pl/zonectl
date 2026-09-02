from __future__ import annotations

import subprocess
import stat
from pathlib import Path

import pytest

from zonectl import cli
from zonectl.core.config import ToolkitConfig
from zonectl.core.git_history import GitHistoryError, LocalGitHistory
from zonectl.core.models import Zone


def test_git_history_config_is_disabled_by_default(tmp_path: Path) -> None:
    config_path = tmp_path / "toolkit.conf"
    config_path.write_text("[toolkit]\nauto_discover_zones = no\n", encoding="utf-8")
    config = ToolkitConfig(
        config_path, tmp_path / "zones.conf", tmp_path / "groups.yaml"
    ).load()
    assert config.git_history_enabled is False
    assert str(config.git_history_directory).endswith("git-history")


def test_git_history_config_accepts_explicit_private_path(tmp_path: Path) -> None:
    repository = tmp_path / "private-history"
    config_path = tmp_path / "toolkit.conf"
    config_path.write_text(
        "[toolkit]\nauto_discover_zones = no\n"
        f"git_history_enabled = yes\ngit_history_directory = {repository}\n",
        encoding="utf-8",
    )
    config = ToolkitConfig(
        config_path, tmp_path / "zones.conf", tmp_path / "groups.yaml"
    ).load()
    assert config.git_history_enabled is True
    assert config.git_history_directory == repository


def test_history_requires_explicit_commit_and_creates_local_commit(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "history"
    source = tmp_path / "alpha.db"
    source.write_text("$TTL 3600\n@ IN A 192.0.2.10\n", encoding="utf-8")
    history = LocalGitHistory(repository)

    assert history.initialize() is True
    assert not repository.exists()
    assert history.initialize(commit=True) is True

    plan = history.snapshot(
        "alpha.example.test", source, profile="authoritative", commit=False
    )
    assert plan.changed is True
    assert plan.dry_run is True
    assert history.log() == ()

    result = history.snapshot(
        "alpha.example.test", source, profile="authoritative", commit=True
    )
    assert result.changed is True
    assert result.commit is not None
    assert history.status() == ()
    assert "zone: snapshot alpha.example.test" in history.log()[0]
    assert stat.S_IMODE(repository.stat().st_mode) == 0o750
    target = repository / "zones" / "alpha.example.test" / "zone.db"
    assert stat.S_IMODE(target.stat().st_mode) == 0o640

    unchanged = history.snapshot(
        "alpha.example.test", source, profile="authoritative", commit=True
    )
    assert unchanged.changed is False
    assert unchanged.commit is None


def test_history_excludes_rpz_and_rejects_remote(tmp_path: Path) -> None:
    repository = tmp_path / "history"
    source = tmp_path / "zone.db"
    source.write_text("synthetic\n", encoding="utf-8")
    history = LocalGitHistory(repository)
    history.initialize(commit=True)

    with pytest.raises(GitHistoryError, match="RPZ"):
        history.snapshot("rpz.example.test", source, profile="RPZ", commit=True)

    subprocess.run(
        ["git", "remote", "add", "origin", "https://example.invalid/private.git"],
        cwd=repository,
        check=True,
    )
    with pytest.raises(GitHistoryError, match="remote"):
        history.status()


def test_history_rejects_symlink_sources_and_destinations(tmp_path: Path) -> None:
    repository = tmp_path / "history"
    source = tmp_path / "zone.db"
    source.write_text("synthetic\n", encoding="utf-8")
    source_link = tmp_path / "zone-link.db"
    source_link.symlink_to(source)
    history = LocalGitHistory(repository)
    history.initialize(commit=True)

    with pytest.raises(GitHistoryError, match="zwykłym plikiem"):
        history.snapshot(
            "alpha.example.test", source_link, profile="authoritative", commit=True
        )

    outside = tmp_path / "outside"
    outside.mkdir()
    (repository / "zones").symlink_to(outside, target_is_directory=True)
    with pytest.raises(GitHistoryError, match="symlinkiem"):
        history.snapshot(
            "alpha.example.test", source, profile="authoritative", commit=True
        )


def test_history_rejects_overly_broad_repository_permissions(tmp_path: Path) -> None:
    repository = tmp_path / "history"
    history = LocalGitHistory(repository)
    history.initialize(commit=True)
    repository.chmod(0o755)

    with pytest.raises(GitHistoryError, match="uprawnienia"):
        history.status()


class _Config:
    def __init__(self, tmp_path: Path, *, enabled: bool = True) -> None:
        self.git_history_enabled = enabled
        self.git_history_directory = tmp_path / "history"
        self._zone_file = tmp_path / "alpha.db"
        self._zone_file.write_text("synthetic\n", encoding="utf-8")

    def zones(self) -> list[Zone]:
        return [Zone("alpha.example.test", self._zone_file)]


def test_cli_is_opt_in_and_requires_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    disabled = _Config(tmp_path, enabled=False)
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: disabled)
    assert cli.main(["git-history", "init"]) == 2
    assert "wyłączona" in capsys.readouterr().err

    enabled = _Config(tmp_path)
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: enabled)
    assert cli.main(["git-history", "init", "--commit"]) == 2
    assert "INITIALIZE" in capsys.readouterr().err
    assert cli.main(["git-history", "init", "--commit", "--confirm", "INITIALIZE"]) == 0
    assert cli.main(["git-history", "snapshot", "alpha.example.test"]) == 0
    assert "PLAN" in capsys.readouterr().out
    assert (
        cli.main(
            [
                "git-history",
                "snapshot",
                "alpha.example.test",
                "--commit",
                "--confirm",
                "alpha.example.test",
            ]
        )
        == 0
    )
    assert "COMMITTED" in capsys.readouterr().out
