from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts/audit_public_api.py"
SPEC = importlib.util.spec_from_file_location("audit_public_api", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_audit_reports_public_objects_without_importing_target(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text(
        '"""module docs"""\n'
        "class Public:\n"
        '    """class docs"""\n'
        "    def documented(self):\n"
        '        """method docs"""\n'
        "    def missing(self):\n"
        "        pass\n"
        "def missing_function():\n"
        "    pass\n"
        "def _private():\n"
        "    pass\n",
        encoding="utf-8",
    )
    total, missing = MODULE.audit([target])
    assert total == 5
    assert [item.name for item in missing] == ["Public.missing", "missing_function"]


def test_strict_mode_fails_only_for_missing_docs(tmp_path: Path, capsys) -> None:
    target = tmp_path / "clean.py"
    target.write_text(
        '"""module"""\n\ndef public():\n    """documented"""\n',
        encoding="utf-8",
    )
    assert MODULE.main(["--strict", str(target)]) == 0
    assert "Brakujące docstringi: 0" in capsys.readouterr().out


def test_current_critical_modules_are_fully_documented() -> None:
    root = Path(__file__).parents[1]
    paths = [
        root / "src/zonectl/core/zone_quarantine_retention.py",
        root / "src/zonectl/core/zone_quarantine_purge.py",
        root / "src/zonectl/core/zone_create_transaction.py",
        root / "src/zonectl/core/zone_disable_transaction.py",
        root / "src/zonectl/core/zone_restore_transaction.py",
        root / "src/zonectl/core/zone_quarantine.py",
        root / "src/zonectl/core/zone_quarantine_restore.py",
        root / "src/zonectl/core/managed_zone_migration_transaction.py",
        root / "src/zonectl/core/managed_zone_relocation_transaction.py",
        root / "src/zonectl/core/audit_store.py",
        root / "src/zonectl/core/transaction_audit_adapter.py",
    ]
    total, missing = MODULE.audit(paths)
    assert total > 0
    assert missing == []
