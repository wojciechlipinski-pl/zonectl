from pathlib import Path

from zonectl.core.bind_access_inventory import BindAccessInventoryReader


def test_collects_definitions_usages_sources_and_lines(tmp_path: Path) -> None:
    root = tmp_path / "named.conf"
    included = tmp_path / "access.conf"
    root.write_text(
        f'include "{included}";\n'
        'options { allow-recursion { trusted; localhost; }; };\n',
        encoding="utf-8",
    )
    included.write_text(
        '# ignored acl "fake" { any; };\n'
        'acl "trusted" {\n  127.0.0.1;\n  192.0.2.0/24;\n  !192.0.2.13;\n};\n'
        'primaries dns2-notify { 192.0.2.53; 2001:db8::53; };\n'
        'zone "example" { allow-transfer { trusted; }; '
        'also-notify { dns2-notify; }; };\n',
        encoding="utf-8",
    )
    report = BindAccessInventoryReader(root).collect()
    definitions = {(item.kind, item.name): item for item in report.definitions}
    assert definitions[("acl", "trusted")].entries == (
        "127.0.0.1", "192.0.2.0/24", "!192.0.2.13"
    )
    assert definitions[("acl", "trusted")].line == 2
    assert definitions[("primaries", "dns2-notify")].entries == (
        "192.0.2.53", "2001:db8::53"
    )
    usages = {(item.directive, item.values) for item in report.usages}
    assert ("allow-recursion", ("trusted", "localhost")) in usages
    assert ("allow-transfer", ("trusted",)) in usages
    assert ("also-notify", ("dns2-notify",)) in usages


def test_json_payload_uses_string_paths(tmp_path: Path) -> None:
    root = tmp_path / "named.conf"
    root.write_text('acl "trusted" { localhost; };\n', encoding="utf-8")
    payload = BindAccessInventoryReader(root).collect().to_dict()
    assert payload["definitions"][0]["source"] == str(root.resolve())
    assert payload["definitions"][0]["entries"] == ["localhost"]
