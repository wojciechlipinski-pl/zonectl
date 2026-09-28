from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from zonectl.core.doctor import (
    Doctor,
    DoctorCheck,
    DoctorReport,
    issue_body,
    prepare_issue,
    privacy_findings,
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
