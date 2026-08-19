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
        '  198.51.100/24;\n'
        '  203.0.113.0/24;\n'
        '  203.0.113.0/24;\n'
        '};\n'
        'options { allow-query { trusted; }; };\n',
        encoding="utf-8",
    )
    before = options.read_bytes()

    plan = BindAclPlanner(root).plan(
        "trusted", replacements={"198.51.100/24": "198.51.100.0/24"}
    )

    assert plan.validation_ok is True
    assert plan.candidate_text.count("203.0.113.0/24") == 1
    assert options.read_bytes() == before


def test_real_named_checkconf_accepts_full_acl_list(tmp_path: Path) -> None:
    root = tmp_path / "named.conf"
    root.write_text(
        'acl "trusted" {\n  localhost;\n  192.0.2.0/24;\n};\n'
        'options { allow-query { trusted; }; };\n', encoding="utf-8"
    )
    before = root.read_bytes()
    plan = BindAclPlanner(root).plan(
        "trusted", entries=["localhost", "198.51.100.0/24", "!192.0.2.55"]
    )
    assert plan.validation_ok is True
    assert "198.51.100.0/24" in plan.candidate_text
    assert root.read_bytes() == before
