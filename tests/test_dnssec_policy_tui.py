from __future__ import annotations

import inspect
from pathlib import Path

from zonectl.core.dnssec_policy_inventory import DnssecPolicyInventoryReader
from zonectl.core.bind_capabilities import BindCapabilities
from zonectl.ui.curses_app import CursesApp
from zonectl.ui.dnssec_policy_view import dnssec_policy_lines


def test_dnssec_status_routes_f5_to_read_only_policy_view() -> None:
    source = inspect.getsource(CursesApp._dnssec_status_view)
    view = inspect.getsource(CursesApp._dnssec_policy_inventory_view)
    assert "curses.KEY_F5" in source
    assert "self._dnssec_policy_inventory_view(win, zone)" in source
    assert "DnssecPolicyInventoryReader" in view
    assert "BindCapabilityDetector" in view
    assert "_run_with_wait_indicator" in view


def test_policy_lines_prioritize_selected_zone_and_remain_synthetic(
    tmp_path: Path,
) -> None:
    zone_file = tmp_path / "alpha.db"
    zone_file.write_text("", encoding="utf-8")
    root = tmp_path / "named.conf"
    root.write_text(
        f'''dnssec-policy modern {{
  keys {{ csk lifetime P1Y algorithm ED25519; }};
  dnskey-ttl 1h;
}};
zone "alpha.example.test" {{
  type primary; file "{zone_file}"; dnssec-policy modern;
}};
''',
        encoding="utf-8",
    )
    lines = dnssec_policy_lines(
        DnssecPolicyInventoryReader(root).read(), zone_name="alpha.example.test"
    )
    text = "\n".join(lines)
    assert "[PASS] modern (nazwana) [STREFA]" in text
    assert "CSK: ED25519; lifetime=P1Y" in text
    assert "dnskey-ttl=1h" in text
    assert "niczego nie zmieniono" in text


def test_policy_lines_show_bind_compatibility(tmp_path: Path) -> None:
    zone_file = tmp_path / "alpha.db"
    zone_file.write_text("", encoding="utf-8")
    root = tmp_path / "named.conf"
    root.write_text(
        f'''dnssec-policy modern {{
  inline-signing yes;
  keys {{ csk lifetime unlimited algorithm ED25519; }};
}};
zone "alpha.example.test" {{
  type primary; file "{zone_file}"; dnssec-policy modern;
}};
''',
        encoding="utf-8",
    )
    capabilities = BindCapabilities(
        detected=True,
        version="9.20.26",
        series="9.20",
        status="PASS",
        dnssec_policy=True,
        inline_signing_in_policy=True,
        nsec3_iterations_zero_required=True,
        findings=(),
    )

    text = "\n".join(
        dnssec_policy_lines(DnssecPolicyInventoryReader(root, capabilities).read())
    )

    assert "BIND: 9.20.26 [PASS]" in text
    assert "Zgodność z BIND: COMPATIBLE" in text


def test_policy_view_uses_scrollable_small_terminal_safe_message_view() -> None:
    source = inspect.getsource(CursesApp._dnssec_policy_inventory_view)

    assert "self._message_view(" in source
    assert "dnssec_policy_lines(" in source
    assert "_run_with_wait_indicator" in source
