#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = Path(__file__).resolve().parent
STATE = ROOT / ".zonectl-migrations.json"


def discover() -> list[Path]:
    return sorted(MIGRATIONS.glob("m[0-9][0-9][0-9]_*.py"))


def load_state() -> dict:
    if not STATE.exists():
        return {"applied": []}
    return json.loads(STATE.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(prog="zonectl-migrate")
    parser.add_argument("command", choices=("list", "status", "test"))
    args = parser.parse_args()

    if args.command == "list":
        applied = set(load_state().get("applied", []))
        for path in discover():
            migration_id = path.stem.split("_", 1)[0][1:]
            marker = "x" if migration_id in applied else " "
            print(f"[{marker}] {migration_id}  {path.name}")
        return 0

    if args.command == "status":
        print(json.dumps({
            "root": str(ROOT),
            "state_file": str(STATE),
            "available": [p.name for p in discover()],
            "applied": load_state().get("applied", []),
        }, ensure_ascii=False, indent=2))
        return 0

    pytest = ROOT / ".venv" / "bin" / "pytest"
    command = [str(pytest if pytest.exists() else "pytest"), "-q"]
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
