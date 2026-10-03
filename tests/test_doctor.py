from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from zonectl.core.doctor import (
    Doctor,
    DoctorCheck,
    DoctorReport,
    GitHistorySettings,
    issue_body,
    prepare_issue,
    privacy_findings,
    read_git_history_settings,
    submit_issue,
    write_public_report,
)


def _result(code: int = 0, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)


def _runner(command: list[str] | tuple[str, ...], timeout: int) -> SimpleNamespace:
    del timeout
    if list(command) == ["named-checkconf", "-v"]:
        return _result(stdout="BIND 9.20.11")
    if list(command) == ["dpkg-query", "-W", "-f=${Version}", "zonectl"]:
        return _result(stdout="4.18.0-1")
    if list(command)[-1:] == ["zonectl-cert-rpz.timer"]:
        return _result(1)
    return _result()


def test_doctor_returns_allowlisted_pass_report(tmp_path: Path) -> None:
    report = Doctor(
        zonectl_version="4.18.0",
        root_config=tmp_path / "named.conf",
        directories=(("backup", tmp_path),),
        command_runner=_runner,
        which=lambda name: f"/usr/bin/{name}",
        policy_probe=lambda path: DoctorCheck(
            "dnssec.policies", "PASS", "polityki bez blokad"
        ),
    ).collect()

    assert report.status == "PASS"
    assert report.bind_version == "9.20.11"
    assert report.package_version == "4.18.0-1"
    payload = report.to_dict()
    assert payload["schema"] == "zonectl.doctor/v1"
    assert str(tmp_path) not in str(payload)
    assert any(check.code == "rollback.readiness" for check in report.checks)
    assert any(check.code == "bind.control" for check in report.checks)


def test_doctor_classifies_missing_tool_and_inactive_bind_as_blocked() -> None:
    def runner(command: list[str] | tuple[str, ...], timeout: int) -> SimpleNamespace:
        del timeout
        if list(command) == ["systemctl", "is-active", "bind9"]:
            return _result(3)
        return _result()

    report = Doctor(
        zonectl_version="4.18.0",
        command_runner=runner,
        which=lambda name: None if name == "rndc" else f"/usr/bin/{name}",
        policy_probe=lambda path: DoctorCheck(
            "dnssec.policies", "WARN", "ocena niedostępna"
        ),
    ).collect()

    assert report.status == "BLOCKED"
    by_code = {check.code: check for check in report.checks}
    assert by_code["tool.rndc"].status == "BLOCKED"
    assert by_code["bind.service"].status == "BLOCKED"


