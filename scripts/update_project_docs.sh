#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
[[ -x "$ROOT/.venv/bin/python" ]] && PYTHON="$ROOT/.venv/bin/python"
exec "$PYTHON" "$ROOT/scripts/update_project_docs.py" "$@"
