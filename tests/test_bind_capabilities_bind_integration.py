from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from zonectl.core.bind_capabilities import BindCapabilityDetector


pytestmark = pytest.mark.skipif(
    shutil.which("named-checkconf") is None,
    reason="Brak narzędzia named-checkconf",
)


def test_real_bind_version_matches_reported_policy_grammar(tmp_path: Path) -> None:
    report = BindCapabilityDetector().detect()
    assert report.detected is True
    assert report.version is not None
    assert report.series is not None
    assert report.dnssec_policy is True

    config = tmp_path / "named.conf"
    config.write_text(
        "dnssec-policy modern {\n"
        "  inline-signing yes;\n"
        "  keys { csk lifetime unlimited algorithm ED25519; };\n"
        "};\n",
        encoding="utf-8",
    )
    validation = subprocess.run(
        ["named-checkconf", str(config)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert (validation.returncode == 0) is report.inline_signing_in_policy


def test_real_version_report_contains_no_build_environment() -> None:
    payload = BindCapabilityDetector().detect().to_dict()
    serialized = str(payload)

    assert "/" not in serialized
    assert "<id:" not in serialized
