from pathlib import Path

import pytest

from zonectl.core.bind_bootstrap import (
    BindBootstrapError,
    BindBootstrapStep,
    BindBootstrapTransaction,
)


def layout(tmp_path: Path):
    bind = tmp_path / "bind"
    bind.mkdir()
    local = bind / "named.conf.local"
    local.write_text('// local\nzone "existing" { type primary; };\n')
    root = bind / "named.conf"
    root.write_text(f'include "{local}";\n')
    index = bind / "zonectl-zones.conf"
    declarations = bind / "zonectl-zones.d"
    manifests = tmp_path / "manifests"
    return local, root, index, declarations, manifests


def valid(_path: Path) -> BindBootstrapStep:
    return BindBootstrapStep("named-checkconf", True, "OK")


def test_plan_has_no_side_effects(tmp_path: Path) -> None:
    local, root, index, declarations, manifests = layout(tmp_path)
    plan = BindBootstrapTransaction.plan(
        local_config=local,
        managed_index=index,
        managed_zone_directory=declarations,
        root_config=root,
    )
    result = BindBootstrapTransaction(
        manifests, config_validator=valid
    ).apply(plan)
    assert result.status == "DRY-RUN"
    assert not index.exists()
    assert not declarations.exists()
    assert "ZoneCTL" not in local.read_text()


def test_commit_creates_index_directory_include_backup_and_manifest(
    tmp_path: Path,
) -> None:
    local, root, index, declarations, manifests = layout(tmp_path)
    local.chmod(0o644)
    original = local.read_bytes()
    plan = BindBootstrapTransaction.plan(
        local_config=local,
        managed_index=index,
        managed_zone_directory=declarations,
        root_config=root,
    )
    result = BindBootstrapTransaction(
        manifests, config_validator=valid
    ).apply(plan, commit=True)
    assert result.status == "COMMIT"
    assert index.read_text().startswith("# ZoneCTL")
    assert declarations.is_dir()
    assert local.read_text().count(f'include "{index}";') == 1
    assert local.stat().st_mode & 0o777 == 0o644
    assert Path(result.backup).read_bytes() == original
    assert Path(result.manifest).is_file()


def test_existing_index_is_preserved_and_bootstrap_is_idempotent(
    tmp_path: Path,
) -> None:
    local, root, index, declarations, manifests = layout(tmp_path)
    index.write_text('// keep\ninclude "/custom/example.conf";\n')
    declarations.mkdir()
    transaction = BindBootstrapTransaction(
        manifests, config_validator=valid
    )
    first = transaction.apply(
        transaction.plan(
            local_config=local,
            managed_index=index,
            managed_zone_directory=declarations,
            root_config=root,
        ),
        commit=True,
    )
    second = transaction.apply(
        transaction.plan(
            local_config=local,
            managed_index=index,
            managed_zone_directory=declarations,
            root_config=root,
        ),
        commit=True,
    )
    assert first.status == second.status == "COMMIT"
    assert index.read_text() == '// keep\ninclude "/custom/example.conf";\n'
    assert local.read_text().count(f'include "{index}";') == 1


def test_validation_failure_restores_original_state(tmp_path: Path) -> None:
    local, root, index, declarations, manifests = layout(tmp_path)
    local.chmod(0o644)
    original = local.read_bytes()

    def invalid(_path: Path) -> BindBootstrapStep:
        return BindBootstrapStep("named-checkconf", False, "bad config")

    transaction = BindBootstrapTransaction(
        manifests, config_validator=invalid
    )
    result = transaction.apply(
        transaction.plan(
            local_config=local,
            managed_index=index,
            managed_zone_directory=declarations,
            root_config=root,
        ),
        commit=True,
    )
    assert result.status == "ROLLED-BACK"
    assert result.rolled_back
    assert local.read_bytes() == original
    assert local.stat().st_mode & 0o777 == 0o644
    assert not index.exists()
    assert not declarations.exists()


def test_duplicate_include_is_rejected(tmp_path: Path) -> None:
    local, root, index, declarations, manifests = layout(tmp_path)
    include = f'include "{index}";\n'
    local.write_text(include + include)
    with pytest.raises(BindBootstrapError, match="Powielony"):
        BindBootstrapTransaction.plan(
            local_config=local,
            managed_index=index,
            managed_zone_directory=declarations,
            root_config=root,
        )
