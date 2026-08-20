from zonectl.core.bind_secondary_health import (
    BindSecondaryHealthGate,
    SecondarySoaObservation,
)
from zonectl.core.runner import CommandResult


def _query(values):
    def query(server: str, zone: str):
        authoritative, serial = values[server]
        return SecondarySoaObservation(
            server, authoritative, serial, f"{zone}: {serial}"
        )
    return query


def test_matching_authoritative_serial_is_pass() -> None:
    gate = BindSecondaryHealthGate(query=_query({
        "127.0.0.1": (True, 2026082001),
        "192.0.2.53": (True, 2026082001),
    }), attempts=1)

    report = gate.check(("example.test",), ("192.0.2.53",))[0]

    assert report.status == "PASS"


def test_missing_aa_is_failure() -> None:
    gate = BindSecondaryHealthGate(query=_query({
        "127.0.0.1": (True, 2026082001),
        "192.0.2.53": (False, 2026082001),
    }), attempts=1)

    report = gate.check(("example.test",), ("192.0.2.53",))[0]

    assert report.status == "FAIL"
    assert "autorytatywnego" in report.message


def test_lower_secondary_serial_is_pending_not_failure() -> None:
    gate = BindSecondaryHealthGate(query=_query({
        "127.0.0.1": (True, 2026082002),
        "192.0.2.53": (True, 2026082001),
    }), attempts=1)

    report = gate.check(("example.test",), ("192.0.2.53",))[0]

    assert report.status == "PENDING"


def test_secondary_serial_ahead_of_primary_is_failure() -> None:
    gate = BindSecondaryHealthGate(query=_query({
        "127.0.0.1": (True, 2026082001),
        "192.0.2.53": (True, 2026082002),
    }), attempts=1)

    report = gate.check(("example.test",), ("192.0.2.53",))[0]

    assert report.status == "FAIL"
    assert "wyższy" in report.message


def test_dig_output_parser_reads_aa_and_soa_serial(monkeypatch) -> None:
    monkeypatch.setattr(
        "zonectl.core.bind_secondary_health.run",
        lambda command, timeout: CommandResult(
            0,
            ";; flags: qr aa; QUERY: 1, ANSWER: 1\n"
            "example.test. 3600 IN SOA ns1.example.test. "
            "hostmaster.example.test. 2026082003 3600 900 1209600 3600\n",
            "",
        ),
    )

    observation = BindSecondaryHealthGate._query_soa(
        "192.0.2.53", "example.test"
    )

    assert observation.authoritative is True
    assert observation.serial == 2026082003
