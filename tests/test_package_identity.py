from importlib import import_module

import elkman_dns
import zonectl


def test_new_and_legacy_namespaces_share_version() -> None:
    assert zonectl.__version__ == elkman_dns.__version__


def test_zonectl_cli_is_importable() -> None:
    cli = import_module("zonectl.cli")

    assert cli.main.__module__ == "zonectl.cli"
    assert cli.deprecated_main.__module__ == "zonectl.cli"


def test_legacy_cli_remains_importable() -> None:
    cli = import_module("elkman_dns.cli")

    assert callable(cli.main)
    assert callable(cli.deprecated_main)
