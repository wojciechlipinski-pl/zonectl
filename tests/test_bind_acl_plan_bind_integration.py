from pathlib import Path
import shutil

import pytest

from zonectl.core.bind_acl_plan import BindAclPlanner


pytestmark = pytest.mark.skipif(
    shutil.which("named-checkconf") is None, reason="Brak named-checkconf"
)


def test_real_named_checkconf_accepts_acl_candidate(tmp_path: Path) -> None:
    root = tmp_path / "named.conf"
    options = tmp_path / "named.conf.options"
    root.write_text(f'include "{options}";\n', encoding="utf-8")
    options.write_text(
        'acl "trusted" {\n'
        '  192.168.200/24;\n'
        '  172.24.0.0/16;\n'
        '  172.24.0.0/16;\n'
        '};\n'
        'options { allow-query { trusted; }; };\n',
        encoding="utf-8",
    )
    before = options.read_bytes()

    plan = BindAclPlanner(root).plan(
        "trusted", replacements={"192.168.200/24": "192.168.200.0/24"}
    )

    assert plan.validation_ok is True
    assert plan.candidate_text.count("172.24.0.0/16") == 1
    assert options.read_bytes() == before
