from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from zonectl import cli
from zonectl.core.bind_capabilities import BindCapabilities
from zonectl.core.dnssec_enable_transaction import DnssecEnableStep
from zonectl.core.discovery import ZoneConfig
from zonectl.core.dnssec_policy_migration import DnssecPolicyMigrationWorkflow
from zonectl.core.dnssec_policy_migration_state import MigrationPhase
from zonectl.core.models import Zone

from tests.test_dnssec_policy_migration import SOURCE_DS, TARGET_DS, make_plan, workflow


class MigrationCliConfig:
    toolkit = {"local_server": "mock-local", "dig_timeout": "1"}

    def __init__(self, plan):
        self.plan = plan
        self.zone = Zone(plan.zone, plan.declaration_file)
        self.discovered = ZoneConfig(
            plan.zone,
            "primary",
            plan.declaration_file.parent / "alpha.db",
            plan.declaration_file,
            dnssec_policy="new",
            inline_signing=True,
            source_exists=True,
            source_writable=True,
        )

    def zones(self):
        return [self.zone]

    def discovered_zone(self, name: str):
        if name.rstrip(".").casefold() == self.plan.zone.rstrip(".").casefold():
            return self.discovered
        return None


def _paths(plan, tmp_path: Path) -> list[str]:
    return [
        "--state-directory",
        str(tmp_path / "state"),
        "--backup-root",
        str(tmp_path / "backups"),
        "--root-config",
        str(plan.declaration_file),
        "--json",
    ]


def _mock_cli_io(monkeypatch, config: MigrationCliConfig, observations) -> None:
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: config)
    monkeypatch.setattr(
        cli.DnssecReporter,
        "collect",
        lambda self, zone: SimpleNamespace(
            loaded=True,
            dnskey_records=("privacy-safe-presence-only",),
            rrsig_records=("privacy-safe-presence-only",),
            calculated_ds=(SOURCE_DS, TARGET_DS),
        ),
    )
    monkeypatch.setattr(
        cli.DnssecDsChecker,
        "collect",
        lambda self, zone, resolvers: SimpleNamespace(
            expected_ds=(SOURCE_DS, TARGET_DS),
            resolver_checks=tuple(
                SimpleNamespace(status=status, records=records)
                for status, records in observations()
            ),
            authority_checks=(SimpleNamespace(status="MATCH"),),
        ),
    )


def test_cli_source_ds_match_cannot_advance_but_target_identity_can_after_restart(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    plan, _ = make_plan(tmp_path)
    first = workflow(tmp_path)
    started = first.start(plan, commit=True, activate=True, confirmation=plan.zone)
    state = first.store.load(plan.zone)
    state.transition(MigrationPhase.WAITING_DS, "wait for target DS")
    first.store.save(state)
    assert started.status == "POLICY_APPLIED"

    current = [("MATCH", (SOURCE_DS,)), ("MATCH", (SOURCE_DS,))]
    config = MigrationCliConfig(plan)
    _mock_cli_io(monkeypatch, config, lambda: current)
    arguments = _paths(plan, tmp_path)

    assert cli.main(["dnssec", "migration-status", plan.zone, *arguments]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["phase"] == "WAITING_DS"

    assert cli.main(["dnssec", "migration-resume", plan.zone, *arguments]) == 0
    source_only = json.loads(capsys.readouterr().out)
    assert source_only["status"] == "WAITING"
    assert source_only["phase"] == "WAITING_DS"

    current[:] = [("MATCH", (TARGET_DS,)), ("MATCH", (TARGET_DS,))]
    assert cli.main(["dnssec", "migration-resume", plan.zone, *arguments]) == 0
    target = json.loads(capsys.readouterr().out)
    assert target["status"] == "ADVANCED"
    assert target["phase"] == "WAITING_PROPAGATION"


def test_cli_committed_start_rejects_missing_source_ksk_identity(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    plan, declaration = make_plan(tmp_path)
    before = declaration.read_bytes()
    config = MigrationCliConfig(plan)
    monkeypatch.setattr(cli.ToolkitConfig, "load", lambda self: config)
    monkeypatch.setattr(
        cli.BindCapabilityDetector,
        "detect",
        lambda self: BindCapabilities(
            True, "9.20.0", "9.20", "PASS", True, True, True, ()
        ),
    )
    monkeypatch.setattr(cli.DnssecPolicyInventoryReader, "read", lambda self: object())
    monkeypatch.setattr(
        cli.DnssecPolicyMigrationPlanner, "plan", lambda self, *a, **k: plan
    )
    monkeypatch.setattr(
        cli.DnssecReporter,
        "collect",
        lambda self, zone: SimpleNamespace(calculated_ds=()),
    )
    monkeypatch.setattr(
        DnssecPolicyMigrationWorkflow,
        "_validate_config",
        staticmethod(lambda root: DnssecEnableStep("checkconf", True, "mock")),
    )

    code = cli.main(
        [
            "dnssec",
            "migration-start",
            plan.zone,
            "--source-policy",
            "old",
            "--target-policy",
            "new",
            "--commit",
            "--activate",
            "--confirm",
            plan.zone,
            *_paths(plan, tmp_path),
        ]
    )

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "REJECTED"
    assert payload["steps"][0]["name"] == "source-key-identity"
    assert declaration.read_bytes() == before
    assert not (tmp_path / "state" / f"{plan.zone}.json").exists()
