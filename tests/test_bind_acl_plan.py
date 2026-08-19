from pathlib import Path

from zonectl.core.bind_acl_plan import BindAclPlanner


def _config(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "named.conf"
    options = tmp_path / "named.conf.options"
    root.write_text(f'include "{options}";\n', encoding="utf-8")
    options.write_text(
        'acl "trusted" {\n'
        '    localhost; // zachowaj komentarz\n'
        '    198.51.100/24;\n'
        '    203.0.113.0/24;\n'
        '    203.0.113.0/24;\n'
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
        "trusted", replacements={"198.51.100/24": "198.51.100.0/24"}
    )

    assert "198.51.100.0/24" in plan.candidate_text
    assert plan.candidate_text.count("203.0.113.0/24") == 1
    assert "// zachowaj komentarz" in plan.candidate_text
    assert plan.replacements == ("198.51.100/24 -> 198.51.100.0/24",)
    assert plan.removed_duplicates == ("203.0.113.0/24",)
    assert "-    203.0.113.0/24;" in plan.diff
    assert "+    203.0.113.0/24;" not in plan.diff
    assert "\n-    localhost;" not in plan.diff
    assert "\n+    localhost;" not in plan.diff
    assert "\n- \n" not in plan.diff
    assert "\n-    203.0.113.0/24;\n+    203.0.113.0/24;" not in plan.diff
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
        replacements={"198.51.100/24": "198.51.100.0/24"},
        remove_duplicates=False,
    )
    assert plan.candidate_text.count("203.0.113.0/24") == 2
    assert plan.removed_duplicates == ()


def test_full_list_plan_preserves_unchanged_inline_comment(
    tmp_path: Path, monkeypatch
) -> None:
    root, _ = _config(tmp_path)
    monkeypatch.setattr(
        BindAclPlanner, "_validate_candidate",
        lambda self, source, candidate: (True, "kod 0"),
    )
    plan = BindAclPlanner(root).plan(
        "trusted", entries=["localhost", "192.0.2.0/24"]
    )
    assert "localhost; // zachowaj komentarz" in plan.candidate_text
    assert "192.0.2.0/24;" in plan.candidate_text
    assert "203.0.113.0/24" not in plan.candidate_text


def test_full_list_rejects_empty_duplicate_invalid_and_missing_localhost(
    tmp_path: Path,
) -> None:
    root, _ = _config(tmp_path)
    planner = BindAclPlanner(root)
    for entries in (
        [],
        ["localhost", "192.0.2.1", "192.0.2.1/32"],
        ["localhost", "bad value"],
        ["192.0.2.0/24"],
    ):
        try:
            planner.plan("trusted", entries=entries)
        except Exception as exc:
            assert "ACL" in str(exc) or "element" in str(exc)
        else:
            raise AssertionError(f"Nie odrzucono: {entries}")
