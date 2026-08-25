#!/usr/bin/env python3
"""Report missing docstrings in public Python APIs without importing code."""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class MissingDocstring:
    """One public API object without a docstring."""

    path: str
    line: int
    kind: str
    name: str


def python_files(paths: list[Path]) -> list[Path]:
    """Expand files and directories into a stable Python-file list."""
    files: set[Path] = set()
    for path in paths:
        if path.is_file() and path.suffix == ".py":
            files.add(path)
        elif path.is_dir():
            files.update(path.rglob("*.py"))
    return sorted(files)


def audit_file(path: Path) -> tuple[int, list[MissingDocstring]]:
    """Count public objects and return those lacking docstrings."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    total = 1
    missing: list[MissingDocstring] = []
    if not ast.get_docstring(tree):
        missing.append(MissingDocstring(str(path), 1, "module", path.stem))
    for node in tree.body:
        if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue
        kind = "class" if isinstance(node, ast.ClassDef) else "function"
        total += 1
        if not ast.get_docstring(node):
            missing.append(MissingDocstring(str(path), node.lineno, kind, node.name))
        if isinstance(node, ast.ClassDef):
            for member in node.body:
                if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if member.name.startswith("_"):
                    continue
                total += 1
                if not ast.get_docstring(member):
                    missing.append(
                        MissingDocstring(
                            str(path), member.lineno, "method",
                            f"{node.name}.{member.name}",
                        )
                    )
    return total, missing


def audit(paths: list[Path]) -> tuple[int, list[MissingDocstring]]:
    """Audit all selected paths and aggregate deterministic results."""
    total = 0
    missing: list[MissingDocstring] = []
    for path in python_files(paths):
        file_total, file_missing = audit_file(path)
        total += file_total
        missing.extend(file_missing)
    return total, missing


def parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("paths", nargs="+", type=Path)
    result.add_argument("--strict", action="store_true")
    result.add_argument("--json", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    """Print an inventory and optionally fail when selected APIs lack docs."""
    args = parser().parse_args(argv)
    total, missing = audit(args.paths)
    if args.json:
        print(json.dumps({
            "public_objects": total,
            "missing": [asdict(item) for item in missing],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Publiczne obiekty API: {total}")
        print(f"Brakujące docstringi: {len(missing)}")
        for item in missing:
            print(f"{item.path}:{item.line}: {item.kind} {item.name}")
    return 1 if args.strict and missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
