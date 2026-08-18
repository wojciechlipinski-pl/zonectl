from pathlib import Path

from zonectl.core.rpz_managed_install import (
    RpzManagedInstallDryRun,
    RpzManagedInstallTransaction,
)
from zonectl.core.rpz_managed_plan import RpzManagedPlan
from zonectl.core.runner import CommandResult


def _plan(tmp_path: Path, *, status: str = "READY") -> RpzManagedPlan:
    root = tmp_path / "named.conf"
    options = tmp_path / "named.conf.options"
    root.write_text(f'include "{options}";\n', encoding="utf-8")
    options.write_text("options { recursion no; };\n", encoding="utf-8")
    return RpzManagedPlan(
        status=status,
        zone="cert-rpz.local",
        source_url="https://hole.cert.pl/domains/v2/domains_rpz.db",
        root_config=root,
        zone_file=tmp_path / "system" / "domains_rpz.db",
        declaration_file=tmp_path / "system" / "zonectl-rpz.conf",
        updater_file=tmp_path / "system" / "update-cert-rpz",
        service_file=tmp_path / "system" / "zonectl-cert-rpz.service",
        timer_file=tmp_path / "system" / "zonectl-cert-rpz.timer",
        backup_root=tmp_path / "backup",
        conflicts=() if status == "READY" else ("conflict",),
        steps=(),
        next_action="dry-run",
        options_file=options,
    )


def test_dry_run_builds_and_validates_candidates_without_system_writes(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def runner(command: list[str], _timeout: int) -> CommandResult:
        commands.append(command)
        return CommandResult(0, "OK", "")

    plan = _plan(tmp_path)
    result = RpzManagedInstallDryRun(
        command_runner=runner,
        fetcher=lambda _url: b"$TTL 60\n@ IN SOA localhost. root.localhost. 1 60 60 60 60\n",
    ).execute(plan)

    assert result.status == "DRY-RUN"
    assert {command[0] for command in commands} == {"bash", "named-checkzone", "named-checkconf"}
    assert "options" in result.candidate_hashes
    assert not plan.zone_file.exists()
    assert not plan.declaration_file.exists()
    assert not plan.updater_file.exists()
    assert not plan.service_file.exists()
    assert not plan.timer_file.exists()


def test_dry_run_blocks_external_or_conflicting_plan(tmp_path: Path) -> None:
    result = RpzManagedInstallDryRun(
        fetcher=lambda _url: b"unused"
    ).execute(_plan(tmp_path, status="BLOCKED_EXTERNAL"))
    assert result.status == "BLOCKED"
    assert result.steps[0].name == "preflight"


def test_dry_run_requires_https(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    object.__setattr__(plan, "source_url", "http://example.invalid/rpz")
    result = RpzManagedInstallDryRun(fetcher=lambda _url: b"unused").execute(plan)
    assert result.status == "BLOCKED"
    assert "HTTPS" in result.steps[0].message


def test_response_policy_is_inserted_inside_options_block() -> None:
    candidate = RpzManagedInstallDryRun._inject_response_policy(
        "options {\n    recursion no;\n};\n", "cert-rpz.local"
    )
    assert 'response-policy { zone "cert-rpz.local"; };' in candidate
    assert candidate.index("response-policy") < candidate.index("};")


def test_existing_response_policy_is_rejected() -> None:
    try:
        RpzManagedInstallDryRun._inject_response_policy(
            'options { response-policy { zone "other"; }; };\n', "cert-rpz.local"
        )
    except ValueError as exc:
        assert "już response-policy" in str(exc)
    else:
        raise AssertionError("existing response-policy must be rejected")


def test_updater_guards_serial_and_creates_backup(tmp_path: Path) -> None:
    updater = RpzManagedInstallDryRun._updater(_plan(tmp_path))
    assert 'test "$new_serial" -ge "$current_serial"' in updater
    assert "named-checkzone -D" in updater
    assert "cp -p" in updater
    assert "rndc reload" in updater


def _simple_atomic(path: Path, content: bytes, mode: int, uid: int, gid: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _ok_runner(command: list[str], _timeout: int) -> CommandResult:
    if command[:2] == ["systemctl", "show"]:
        return CommandResult(0, "success\n", "")
    return CommandResult(0, "OK", "")


def test_transaction_defaults_to_dry_run(tmp_path: Path, monkeypatch) -> None:
    plan = _plan(tmp_path)
    transaction = RpzManagedInstallTransaction(
        command_runner=_ok_runner,
        fetcher=lambda _url: b"$TTL 60\n@ IN SOA localhost. root.localhost. 1 60 60 60 60\n",
        manifest_directory=tmp_path / "manifests",
    )
    result = transaction.apply(plan)
    assert result.status == "DRY-RUN"
    assert not result.committed
    assert not plan.zone_file.exists()


def test_transaction_requires_both_flags_and_exact_confirmation(tmp_path: Path) -> None:
    transaction = RpzManagedInstallTransaction(
        command_runner=_ok_runner,
        fetcher=lambda _url: b"zone",
        manifest_directory=tmp_path / "manifests",
    )
    assert transaction.apply(_plan(tmp_path), commit=True).status == "REJECTED"
    assert transaction.apply(
        _plan(tmp_path), commit=True, activate=True, confirm="wrong"
    ).status == "REJECTED"


def test_transaction_commits_after_all_gates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        RpzManagedInstallTransaction, "_atomic_write", staticmethod(_simple_atomic)
    )
    plan = _plan(tmp_path)
    transaction = RpzManagedInstallTransaction(
        command_runner=_ok_runner,
        fetcher=lambda _url: b"$TTL 60\n@ IN SOA localhost. root.localhost. 1 60 60 60 60\n",
        manifest_directory=tmp_path / "manifests",
        clock=lambda: plan.zone_file.stat().st_mtime,
    )
    result = transaction.apply(
        plan, commit=True, activate=True, confirm="cert-rpz.local"
    )
    assert result.status == "COMMIT"
    assert result.committed and result.activated and not result.rolled_back
    assert plan.zone_file.exists()
    assert 'response-policy { zone "cert-rpz.local"; };' in plan.options_file.read_text()
    assert f'include "{plan.declaration_file}";' in plan.root_config.read_text()
    assert result.manifest and Path(result.manifest).exists()


def test_transaction_rolls_back_configuration_after_activation_failure(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        RpzManagedInstallTransaction, "_atomic_write", staticmethod(_simple_atomic)
    )
    plan = _plan(tmp_path)
    original_options = plan.options_file.read_bytes()
    original_root = plan.root_config.read_bytes()

    def failing_runner(command: list[str], _timeout: int) -> CommandResult:
        if command[:2] == ["systemctl", "start"]:
            return CommandResult(1, "", "forced failure")
        return _ok_runner(command, _timeout)

    result = RpzManagedInstallTransaction(
        command_runner=failing_runner,
        fetcher=lambda _url: b"$TTL 60\n@ IN SOA localhost. root.localhost. 1 60 60 60 60\n",
        manifest_directory=tmp_path / "manifests",
    ).apply(plan, commit=True, activate=True, confirm="cert-rpz.local")
    assert result.status == "ROLLED-BACK"
    assert result.rolled_back and not result.committed
    assert plan.options_file.read_bytes() == original_options
    assert plan.root_config.read_bytes() == original_root
    assert not any(path.exists() for path in RpzManagedInstallTransaction._targets(plan))
