from __future__ import annotations

import json
from pathlib import Path

from zonectl import cli
from zonectl.core.zone_create_transaction import (
    ZoneCreateResult,
    ZoneCreateStep,
)
from zonectl.core.zone_disable_transaction import (
    ZoneDisableResult,
    ZoneDisableStep,
)
from zonectl.core.zone_restore_transaction import (
    ZoneRestoreResult,
    ZoneRestoreStep,
)
from zonectl.core.zone_quarantine import (
    ZoneQuarantineResult,
    ZoneQuarantineStep,
)
from zonectl.core.zone_quarantine_restore import (
    QuarantineRestoreResult,
    QuarantineRestoreStep,
)


class FakeConfig:
    def zones(self):
        return []


class FakeRpzConfig:
    def zones(self):
        from zonectl.core.models import Zone

        return [
            Zone(
                name="cert-rpz.local",
                file=Path("/etc/bind/domains_rpz.db"),
                health_profile="rpz",
            )
        ]


def test_rpz_disable_is_rejected_before_planning(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(
        cli.ToolkitConfig, "load", lambda self: FakeRpzConfig()
    )

    code = cli.main(
        [
            "zone",
            "disable",
            "cert-rpz.local",
            "--reason",
            "nie wolno",
            "--commit",
        ]
    )

    assert code == 2
    assert "strefy RPZ" in capsys.readouterr().err


def test_create_plan_cli_outputs_json(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        cli.ToolkitConfig,
        "load",
        lambda self: FakeConfig(),
    )

    code = cli.main(
        [
            "zone",
            "create-plan",
            "example.pl",
            "--primary-ns",
            "ns1.elkman.pl.",
            "--admin",
            "hostmaster.elkman.pl.",
            "--ns",
            "ns1.elkman.pl.",
            "--json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["zone_name"] == "example.pl"
    assert payload["zone_file"].endswith("/example.pl")


def test_create_plan_cli_reports_validation_error(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        cli.ToolkitConfig,
        "load",
        lambda self: FakeConfig(),
    )

    code = cli.main(
        [
            "zone",
            "create-plan",
            "bad_name.pl",
            "--primary-ns",
            "ns1.elkman.pl.",
            "--admin",
            "hostmaster.elkman.pl.",
            "--ns",
            "ns1.elkman.pl.",
        ]
    )

    assert code == 2
    assert "BŁĄD:" in capsys.readouterr().err


def test_create_cli_defaults_to_dry_run(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        cli.ToolkitConfig,
        "load",
        lambda self: FakeConfig(),
    )
    calls = []

    def apply(self, plan, *, commit=False, activate=False):
        calls.append((commit, activate, plan.zone_name))
        return ZoneCreateResult(
            "tx-1",
            plan.zone_name,
            "DRY-RUN",
            steps=[ZoneCreateStep("dry-run", True, "bez zmian")],
        )

    monkeypatch.setattr(cli.ZoneCreateTransaction, "apply", apply)
    code = cli.main(
        [
            "zone",
            "create",
            "example.pl",
            "--primary-ns",
            "ns1.elkman.pl.",
            "--admin",
            "hostmaster.elkman.pl.",
            "--ns",
            "ns1.elkman.pl.",
            "--zone-directory",
            str(tmp_path / "zones"),
            "--managed-config",
            str(tmp_path / "zones.conf"),
            "--managed-zone-directory",
            str(tmp_path / "zones.d"),
        ]
    )
    assert code == 0
    assert calls == [(False, False, "example.pl")]
    assert "Status:     DRY-RUN" in capsys.readouterr().out


def test_create_cli_commit_requests_activation(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        cli.ToolkitConfig,
        "load",
        lambda self: FakeConfig(),
    )
    calls = []

    def apply(self, plan, *, commit=False, activate=False):
        calls.append((commit, activate))
        return ZoneCreateResult(
            "tx-2",
            plan.zone_name,
            "COMMIT",
            committed=True,
            steps=[ZoneCreateStep("rndc-zonestatus", True, "loaded")],
        )

    monkeypatch.setattr(cli.ZoneCreateTransaction, "apply", apply)
    code = cli.main(
        [
            "zone",
            "create",
            "example.pl",
            "--primary-ns",
            "ns1.elkman.pl.",
            "--admin",
            "hostmaster.elkman.pl.",
            "--ns",
            "ns1.elkman.pl.",
            "--commit",
        ]
    )
    assert code == 0
    assert calls == [(True, True)]
    assert "Status:     COMMIT" in capsys.readouterr().out


def test_disable_cli_defaults_to_dry_run(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        cli.ToolkitConfig, "load", lambda self: FakeConfig()
    )
    zone = tmp_path / "zones/example.invalid"
    declaration = tmp_path / "bind/zones.d/example.invalid.conf"
    index = tmp_path / "bind/zones.conf"
    zone.parent.mkdir(parents=True)
    declaration.parent.mkdir(parents=True)
    zone.write_text("data\n")
    declaration.write_text("zone declaration\n")
    index.write_text(f'include "{declaration}";\n')
    calls = []

    def apply(self, plan, *, commit=False):
        calls.append((commit, plan.zone_name, plan.reason))
        return ZoneDisableResult(
            "tx-disable",
            plan.zone_name,
            "DRY-RUN",
            plan.reason,
            steps=[ZoneDisableStep("dry-run", True, "bez zmian")],
        )

    monkeypatch.setattr(cli.ZoneDisableTransaction, "apply", apply)
    code = cli.main(
        [
            "zone",
            "disable",
            "example.invalid",
            "--reason",
            "test CLI",
            "--zone-directory",
            str(zone.parent),
            "--managed-config",
            str(index),
            "--managed-zone-directory",
            str(declaration.parent),
            "--disabled-root",
            str(tmp_path / "disabled"),
        ]
    )
    assert code == 0
    assert calls == [(False, "example.invalid", "test CLI")]
    assert "Status:     DRY-RUN" in capsys.readouterr().out


def test_restore_cli_defaults_to_dry_run(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        cli.ToolkitConfig, "load", lambda self: FakeConfig()
    )
    zone = tmp_path / "zones/example.invalid"
    declaration = tmp_path / "bind/zones.d/example.invalid.conf"
    archived = tmp_path / "disabled/example.invalid/example.invalid.conf"
    index = tmp_path / "bind/zones.conf"
    zone.parent.mkdir(parents=True)
    declaration.parent.mkdir(parents=True)
    archived.parent.mkdir(parents=True)
    zone.write_text("data\n")
    archived.write_text("zone declaration\n")
    index.write_text("# empty\n")
    calls = []

    def apply(self, plan, *, commit=False):
        calls.append((commit, plan.zone_name))
        return ZoneRestoreResult(
            "tx-restore",
            plan.zone_name,
            "DRY-RUN",
            steps=[ZoneRestoreStep("dry-run", True, "bez zmian")],
        )

    monkeypatch.setattr(cli.ZoneRestoreTransaction, "apply", apply)
    code = cli.main(
        [
            "zone",
            "restore",
            "example.invalid",
            "--zone-directory",
            str(zone.parent),
            "--managed-config",
            str(index),
            "--managed-zone-directory",
            str(declaration.parent),
            "--disabled-root",
            str(tmp_path / "disabled"),
        ]
    )
    assert code == 0
    assert calls == [(False, "example.invalid")]
    assert "Status:     DRY-RUN" in capsys.readouterr().out


def test_quarantine_cli_passes_commit_and_confirmation(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        cli.ToolkitConfig, "load", lambda self: FakeConfig()
    )
    zone = tmp_path / "zones/example.invalid"
    active = tmp_path / "bind/zones.d/example.invalid.conf"
    archived = tmp_path / "disabled/example.invalid/example.invalid.conf"
    index = tmp_path / "bind/zones.conf"
    zone.parent.mkdir(parents=True)
    active.parent.mkdir(parents=True)
    archived.parent.mkdir(parents=True)
    zone.write_text("data\n")
    archived.write_text("declaration\n")
    index.write_text("# empty\n")
    calls = []

    def apply(self, plan, *, commit=False, confirmation=None):
        calls.append((commit, confirmation, plan.reason))
        return ZoneQuarantineResult(
            "tx-quarantine",
            plan.zone_name,
            "QUARANTINED",
            plan.reason,
            package_directory=str(tmp_path / "package"),
            committed=True,
            steps=[ZoneQuarantineStep("package", True, "OK")],
        )

    monkeypatch.setattr(cli.ZoneQuarantineTransaction, "apply", apply)
    code = cli.main(
        [
            "zone",
            "quarantine",
            "example.invalid",
            "--reason",
            "retired",
            "--confirm",
            "example.invalid",
            "--commit",
            "--zone-directory",
            str(zone.parent),
            "--managed-config",
            str(index),
            "--managed-zone-directory",
            str(active.parent),
            "--disabled-root",
            str(tmp_path / "disabled"),
            "--quarantine-root",
            str(tmp_path / "quarantine"),
        ]
    )
    assert code == 0
    assert calls == [(True, "example.invalid", "retired")]
    assert "Status:     QUARANTINED" in capsys.readouterr().out


def test_quarantine_restore_cli_uses_explicit_package(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        cli.ToolkitConfig, "load", lambda self: FakeConfig()
    )
    package = tmp_path / "package"
    package.mkdir()
    (package / "zone.db").write_text("zone\n")
    (package / "zone.conf").write_text("declaration\n")
    import hashlib

    files = {
        name: hashlib.sha256((package / name).read_bytes()).hexdigest()
        for name in ("zone.db", "zone.conf")
    }
    (package / "manifest.json").write_text(
        json.dumps({
            "zone": "example.invalid",
            "status": "QUARANTINED",
            "files": files,
        })
    )
    zones = tmp_path / "zones"
    declarations = tmp_path / "bind/zones.d"
    index = tmp_path / "bind/zones.conf"
    zones.mkdir()
    declarations.mkdir(parents=True)
    index.write_text("# empty\n")
    calls = []

    def apply(self, plan, *, commit=False):
        calls.append((commit, plan.package_directory))
        return QuarantineRestoreResult(
            "tx-qr",
            plan.zone_name,
            "DRY-RUN",
            str(plan.package_directory),
            steps=[QuarantineRestoreStep("dry-run", True, "OK")],
        )

    monkeypatch.setattr(cli.QuarantineRestoreTransaction, "apply", apply)
    code = cli.main([
        "zone", "quarantine-restore", "example.invalid",
        "--package", str(package),
        "--zone-directory", str(zones),
        "--managed-config", str(index),
        "--managed-zone-directory", str(declarations),
    ])
    assert code == 0
    assert calls == [(False, package)]
    assert "Status:     DRY-RUN" in capsys.readouterr().out


def test_inventory_cli_outputs_json(monkeypatch, capsys, tmp_path: Path) -> None:
    monkeypatch.setattr(
        cli.ToolkitConfig, "load", lambda self: FakeConfig()
    )
    package = tmp_path / "quarantine/example.invalid/tx-1"
    package.mkdir(parents=True)
    (package / "manifest.json").write_text(
        json.dumps(
            {
                "transaction_id": "tx-1",
                "zone": "example.invalid",
                "status": "QUARANTINED",
                "reason": "test",
                "operator": "root",
                "created_at": "2026-07-31T12:00:00+02:00",
            }
        ),
        encoding="utf-8",
    )

    code = cli.main(
        [
            "zone",
            "inventory",
            "--disabled-root",
            str(tmp_path / "disabled"),
            "--quarantine-root",
            str(tmp_path / "quarantine"),
            "--disable-manifest-directory",
            str(tmp_path / "manifests"),
            "--json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["zone"] == "example.invalid"
    assert payload[0]["state"] == "QUARANTINED"
