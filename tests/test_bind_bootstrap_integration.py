from pathlib import Path
import shutil

import pytest

from zonectl.core.bind_bootstrap import BindBootstrapTransaction


pytestmark = pytest.mark.skipif(
    shutil.which("named-checkconf") is None,
    reason="named-checkconf is not installed",
)


def bind_layout(tmp_path: Path):
    bind = tmp_path / "bind"
    bind.mkdir()
    local = bind / "named.conf.local"
    local.write_text("// local configuration\n", encoding="utf-8")
    root = bind / "named.conf"
    root.write_text(f'include "{local}";\n', encoding="utf-8")
    return (
        local,
        root,
        bind / "zonectl-zones.conf",
        bind / "zonectl-zones.d",
    )


def test_real_named_checkconf_accepts_bootstrap(tmp_path: Path) -> None:
    local, root, index, declarations = bind_layout(tmp_path)
    transaction = BindBootstrapTransaction(tmp_path / "manifests")
    plan = transaction.plan(
        local_config=local,
        managed_index=index,
        managed_zone_directory=declarations,
        root_config=root,
    )
    result = transaction.apply(plan, commit=True)
    assert result.status == "COMMIT"
    assert result.committed


def test_real_named_checkconf_failure_rolls_back(tmp_path: Path) -> None:
    local, root, index, declarations = bind_layout(tmp_path)
    original = local.read_bytes()
    root.write_text(
        f'include "{local}";\nthis is invalid;\n',
        encoding="utf-8",
    )
    transaction = BindBootstrapTransaction(tmp_path / "manifests")
    plan = transaction.plan(
        local_config=local,
        managed_index=index,
        managed_zone_directory=declarations,
        root_config=root,
    )
    result = transaction.apply(plan, commit=True)
    assert result.status == "ROLLED-BACK"
    assert local.read_bytes() == original
    assert not index.exists()
    assert not declarations.exists()
