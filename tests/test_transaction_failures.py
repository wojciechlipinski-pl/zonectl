from __future__ import annotations

from pathlib import Path

import zonectl.core.transaction as transaction_module
from zonectl.core.models import Zone
from zonectl.core.runner import CommandResult
from zonectl.core.transaction import TransactionEngine


class FakeConfig:
    def __init__(self, root: Path, zone: Zone):
        self.toolkit = {
            "state_dir": str(root / "state"),
            "transaction_backup_dir": str(root / "backups"),
            "transaction_dir": str(root / "transactions"),
            "lock_dir": str(root / "locks"),
            "audit_log": str(root / "audit.jsonl"),
            "command_timeout": "2",
            "local_server": "127.0.0.1",
        }
        self._zone = zone

    def zones(self) -> list[Zone]:
        return [self._zone]


def command_result(
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> CommandResult:
    return CommandResult(returncode, stdout, stderr)


def make_engine(
    tmp_path: Path,
) -> tuple[TransactionEngine, Path, Path]:
    target = tmp_path / "example.pl"
    source = tmp_path / "candidate.db"
    target.write_text(
        "$TTL 3600\n"
        "@ IN SOA ns.example.pl. hostmaster.example.pl. "
        "1 3600 600 86400 300\n",
        encoding="utf-8",
    )
    source.write_text(
        "$TTL 3600\n"
        "@ IN SOA ns.example.pl. hostmaster.example.pl. "
        "2 3600 600 86400 300\n",
        encoding="utf-8",
    )
    zone = Zone(name="example.pl", file=target)
    return TransactionEngine(FakeConfig(tmp_path, zone)), source, target


def test_named_checkzone_failure_does_not_modify_active_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine, source, target = make_engine(tmp_path)
    original = target.read_bytes()
    commands: list[list[str]] = []

    def fake_run(
        command: list[str],
        timeout: int,
    ) -> CommandResult:
        commands.append(command)
        assert command[0] == "named-checkzone"
        return command_result(
            1,
            stderr="zone example.pl/IN: loading from master file failed",
        )

    monkeypatch.setattr(transaction_module, "run", fake_run)

    result = engine.apply("example.pl", source, commit=True)

    assert result.status == "FAIL"
    assert result.committed is False
    assert result.rolled_back is False
    assert target.read_bytes() == original
    assert result.backup is None
    assert [step.name for step in result.steps] == [
        "source",
        "named-checkzone",
    ]
    assert commands == [
        ["named-checkzone", "example.pl", str(source.resolve())],
    ]


def test_rndc_reload_failure_restores_original_zone_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine, source, target = make_engine(tmp_path)
    original = target.read_bytes()
    reload_calls = 0

    def fake_run(
        command: list[str],
        timeout: int,
    ) -> CommandResult:
        nonlocal reload_calls

        if command[0] == "named-checkzone":
            return command_result(stdout=("zone example.pl/IN: loaded serial 2\nOK\n"))
        if command[0] == "named-checkconf":
            return command_result()
        if command[0] == "dig":
            return command_result(
                stdout=("ns.example.pl. hostmaster.example.pl. 1 3600 600 86400 300\n")
            )
        if command[:2] == ["rndc", "reload"]:
            reload_calls += 1
            if reload_calls == 1:
                return command_result(
                    1,
                    stderr="rndc: 'reload' failed: failure",
                )
            return command_result(stdout="zone reload successful\n")

        raise AssertionError(f"Nieoczekiwane polecenie: {command}")

    monkeypatch.setattr(transaction_module, "run", fake_run)

    result = engine.apply("example.pl", source, commit=True)

    assert result.status == "ROLLED-BACK"
    assert result.committed is False
    assert result.rolled_back is True
    assert result.backup is not None
    assert Path(result.backup).read_bytes() == original
    assert target.read_bytes() == original
    assert reload_calls == 2

    steps = {step.name: step for step in result.steps}
    assert steps["atomic-install"].ok is True
    assert steps["rndc-reload"].ok is False
    assert steps["transaction"].ok is False
    assert steps["rollback"].ok is True
