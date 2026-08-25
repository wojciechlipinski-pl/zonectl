from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "quality-gate.yml"


def test_quality_gate_runs_supported_python_versions_and_bind_tools() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'python-version: ["3.11", "3.13"]' in text
    assert "bind9-utils bind9-dnsutils" in text
    assert "PYTHONPATH: src" in text
    assert "python -m pytest -q" in text


def test_quality_gate_is_read_only_and_has_no_production_bind_commands() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "permissions:\n  contents: read" in text
    assert "/etc/bind" not in text
    assert "rndc" not in text.casefold()
    assert "systemctl" not in text.casefold()
    assert "--commit" not in text


def test_quality_gate_checks_repository_hygiene() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "git diff --check" in text
    assert "Unexpected executable files" in text


def test_quality_gate_type_checks_only_incremental_critical_scope() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert '"mypy>=1.20,<1.21"' in text
    assert "MYPYPATH: src" in text
    assert "python -m mypy" in text
    assert "zone_quarantine_retention.py" in text
    assert "zone_quarantine_purge.py" in text
    assert "zone_create_transaction.py" in text
    assert "zone_disable_transaction.py" in text
    assert "zone_restore_transaction.py" in text
    assert "zone_quarantine.py" in text
    assert "zone_quarantine_restore.py" in text
    assert "discovery.py" in text
    assert "managed_zone_migration.py" in text
    assert "managed_zone_migration_transaction.py" in text
    assert "managed_zone_relocation.py" in text
    assert "managed_zone_relocation_transaction.py" in text
    assert "bind_audit_manifest.py" in text
    assert "bind_secondary_health.py" in text
    assert "bind_access_impact.py" in text
    assert "bind_config.py" in text
    assert "bind_secondary_plan.py" in text
    assert "bind_zone_secondary.py" in text
    assert "bind_acl_transaction.py" in text
    assert "bind_secondary_transaction.py" in text
    assert "zone_inventory.py" in text
    assert "edit_lock.py" in text
    assert "audit.py" in text
    assert "zone_document_adapter.py" in text
    assert "zone_writer.py" in text
    assert "zone_serializer.py" in text
    assert "transaction.py" in text
    assert "zone_edit_session.py" in text
    assert "rpz_managed_install.py" in text
    assert "rpz_external_migration_transaction.py" in text
    assert "scripts/audit_public_api.py" in text
