from __future__ import annotations

import json
from pathlib import Path

from zonectl import cli
from zonectl.core.doctor import DoctorCheck, DoctorReport, PreparedIssue


REPORT = DoctorReport(
    generated_at="2026-09-28T12:00:00+00:00",
    status="WARN",
    zonectl_version="4.18.0",
    bind_version="9.20.11",
    package_version="4.18.0-1",
    checks=(DoctorCheck("rpz.timer", "WARN", "timer RPZ nie jest aktywny"),),
)


class FakeDoctor:
    def __init__(self, **kwargs: object) -> None:
        del kwargs

    def collect(self) -> DoctorReport:
        return REPORT


def test_doctor_runs_before_toolkit_configuration_is_loaded(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(cli, "Doctor", FakeDoctor)
    monkeypatch.setattr(
        cli.ToolkitConfig,
        "load",
        lambda self: (_ for _ in ()).throw(AssertionError("must not load config")),
    )

    code = cli.main(["doctor", "--json"])

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "zonectl.doctor/v1"
    assert payload["status"] == "WARN"


def test_submit_requires_prepare_issue(capsys) -> None:
    assert cli.main(["doctor", "--submit-github"]) == 2
    assert "--prepare-issue" in capsys.readouterr().err


def test_json_cannot_be_mixed_with_human_issue_workflow(capsys) -> None:
    assert cli.main(["doctor", "--json", "--prepare-issue"]) == 2
    assert "--json" in capsys.readouterr().err


def test_prepare_issue_prints_copyable_link_without_sending(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(cli, "Doctor", FakeDoctor)
    target = tmp_path / "report.md"
    monkeypatch.setattr(cli, "write_public_report", lambda report, directory: target)
    monkeypatch.setattr(
        cli,
        "prepare_issue",
        lambda report, repository, report_path: PreparedIssue(
            title="doctor",
            body="safe body",
            url="https://github.com/example/project/issues/new?title=doctor",
            report_path=report_path,
        ),
    )
    sent = False

    def fail_submit(*args: object, **kwargs: object) -> str:
        nonlocal sent
        sent = True
        raise AssertionError("must not submit")

    monkeypatch.setattr(cli, "submit_issue", fail_submit)

    code = cli.main(
        [
            "doctor",
            "--prepare-issue",
            "--repository",
            "example/project",
            "--report-directory",
            str(tmp_path),
        ]
    )

    output = capsys.readouterr().out
    assert code == 1
    assert not sent
    assert "NIE ZOSTAŁO JESZCZE WYSŁANE" in output
    assert "https://github.com/example/project/issues/new" in output


def test_submit_prints_body_then_uses_explicit_confirmation(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(cli, "Doctor", FakeDoctor)
    monkeypatch.setattr(
        cli, "write_public_report", lambda report, directory: tmp_path / "report.md"
    )
    prepared = PreparedIssue(
        title="doctor",
        body="public preview",
        url="https://github.com/example/project/issues/new",
    )
    monkeypatch.setattr(cli, "prepare_issue", lambda *args, **kwargs: prepared)
    received: dict[str, str] = {}

    def submit(prepared: PreparedIssue, *, repository: str, confirmation: str) -> str:
        received.update(repository=repository, confirmation=confirmation)
        return "https://github.com/example/project/issues/8"

    monkeypatch.setattr(cli, "submit_issue", submit)

    code = cli.main(
        [
            "doctor",
            "--prepare-issue",
            "--submit-github",
            "--confirm-public",
            "WYŚLIJ",
            "--repository",
            "example/project",
            "--report-directory",
            str(tmp_path),
        ]
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "public preview" in output
    assert output.index("public preview") < output.index("issues/8")
    assert received == {"repository": "example/project", "confirmation": "WYŚLIJ"}