def test_doctor_reports_denied_directory_and_low_space(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("zonectl.core.doctor.os.access", lambda path, mode: False)
    report = Doctor(
        zonectl_version="4.18.0",
        directories=(("backup", tmp_path),),
        command_runner=_runner,
        which=lambda name: f"/usr/bin/{name}",
        disk_usage=lambda path: SimpleNamespace(total=1, used=1, free=1),
        policy_probe=lambda path: DoctorCheck(
            "dnssec.policies", "PASS", "polityki bez blokad"
        ),
    ).collect()

    by_code = {check.code: check for check in report.checks}
    assert by_code["directory.backup"].status == "BLOCKED"
    assert by_code["storage.backup"].status == "WARN"
    assert by_code["rollback.readiness"].status == "BLOCKED"


def test_doctor_treats_disabled_git_history_as_healthy() -> None:
    report = Doctor(
        zonectl_version="4.18.0",
        command_runner=_runner,
        which=lambda name: f"/usr/bin/{name}",
        git_history=GitHistorySettings(False, Path("/not/inspected")),
        policy_probe=lambda path: DoctorCheck(
            "dnssec.policies", "PASS", "polityki bez blokad"
        ),
    ).collect()

    check = {item.code: item for item in report.checks}["directory.historia-git"]
    assert check.status == "PASS"
    assert "wyłączona" in check.summary


def test_doctor_warns_when_enabled_git_history_is_not_initialized(
    tmp_path: Path,
) -> None:
    report = Doctor(
        zonectl_version="4.18.0",
        command_runner=_runner,
        which=lambda name: f"/usr/bin/{name}",
        git_history=GitHistorySettings(True, tmp_path / "missing"),
        policy_probe=lambda path: DoctorCheck(
            "dnssec.policies", "PASS", "polityki bez blokad"
        ),
    ).collect()

    check = {item.code: item for item in report.checks}["directory.historia-git"]
    assert check.status == "WARN"
    assert "niezainicjalizowana" in check.summary


def test_doctor_accepts_private_remote_free_git_history(tmp_path: Path) -> None:
    repository = tmp_path / "history"
    (repository / ".git").mkdir(parents=True)
    repository.chmod(0o750)
    report = Doctor(
        zonectl_version="4.18.0",
        command_runner=_runner,
        which=lambda name: f"/usr/bin/{name}",
        git_history=GitHistorySettings(True, repository),
        policy_probe=lambda path: DoctorCheck(
            "dnssec.policies", "PASS", "polityki bez blokad"
        ),
    ).collect()

    by_code = {item.code: item for item in report.checks}
    assert by_code["directory.historia-git"].status == "PASS"
    assert by_code["storage.historia-git"].status == "PASS"


def test_doctor_blocks_git_history_with_remote(tmp_path: Path) -> None:
    repository = tmp_path / "history"
    (repository / ".git").mkdir(parents=True)
    repository.chmod(0o750)

    def runner(command: list[str] | tuple[str, ...], timeout: int) -> SimpleNamespace:
        if list(command)[:3] == ["git", "-C", str(repository)]:
            return _result(stdout="origin\n")
        return _runner(command, timeout)

    report = Doctor(
        zonectl_version="4.18.0",
        command_runner=runner,
        which=lambda name: f"/usr/bin/{name}",
        git_history=GitHistorySettings(True, repository),
        policy_probe=lambda path: DoctorCheck(
            "dnssec.policies", "PASS", "polityki bez blokad"
        ),
    ).collect()

    check = {item.code: item for item in report.checks}["directory.historia-git"]
    assert check.status == "BLOCKED"
    assert "remote" in check.summary


@pytest.mark.parametrize(
    ("repository_kind", "expected_summary"),
    [
        ("symlink", "niebezpieczny typ"),
        ("broad_permissions", "zbyt szerokie uprawnienia"),
        ("broken_repository", "uszkodzona lub niedostępna"),
    ],
)
def test_doctor_blocks_unsafe_git_history(
    tmp_path: Path,
    repository_kind: str,
    expected_summary: str,
) -> None:
    repository = tmp_path / "history"
    target = tmp_path / "target"
    target.mkdir()
    if repository_kind == "symlink":
        repository.symlink_to(target, target_is_directory=True)
    else:
        (repository / ".git").mkdir(parents=True)
        repository.chmod(0o775 if repository_kind == "broad_permissions" else 0o750)

    def runner(command: list[str] | tuple[str, ...], timeout: int) -> SimpleNamespace:
        if repository_kind == "broken_repository" and list(command)[:2] == [
            "git",
            "-C",
        ]:
            return _result(code=128, stderr="not a git repository")
        return _runner(command, timeout)

    report = Doctor(
        zonectl_version="4.18.0",
        command_runner=runner,
        which=lambda name: f"/usr/bin/{name}",
        git_history=GitHistorySettings(True, repository),
        policy_probe=lambda path: DoctorCheck(
            "dnssec.policies", "PASS", "polityki bez blokad"
        ),
    ).collect()

    check = {item.code: item for item in report.checks}["directory.historia-git"]
    assert check.status == "BLOCKED"
    assert expected_summary in check.summary


def test_doctor_blocks_enabled_git_history_without_git(tmp_path: Path) -> None:
    report = Doctor(
        zonectl_version="4.18.0",
        command_runner=_runner,
        which=lambda name: None if name == "git" else f"/usr/bin/{name}",
        git_history=GitHistorySettings(True, tmp_path / "history"),
        policy_probe=lambda path: DoctorCheck(
            "dnssec.policies", "PASS", "polityki bez blokad"
        ),
    ).collect()

    check = {item.code: item for item in report.checks}["tool.git"]
    assert check.status == "BLOCKED"
    assert "brak narzędzia Git" in check.summary


def test_read_git_history_settings_is_failure_tolerant(tmp_path: Path) -> None:
    missing = read_git_history_settings(tmp_path / "missing.conf")
    assert missing.enabled is False

    invalid = tmp_path / "invalid.conf"
    invalid.write_text("not an ini file", encoding="utf-8")
    assert read_git_history_settings(invalid).enabled is None

    configured = tmp_path / "toolkit.conf"
    repository = tmp_path / "history"
    configured.write_text(
        f"[toolkit]\ngit_history_enabled = yes\ngit_history_directory = {repository}\n",
        encoding="utf-8",
    )
    settings = read_git_history_settings(configured)
    assert settings == GitHistorySettings(True, repository)


@pytest.mark.parametrize(
    "secret,category",
    [
        ("192.0.2.10", "ipv4"),
        ("2001:db8::10", "ipv6"),
        ("operator@example.test", "email"),
        ("/etc/bind/named.conf", "absolute-path"),
        ("A1" * 32, "key-or-digest"),
    ],
)
def test_privacy_scan_blocks_sensitive_categories(secret: str, category: str) -> None:
    assert category in privacy_findings(f"diagnostic: {secret}")


def _warning_report() -> DoctorReport:
    return DoctorReport(
        generated_at="2026-09-28T12:00:00+00:00",
        status="WARN",
        zonectl_version="4.18.0",
        bind_version="9.20.11",
        package_version="4.18.0-1",
        checks=(
            DoctorCheck(
                "storage.backup",
                "WARN",
                "mało dostępnego miejsca",
                "zwolnij miejsce przed operacją zapisu",
            ),
        ),
    )


def test_prepared_issue_contains_no_environment_details() -> None:
    prepared = prepare_issue(_warning_report())

    assert prepared.url.startswith(
        "https://github.com/wojciechlipinski-pl/zonectl/issues/new?"
    )
    assert "storage.backup" in prepared.body
    assert not privacy_findings(prepared.title + prepared.body)


def test_long_issue_uses_template_link_and_keeps_body_in_private_report() -> None:
    checks = tuple(
        DoctorCheck(f"check.{index}", "WARN", "generic warning", "review state")
        for index in range(100)
    )
    report = DoctorReport(
        generated_at="2026-09-28T12:00:00+00:00",
        status="WARN",
        zonectl_version="4.18.0",
        bind_version="9.20.11",
        package_version="4.18.0-1",
        checks=checks,
    )

    prepared = prepare_issue(report)

    assert not prepared.body_in_url
    assert "template=doctor.yml" in prepared.url
    assert len(prepared.url) < 500
    assert "check.99" in prepared.body


def test_report_is_atomic_private_and_rejects_unsafe_payload(tmp_path: Path) -> None:
    path = write_public_report(_warning_report(), tmp_path / "reports")
    assert path.is_file()
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700

    unsafe = DoctorReport(
        generated_at="2026-09-28T12:00:00+00:00",
        status="WARN",
        zonectl_version="4.18.0",
        bind_version=None,
        package_version=None,
        checks=(DoctorCheck("unsafe", "WARN", "host 192.0.2.10"),),
    )
    with pytest.raises(ValueError, match="niedozwolone dane"):
        issue_body(unsafe)


def test_report_directory_must_not_be_a_symlink(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "reports"
    link.symlink_to(real, target_is_directory=True)

    with pytest.raises(OSError, match="dowiązaniem symbolicznym"):
        write_public_report(_warning_report(), link)


def test_submit_requires_confirmation_and_existing_gh_authentication() -> None:
    prepared = prepare_issue(_warning_report())
    with pytest.raises(ValueError, match="WYŚLIJ"):
        submit_issue(prepared, confirmation="TAK", which=lambda name: "/usr/bin/gh")

    calls: list[list[str]] = []

    def runner(command: list[str] | tuple[str, ...], timeout: int) -> SimpleNamespace:
        del timeout
        calls.append(list(command))
        if list(command)[:3] == ["gh", "auth", "status"]:
            return _result()
        return _result(stdout="https://github.com/example/project/issues/7\n")

    url = submit_issue(
        prepared,
        repository="example/project",
        confirmation="WYŚLIJ",
        command_runner=runner,
        which=lambda name: "/usr/bin/gh",
    )
    assert url.endswith("/issues/7")
    assert calls[-1][:3] == ["gh", "issue", "create"]
    assert "--body" in calls[-1]


def test_submit_does_not_read_tokens_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GH_TOKEN", "should-not-be-read")
    prepared = prepare_issue(_warning_report())
    seen: list[list[str]] = []

    def runner(command: list[str] | tuple[str, ...], timeout: int) -> SimpleNamespace:
        del timeout
        seen.append(list(command))
        if list(command)[:3] == ["gh", "auth", "status"]:
            return _result(1)
        return _result()

    with pytest.raises(RuntimeError, match="uwierzytelniony"):
        submit_issue(
            prepared,
            confirmation="WYŚLIJ",
            command_runner=runner,
            which=lambda name: "/usr/bin/gh",
        )
    assert all("should-not-be-read" not in " ".join(command) for command in seen)
    assert os.environ["GH_TOKEN"] == "should-not-be-read"
