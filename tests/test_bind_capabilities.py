from zonectl.core.bind_capabilities import BindCapabilityDetector
from zonectl.core.runner import CommandResult


def detector(result: CommandResult) -> BindCapabilityDetector:
    return BindCapabilityDetector(lambda command, timeout: result)


def test_detects_bind_920_capabilities_without_exposing_build_details() -> None:
    report = detector(
        CommandResult(
            0,
            "BIND 9.20.4-1-Debian (Stable Release) <id:private-build-id>\n",
            "",
        )
    ).detect()

    assert report.status == "PASS"
    assert report.version == "9.20.4-1-Debian"
    assert report.series == "9.20"
    assert report.dnssec_policy is True
    assert report.inline_signing_in_policy is True
    assert report.nsec3_iterations_zero_required is True
    assert "private-build-id" not in str(report.to_dict())


def test_detects_bind_918_differences() -> None:
    report = detector(
        CommandResult(0, "BIND 9.18.33 (Extended Support Version)\n", "")
    ).detect()

    assert report.status == "BLOCKED"
    assert report.findings == ("ZoneCTL wymaga BIND 9.20 lub nowszego",)
    assert report.dnssec_policy is True
    assert report.inline_signing_in_policy is False
    assert report.nsec3_iterations_zero_required is False


def test_warns_for_unverified_new_series() -> None:
    report = detector(CommandResult(0, "BIND 9.22.1\n", "")).detect()

    assert report.status == "WARN"
    assert "nie należy" in report.findings[0]


def test_blocks_bind_without_required_policy_capability() -> None:
    report = detector(CommandResult(0, "BIND 9.16.50\n", "")).detect()

    assert report.status == "BLOCKED"
    assert report.dnssec_policy is True


def test_blocks_missing_or_unparseable_named() -> None:
    missing = detector(
        CommandResult(127, "", "details containing /private/path")
    ).detect()
    invalid = detector(CommandResult(0, "unexpected output", "")).detect()

    assert missing.status == "BLOCKED"
    assert missing.findings == ("Nie znaleziono poleceń named ani named-checkconf",)
    assert "/private/path" not in str(missing.to_dict())
    assert invalid.detected is False


def test_falls_back_to_named_checkconf_when_server_is_not_installed() -> None:
    calls: list[list[str]] = []

    def run(command: list[str], timeout: int) -> CommandResult:
        calls.append(command)
        if command[0] == "named":
            return CommandResult(127, "", "not installed")
        return CommandResult(0, "9.20.26-1~deb13u1-Debian\n", "")

    report = BindCapabilityDetector(run).detect()

    assert report.status == "PASS"
    assert report.version == "9.20.26-1~deb13u1-Debian"
    assert calls == [["named", "-v"], ["named-checkconf", "-v"]]
