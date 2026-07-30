#!/usr/bin/env python3
"""Bezpieczna migracja katalogów systemowych do przestrzeni ZoneCTL."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


MIGRATION_ID = "001-system-paths"
MANIFEST_ROOT = Path("/var/backups/zonectl-migrations")

PATH_PAIRS = (
    (
        Path("/etc/elkman-dns-toolkit"),
        Path("/etc/zonectl"),
    ),
    (
        Path("/var/lib/elkman-dns-toolkit"),
        Path("/var/lib/zonectl"),
    ),
    (
        Path("/var/log/elkman-dns-toolkit"),
        Path("/var/log/zonectl"),
    ),
    (
        Path("/var/backups/elkman-dns"),
        Path("/var/backups/zonectl"),
    ),
)

PATH_REPLACEMENTS = (
    ("/etc/elkman-dns-toolkit", "/etc/zonectl"),
    ("/var/lib/elkman-dns-toolkit", "/var/lib/zonectl"),
    ("/var/log/elkman-dns-toolkit", "/var/log/zonectl"),
    ("/var/backups/elkman-dns", "/var/backups/zonectl"),
)


@dataclass(frozen=True, slots=True)
class PathPlan:
    source: Path
    target: Path
    source_exists: bool
    target_exists: bool


def migration_plan(
    pairs: tuple[tuple[Path, Path], ...] = PATH_PAIRS,
) -> list[PathPlan]:
    return [
        PathPlan(
            source=source,
            target=target,
            source_exists=source.exists(),
            target_exists=target.exists(),
        )
        for source, target in pairs
    ]


def rewrite_legacy_paths(text: str) -> str:
    for old, new in PATH_REPLACEMENTS:
        text = text.replace(old, new)
    return text


def print_plan(plan: list[PathPlan]) -> None:
    print(f"Migracja: {MIGRATION_ID}")
    print("Tryb: plan — bez zmian w systemie")
    print()

    for item in plan:
        source_state = "istnieje" if item.source_exists else "brak"
        target_state = "istnieje" if item.target_exists else "wolny"
        print(
            f"{item.source} -> {item.target} "
            f"[źródło: {source_state}; cel: {target_state}]"
        )


def require_root() -> None:
    if os.geteuid() != 0:
        raise RuntimeError(
            "Tryb apply i rollback musi być uruchomiony jako root."
        )


def require_safe_apply(plan: list[PathPlan]) -> None:
    conflicts = [
        item.target
        for item in plan
        if item.target_exists
    ]

    if conflicts:
        rendered = ", ".join(str(path) for path in conflicts)
        raise RuntimeError(
            "Katalogi docelowe już istnieją; migracja nie będzie ich "
            f"nadpisywać: {rendered}"
        )


def copy_archive(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["cp", "-a", "--", str(source), str(target)],
        check=True,
    )


def backup_source(source: Path, backup_root: Path) -> Path:
    relative = source.relative_to("/")
    target = backup_root / "sources" / relative
    copy_archive(source, target)
    return target


def rewrite_target_config(config_dir: Path) -> list[str]:
    changed: list[str] = []

    for name in ("toolkit.conf", "zones.conf"):
        path = config_dir / name

        if not path.is_file():
            continue

        original = path.read_text(encoding="utf-8")
        rewritten = rewrite_legacy_paths(original)

        if rewritten == original:
            continue

        temporary = path.with_name(f".{path.name}.zonectl-new")
        temporary.write_text(rewritten, encoding="utf-8")
        shutil.copymode(path, temporary)
        os.chown(
            temporary,
            path.stat().st_uid,
            path.stat().st_gid,
        )
        temporary.replace(path)
        changed.append(str(path))

    return changed


def apply_migration() -> Path:
    require_root()
    plan = migration_plan()
    require_safe_apply(plan)

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    backup_root = MANIFEST_ROOT / f"{MIGRATION_ID}-{timestamp}"
    backup_root.mkdir(parents=True, mode=0o700)

    manifest_path = backup_root / "manifest.json"
    manifest: dict[str, object] = {
        "migration": MIGRATION_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "applying",
        "created_targets": [],
        "backups": [],
        "rewritten_files": [],
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    created_targets: list[Path] = []

    try:
        for item in plan:
            if not item.source_exists:
                continue

            backup = backup_source(item.source, backup_root)
            manifest["backups"].append(str(backup))

            copy_archive(item.source, item.target)
            created_targets.append(item.target)
            manifest["created_targets"].append(str(item.target))

            manifest_path.write_text(
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

        rewritten = rewrite_target_config(Path("/etc/zonectl"))
        manifest["rewritten_files"] = rewritten
        manifest["status"] = "applied"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        for target in reversed(created_targets):
            if target in {item.target for item in plan}:
                shutil.rmtree(target)

        manifest["status"] = "apply-failed-cleaned"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        raise

    return manifest_path


def rollback_migration(manifest_path: Path) -> None:
    require_root()
    manifest_path = manifest_path.resolve()
    manifest_root = MANIFEST_ROOT.resolve()

    if manifest_root not in manifest_path.parents:
        raise RuntimeError(
            f"Manifest musi znajdować się w {MANIFEST_ROOT}"
        )

    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    if manifest.get("migration") != MIGRATION_ID:
        raise RuntimeError("Manifest dotyczy innej migracji.")

    if manifest.get("status") != "applied":
        raise RuntimeError(
            "Rollback wymaga manifestu ze statusem applied."
        )

    allowed_targets = {
        target.resolve()
        for _, target in PATH_PAIRS
    }

    for raw in reversed(manifest.get("created_targets", [])):
        target = Path(raw).resolve()

        if target not in allowed_targets:
            raise RuntimeError(
                f"Manifest zawiera niedozwolony cel: {target}"
            )

        if target.exists():
            shutil.rmtree(target)

    manifest["status"] = "rolled-back"
    manifest["rolled_back_at"] = datetime.now(
        timezone.utc
    ).isoformat()
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="m001-system-paths",
        description=__doc__,
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--apply",
        action="store_true",
        help="utwórz backup i skopiuj dane do nowych katalogów",
    )
    action.add_argument(
        "--rollback",
        type=Path,
        metavar="MANIFEST",
        help="usuń cele utworzone przez wskazaną migrację",
    )
    args = parser.parse_args()

    try:
        if args.rollback:
            rollback_migration(args.rollback)
            print("Rollback zakończony.")
            return 0

        if args.apply:
            manifest = apply_migration()
            print("Migracja zakończona.")
            print(f"Manifest: {manifest}")
            return 0

        print_plan(migration_plan())
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"BŁĄD: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
