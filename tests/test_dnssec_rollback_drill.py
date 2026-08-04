from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "tools" / "dnssec_rollback_drill.py"
SPEC = importlib.util.spec_from_file_location("dnssec_rollback_drill", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
drill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(drill)


def test_drill_rejects_every_other_zone() -> None:
    with pytest.raises(SystemExit, match="wyłącznie"):
        drill.main(["--zone", "mops.elk.pl"])


def test_execute_requires_exact_confirmation() -> None:
    with pytest.raises(SystemExit, match="--confirm"):
        drill.main(["--execute"])


def test_forced_verifier_always_returns_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        drill,
        "run",
        lambda *_args: type(
            "Outcome",
            (),
            {"returncode": 0, "stdout": "zone signing: yes\n", "stderr": ""},
        )(),
    )

    step = drill.forced_failure_after_dnssec_observed(drill.DRILL_ZONE)

    assert step.ok is False
    assert step.name == "forced-dnssec-failure"
    assert "zaobserwowany" in step.message
