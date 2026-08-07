from __future__ import annotations

import subprocess

from zonectl.core.dnssec_withdrawal_check import DnssecWithdrawalChecker


def fake_dig_runner(responses: dict[str, str]):
    def _runner(args):
        resolver = args[4].lstrip("@")
        stdout = responses.get(resolver, "")
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

    return _runner


def test_ready_for_withdrawn_when_ds_absent_everywhere() -> None:
    checker = DnssecWithdrawalChecker(
        dig_runner=fake_dig_runner({"1.1.1.1": "", "8.8.8.8": ""})
    )

    result = checker.collect("example.pl", ("1.1.1.1", "8.8.8.8"))

    assert result.status == "READY_FOR_WITHDRAWN"
    assert all(check.status == "DS_ABSENT" for check in result.resolver_checks)
    assert not result.errors


def test_blocked_when_any_resolver_still_sees_ds() -> None:
    checker = DnssecWithdrawalChecker(
        dig_runner=fake_dig_runner(
            {
                "1.1.1.1": "",
                "8.8.8.8": "example.pl.\t3600\tIN\tDS\t12345 13 2 ABCDEF",
            }
        )
    )

    result = checker.collect("example.pl", ("1.1.1.1", "8.8.8.8"))

    assert result.status == "BLOCKED"
    present = [c for c in result.resolver_checks if c.status == "DS_PRESENT"]
    assert [c.resolver for c in present] == ["8.8.8.8"]
    assert "8.8.8.8" in result.next_action
    assert "withdrawn" in result.next_action


def test_rrsig_covering_ds_does_not_count_as_ds_present() -> None:
    checker = DnssecWithdrawalChecker(
        dig_runner=fake_dig_runner(
            {
                "1.1.1.1": (
                    "example.pl.\t3600\tIN\tRRSIG\t"
                    "DS 13 2 3600 20260901000000 20260801000000 12345 example.pl. AbCd=="
                ),
            }
        )
    )

    result = checker.collect("example.pl", ("1.1.1.1",))

    assert result.status == "READY_FOR_WITHDRAWN"
    assert result.resolver_checks[0].status == "DS_ABSENT"


def test_error_status_when_dig_times_out() -> None:
    def failing_runner(args):
        raise subprocess.TimeoutExpired(cmd=args, timeout=3)

    checker = DnssecWithdrawalChecker(dig_runner=failing_runner)

    result = checker.collect("example.pl", ("1.1.1.1",))

    assert result.status == "ERROR"
    assert result.errors
    assert result.resolver_checks[0].status == "ERROR"


def test_error_takes_priority_even_if_other_resolver_is_clean() -> None:
    def mixed_runner(args):
        resolver = args[4].lstrip("@")
        if resolver == "9.9.9.9":
            raise subprocess.TimeoutExpired(cmd=args, timeout=3)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    checker = DnssecWithdrawalChecker(dig_runner=mixed_runner)

    result = checker.collect("example.pl", ("1.1.1.1", "9.9.9.9"))

    assert result.status == "ERROR"
