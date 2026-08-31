from pathlib import Path

from zonectl.core.config import ToolkitConfig


def write_toolkit_config(
    path: Path,
    bind_config: Path,
    auto_discover: bool = True,
) -> None:
    path.write_text(
        "[toolkit]\n"
        f"bind_config = {bind_config}\n"
        f"auto_discover_zones = "
        f"{'yes' if auto_discover else 'no'}\n",
        encoding="utf-8",
    )


def test_toolkit_uses_discovered_zone_file(
    tmp_path: Path,
) -> None:
    source = tmp_path / "example.pl"
    source.write_text("zone\n", encoding="utf-8")

    bind_config = tmp_path / "named.conf"
    bind_config.write_text(
        f'''
        zone "example.pl" {{
            type master;
            file "{source}";
        }};
        ''',
        encoding="utf-8",
    )

    toolkit_config = tmp_path / "toolkit.conf"
    zones_config = tmp_path / "zones.conf"
    groups_config = tmp_path / "groups.yaml"

    write_toolkit_config(
        toolkit_config,
        bind_config,
    )

    config = ToolkitConfig(
        toolkit_config,
        zones_config,
        groups_config,
    ).load()

    zones = config.zones()

    assert len(zones) == 1
    assert zones[0].name == "example.pl"
    assert zones[0].file == source.resolve()


def test_zones_conf_overrides_toolkit_metadata_only(
    tmp_path: Path,
) -> None:
    real_source = tmp_path / "real-example.pl"
    real_source.write_text("zone\n", encoding="utf-8")

    wrong_source = tmp_path / "wrong-example.pl"
    wrong_source.write_text("wrong\n", encoding="utf-8")

    bind_config = tmp_path / "named.conf"
    bind_config.write_text(
        f'''
        zone "example.pl" {{
            type master;
            file "{real_source}";
        }};
        ''',
        encoding="utf-8",
    )

    toolkit_config = tmp_path / "toolkit.conf"
    zones_config = tmp_path / "zones.conf"
    groups_config = tmp_path / "groups.yaml"

    write_toolkit_config(
        toolkit_config,
        bind_config,
    )

    zones_config.write_text(
        f"[example.pl]\nfile = {wrong_source}\ngroup = Testowe\ndns2 = no\nhe = yes\n",
        encoding="utf-8",
    )

    config = ToolkitConfig(
        toolkit_config,
        zones_config,
        groups_config,
    ).load()

    zone = config.zones()[0]

    # Plik zawsze pochodzi z aktywnej konfiguracji BIND.
    assert zone.file == real_source.resolve()

    # Metadane Toolkitu mogą pochodzić z zones.conf.
    assert zone.group == "Testowe"
    assert zone.dns2 is False
    assert zone.he is True


def test_disabled_zone_is_hidden(
    tmp_path: Path,
) -> None:
    source = tmp_path / "example.pl"
    source.write_text("zone\n", encoding="utf-8")

    bind_config = tmp_path / "named.conf"
    bind_config.write_text(
        f'''
        zone "example.pl" {{
            type master;
            file "{source}";
        }};
        ''',
        encoding="utf-8",
    )

    toolkit_config = tmp_path / "toolkit.conf"
    zones_config = tmp_path / "zones.conf"
    groups_config = tmp_path / "groups.yaml"

    write_toolkit_config(
        toolkit_config,
        bind_config,
    )

    zones_config.write_text(
        "[example.pl]\nenabled = no\n",
        encoding="utf-8",
    )

    config = ToolkitConfig(
        toolkit_config,
        zones_config,
        groups_config,
    ).load()

    assert config.zones() == []


def test_secondary_zone_is_not_editable(
    tmp_path: Path,
) -> None:
    source = tmp_path / "secondary.pl"
    source.write_text("zone\n", encoding="utf-8")

    bind_config = tmp_path / "named.conf"
    bind_config.write_text(
        f'''
        zone "secondary.pl" {{
            type secondary;
            file "{source}";
        }};
        ''',
        encoding="utf-8",
    )

    toolkit_config = tmp_path / "toolkit.conf"
    zones_config = tmp_path / "zones.conf"
    groups_config = tmp_path / "groups.yaml"

    write_toolkit_config(
        toolkit_config,
        bind_config,
    )

    config = ToolkitConfig(
        toolkit_config,
        zones_config,
        groups_config,
    ).load()

    assert config.zones() == []


def test_legacy_mode_uses_zones_conf(
    tmp_path: Path,
) -> None:
    toolkit_config = tmp_path / "toolkit.conf"
    zones_config = tmp_path / "zones.conf"
    groups_config = tmp_path / "groups.yaml"

    write_toolkit_config(
        toolkit_config,
        tmp_path / "missing-named.conf",
        auto_discover=False,
    )

    source = tmp_path / "legacy.pl"

    zones_config.write_text(
        f"[legacy.pl]\nfile = {source}\ngroup = Legacy\n",
        encoding="utf-8",
    )

    config = ToolkitConfig(
        toolkit_config,
        zones_config,
        groups_config,
    ).load()

    zones = config.zones()

    assert len(zones) == 1
    assert zones[0].name == "legacy.pl"
    assert zones[0].file == source
    assert zones[0].group == "Legacy"
