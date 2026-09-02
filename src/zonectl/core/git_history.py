"""Optional local Git history for managed zone files.

The repository is deliberately local-only and supplements transaction backups.
It never reads DNSSEC key directories and rejects automatically managed RPZ
zones.  Callers must provide a zone file already selected by ``ToolkitConfig``.
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


_ZONE_RE = re.compile(
    r"(?i)(?:[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?\.)*[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?"
)
MAX_ZONE_BYTES = 64 * 1024 * 1024


class GitHistoryError(RuntimeError):
    """Raised when the optional history cannot operate safely."""


@dataclass(frozen=True, slots=True)
class GitSnapshot:
    """Describe the result of a local zone snapshot."""

    zone: str
    commit: str | None
    changed: bool
    dry_run: bool


class LocalGitHistory:
    """Maintain a private, remote-free Git repository of zone snapshots."""

    def __init__(self, repository: Path, *, git_binary: str = "git") -> None:
        self.repository = repository
        self.git_binary = git_binary

    def _git(
        self, *arguments: str, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        command = [
            self.git_binary,
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "user.name=ZoneCTL",
            "-c",
            "user.email=zonectl@localhost.invalid",
            *arguments,
        ]
        try:
            return subprocess.run(
                command,
                cwd=self.repository,
                check=check,
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise GitHistoryError("lokalne polecenie Git nie powiodło się") from exc

    @staticmethod
    def _zone_name(zone: str) -> str:
        value = zone.rstrip(".").casefold()
        if not value or len(value) > 253 or _ZONE_RE.fullmatch(value) is None:
            raise GitHistoryError("nieprawidłowa nazwa strefy")
        return value

    def _assert_private_repository(self) -> None:
        if self.repository.is_symlink():
            raise GitHistoryError("katalog historii Git nie może być symlinkiem")
        if stat.S_IMODE(self.repository.stat().st_mode) & 0o027:
            raise GitHistoryError("katalog historii Git ma zbyt szerokie uprawnienia")
        git_directory = self.repository / ".git"
        if git_directory.is_symlink() or not git_directory.is_dir():
            raise GitHistoryError("historia Git nie została zainicjalizowana")
        remotes = self._git("remote").stdout.strip()
        if remotes:
            raise GitHistoryError("lokalna historia Git nie może mieć remote")

    def initialize(self, *, commit: bool = False) -> bool:
        """Plan or create a private repository without any remote."""
        if self.repository.exists():
            if self.repository.is_symlink() or not self.repository.is_dir():
                raise GitHistoryError("niebezpieczna ścieżka historii Git")
            if any(self.repository.iterdir()):
                self._assert_private_repository()
                return False
        if not commit:
            return True
        self.repository.mkdir(parents=True, mode=0o750, exist_ok=True)
        os.chmod(self.repository, 0o750)
        try:
            subprocess.run(
                [
                    self.git_binary,
                    "init",
                    "--quiet",
                    "--initial-branch=main",
                    str(self.repository),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise GitHistoryError(
                "nie udało się zainicjalizować lokalnego Git"
            ) from exc
        self._assert_private_repository()
        return True

    def snapshot(
        self,
        zone: str,
        source: Path,
        *,
        profile: str,
        commit: bool = False,
    ) -> GitSnapshot:
        """Plan or commit one managed zone file to the private repository."""
        name = self._zone_name(zone)
        if profile.casefold() == "rpz":
            raise GitHistoryError(
                "automatycznie aktualizowane strefy RPZ są wykluczone"
            )
        self._assert_private_repository()
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(source, flags)
        except OSError as exc:
            raise GitHistoryError("źródło musi być zwykłym plikiem strefy") from exc
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_ZONE_BYTES:
                raise GitHistoryError("nieprawidłowy rozmiar lub typ pliku strefy")
            with os.fdopen(descriptor, "rb", closefd=False) as handle:
                candidate = handle.read(MAX_ZONE_BYTES + 1)
        finally:
            os.close(descriptor)
        target = self.repository / "zones" / name / "zone.db"
        for directory in (target.parent.parent, target.parent):
            if directory.is_symlink():
                raise GitHistoryError("katalog docelowy nie może być symlinkiem")
        if target.is_symlink():
            raise GitHistoryError("plik docelowy nie może być symlinkiem")
        current = target.read_bytes() if target.is_file() else None
        changed = current != candidate
        if not commit or not changed:
            return GitSnapshot(name, None, changed, not commit)

        target.parent.mkdir(parents=True, mode=0o750, exist_ok=True)
        os.chmod(target.parent, 0o750)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".zone.db.", dir=target.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(candidate)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o640)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        self._git("add", "--", str(target.relative_to(self.repository)))
        self._git("commit", "--quiet", "-m", f"zone: snapshot {name}")
        revision = self._git("rev-parse", "HEAD").stdout.strip()
        return GitSnapshot(name, revision, True, False)

    def status(self) -> tuple[str, ...]:
        """Return bounded porcelain status lines from the private repository."""
        self._assert_private_repository()
        lines = self._git(
            "status", "--short", "--untracked-files=all"
        ).stdout.splitlines()
        return tuple(lines[:200])

    def log(self, *, limit: int = 20) -> tuple[str, ...]:
        """Return a bounded, single-line local history."""
        if not 1 <= limit <= 200:
            raise GitHistoryError("limit historii musi mieścić się w zakresie 1..200")
        self._assert_private_repository()
        result = self._git(
            "log", f"--max-count={limit}", "--format=%H%x09%aI%x09%s", check=False
        )
        if result.returncode not in {0, 128}:
            raise GitHistoryError("nie udało się odczytać lokalnej historii Git")
        return tuple(result.stdout.splitlines())
