from __future__ import annotations

import ast
from pathlib import Path


SCRIPT = Path("scripts/run_screenshot_demo.py")


def test_screenshot_demo_is_isolated_from_host_and_network() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not imports & {"os", "socket", "subprocess", "urllib", "requests"}
    for forbidden in ("/etc/", "/var/", "BindService", "ToolkitConfig", "environ"):
        assert forbidden not in source


def test_screenshot_demo_uses_only_reserved_names_and_addresses() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "example.test" in source
    assert "demo.example" in source
    assert "sample.invalid" in source
    assert "CursesApp" in source
    assert "ZoneCreateDialog().collect" in source
    assert "NewRecordDialog().create_record_dialog" in source
    assert "192.0.2.10" in source
    assert "2001:db8::10" in source
    assert "DnssecStatusView" in source
    assert '"A1" * 32' in source
