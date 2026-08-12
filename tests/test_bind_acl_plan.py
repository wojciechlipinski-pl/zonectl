from pathlib import Path

from zonectl.core.bind_acl_plan import BindAclPlanner


def _config(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "named.conf"
    options = tmp_path / "named.conf.options"
    root.write_text(f'include "{options}";\n', encoding="utf-8")
    options.write_text(
        'acl "trusted" {\n'
        '    localhost; // zachowaj komentarz\n'
        '    192.168.200/24;\n'
        '    172.24.0.0/16;\n'
        '    172.24.0.0/16;\n'
        '};\n'
        'options { allow-query { trusted; }; };\n',
        encoding="utf-8",
    )
    return root, options


def test_plan_replaces_value_removes_later_duplicate_and_preserves_comment(
    tmp_path: Path, monkeypatch
) -> None:
    root, options = _config(tmp_path)
    monkeypatch.setattr(
        BindAclPlanner,
        "_validate_candidate",
        lambda self, source, candidate: (True, "kod 0"),
    )
    before = options.read_bytes()

    plan = BindAclPlanner(root).plan(
        "trusted", replacements={"192.168.200/24": "192.168.200.0/24"}
    )

    assert "192.168.200.0/24" in plan.candidate_text
    assert plan.candidate_text.count("172.24.0.0/16") == 1
    assert "// zachowaj komentarz" in plan.candidate_text
    assert plan.replacements == ("192.168.200/24 -> 192.168.200.0/24",)
    assert plan.removed_duplicates == ("172.24.0.0/16",)
    assert "-    172.24.0.0/16;" in plan.diff
    assert "+    172.24.0.0/16;" not in plan.diff
    assert "\n-    localhost;" not in plan.diff
    assert "\n+    localhost;" not in plan.diff
    assert "\n- \n" not in plan.diff
    assert "\n-    172.24.0.0/16;\n+    172.24.0.0/16;" not in plan.diff
    assert options.read_bytes() == before


def test_keep_duplicates_only_applies_replacement(tmp_path: Path, monkeypatch) -> None:
    root, _ = _config(tmp_path)
    monkeypatch.setattr(
        BindAclPlanner,
        "_validate_candidate",
        lambda self, source, candidate: (True, "kod 0"),
    )
    plan = BindAclPlanner(root).plan(
        "trusted",
        replacements={"192.168.200/24": "192.168.200.0/24"},
        remove_duplicates=False,
    )
    assert plan.candidate_text.count("172.24.0.0/16") == 2
    assert plan.removed_duplicates == ()
