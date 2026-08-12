from pathlib import Path
import shutil

import pytest

from zonectl.core.bind_secondary_plan import BindSecondaryPlanner


pytestmark = pytest.mark.skipif(
    shutil.which("named-checkconf") is None, reason="Brak named-checkconf"
)


def test_real_named_checkconf_accepts_secondary_candidate(tmp_path: Path) -> None:
    root = tmp_path / "named.conf"
    root.write_text(
        'primaries dns2-notify { 192.0.2.53; };\n'
        'zone "a.invalid" { type primary; file "/tmp/a.invalid"; '
        'also-notify { dns2-notify; }; };\n', encoding="utf-8"
    )
    before = root.read_bytes()
    plan = BindSecondaryPlanner(root).plan(
        "dns2-notify", ["192.0.2.60", "2001:db8::53"]
    )
    assert plan.validation_ok is True
    assert root.read_bytes() == before
