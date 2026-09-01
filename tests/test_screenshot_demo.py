from __future__ import annotations

import ast
import struct
from pathlib import Path


SCRIPT = Path("scripts/run_screenshot_demo.py")
IMAGES = Path("docs/images")


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
    assert "_show_access_report" in source
    assert "_show_transaction_result" in source
    assert "_show_rollback_result" in source
    assert "_show_audit_browser" in source
    assert "AuditViewState" in source
    assert 'status="COMMITTED"' in source
    assert 'status="ROLLED-BACK"' in source
    assert "/tmp/zonectl-demo/backups/" in source


def _png_chunk_types(path: Path) -> list[bytes]:
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    chunks: list[bytes] = []
    offset = 8
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunks.append(chunk_type)
        offset += 12 + length
        if chunk_type == b"IEND":
            break
    assert offset == len(data)
    return chunks


def test_published_screenshots_have_no_textual_metadata() -> None:
    images = sorted(IMAGES.glob("*.png"))
    assert [image.name for image in images] == [
        "tui-add-record.png",
        "tui-audit-browser.png",
        "tui-bind-access.png",
        "tui-bind-environment.png",
        "tui-create-zone.png",
        "tui-dnssec-status.png",
        "tui-main-wait.png",
        "tui-records.png",
        "tui-rollback-result.png",
        "tui-transaction-result.png",
    ]
    forbidden_metadata = {b"tEXt", b"zTXt", b"iTXt", b"eXIf"}
    for image in images:
        assert not forbidden_metadata.intersection(_png_chunk_types(image))
