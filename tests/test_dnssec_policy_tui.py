from __future__ import annotations

import inspect
from pathlib import Path

from zonectl.core.dnssec_policy_inventory import DnssecPolicyInventoryReader
from zonectl.ui.curses_app import CursesApp
from zonectl.ui.dnssec_policy_view import dnssec_policy_lines


def test_dnssec_status_routes_f5_to_read_only_policy_view() -> None:
    source = inspect.getsource(CursesApp._dnssec_status_view)
    view = inspect.getsource(CursesApp._dnssec_policy_inventory_view)
    assert "curses.KEY_F5" in source
    assert "self._dnssec_policy_inventory_view(win, zone)" in source
    assert "DnssecPolicyInventoryReader" in view
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
