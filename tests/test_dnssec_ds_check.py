from __future__ import annotations

from zonectl.core.dnssec_ds_check import DnssecDsChecker
from zonectl.core.dnssec_report import dnskey_to_ds
from zonectl.core.runner import CommandResult


DNSKEY = "257 3 13 YWJjZA=="
ZONE = "example.pl"
EXPECTED_DS = dnskey_to_ds(ZONE, DNSKEY)


def runner_for(*, ds_by_server: dict[str, str], kasp_ready: bool = True):
    def runner(command: list[str], timeout: int) -> CommandResult:
        if command[:3] == ["rndc", "dnssec", "-status"]:
            state = "omnipresent" if kasp_ready else "rumoured"
            return CommandResult(
                0,
                f"- dnskey: {state}\n- zone rrsig: {state}\n"
                f"- key rrsig: {state}\n",
                "",
            )
        server = command[1][1:]
        rtype = command[3]
        if rtype == "NS":
            return CommandResult(
                0,
                f"{ZONE}. 3600 IN NS ns1.example.pl.\n"
                f"{ZONE}. 3600 IN NS ns2.example.pl.\n",
                "",
            )
        if rtype == "DS":
            value = ds_by_server.get(server, "")
            output = f"{ZONE}. 3600 IN DS {value}\n" if value else ""
            return CommandResult(0, output, "")
        if rtype == "DNSKEY":
            comments = ";; flags: qr aa; QUERY: 1, ANSWER: 2\n"
            answer = (
                f"{ZONE}. 3600 IN DNSKEY {DNSKEY}\n"
                f"{ZONE}. 3600 IN RRSIG DNSKEY 13 2 signature\n"
            )
            return CommandResult(0, comments + answer, "")
        raise AssertionError(command)

    return runner


def test_all_resolvers_and_authorities_pass() -> None:
    checker = DnssecDsChecker(
        command_runner=runner_for(ds_by_server={"r1": EXPECTED_DS, "r2": EXPECTED_DS})
    )

    result = checker.collect(ZONE, ("r1", "r2"))

    assert result.status == "PASS"
    assert result.kasp_ready is True
    assert [check.status for check in result.resolver_checks] == ["MATCH", "MATCH"]
    assert [check.status for check in result.authority_checks] == ["MATCH", "MATCH"]


def test_partial_ds_visibility_is_propagating() -> None:
    checker = DnssecDsChecker(
        command_runner=runner_for(ds_by_server={"r1": EXPECTED_DS})
    )

    result = checker.collect(ZONE, ("r1", "r2"))

    assert result.status == "PROPAGATING"
    assert result.errors == ()


def test_missing_ds_before_kasp_readiness_is_blocked() -> None:
    checker = DnssecDsChecker(
        command_runner=runner_for(ds_by_server={}, kasp_ready=False)
    )

    result = checker.collect(ZONE, ("r1", "r2"))

    assert result.status == "NOT_READY"
    assert "Nie publikuj DS" in result.next_action


def test_wrong_ds_is_failure() -> None:
    checker = DnssecDsChecker(
        command_runner=runner_for(ds_by_server={"r1": "1 13 2 BAD"})
    )

    result = checker.collect(ZONE, ("r1",))

    assert result.status == "FAIL"
    assert result.errors


def test_non_authoritative_server_is_failure() -> None:
    base = runner_for(ds_by_server={"r1": EXPECTED_DS})

    def runner(command: list[str], timeout: int) -> CommandResult:
        result = base(command, timeout)
        if command[1] == "@ns2.example.pl" and command[3] == "DNSKEY":
            return CommandResult(0, result.stdout.replace("qr aa", "qr"), "")
        return result

    result = DnssecDsChecker(command_runner=runner).collect(ZONE, ("r1",))

    assert result.status == "FAIL"
    assert result.authority_checks[1].status == "NOT-AUTH"


def test_unavailable_resolver_is_indeterminate() -> None:
    base = runner_for(ds_by_server={})

    def runner(command: list[str], timeout: int) -> CommandResult:
        if command[:1] == ["dig"] and command[1] == "@r1" and command[3] == "DS":
            return CommandResult(9, "", "timeout")
        return base(command, timeout)

    result = DnssecDsChecker(command_runner=runner).collect(ZONE, ("r1",))

    assert result.status == "INDETERMINATE"
    assert "nie zmieniaj DS" in result.next_action
