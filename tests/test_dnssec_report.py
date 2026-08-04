from __future__ import annotations

from pathlib import Path

from zonectl.core.dnssec_report import DnssecReporter, dnskey_to_ds
from zonectl.core.models import Zone
from zonectl.core.runner import CommandResult


DNSKEY = "257 3 13 YWJjZA=="


def test_dnskey_to_ds_is_deterministic_and_case_insensitive() -> None:
    expected = dnskey_to_ds("example.pl", DNSKEY)

    assert expected == dnskey_to_ds("EXAMPLE.PL.", DNSKEY)
    assert expected.startswith("51412 13 2 ")
    assert len(expected.split()[3]) == 64


def test_report_collects_signed_zone_state(tmp_path: Path) -> None:
    expected_ds = dnskey_to_ds("example.pl", DNSKEY)

    def runner(command: list[str], timeout: int) -> CommandResult:
        if command[:2] == ["rndc", "zonestatus"]:
            return CommandResult(0, "name: example.pl\n", "")
        if command[:3] == ["rndc", "dnssec", "-status"]:
            return CommandResult(0, "zone signing:   yes - since now\n", "")
        if "DNSKEY" in command:
            return CommandResult(
                0,
                "example.pl. 3600 IN DNSKEY " + DNSKEY + "\n"
                "example.pl. 3600 IN RRSIG DNSKEY 13 2 3600 signature\n",
                "",
            )
        if "DS" in command:
            fields = expected_ds.split()
            wrapped_ds = " ".join((*fields[:3], fields[3][:32], fields[3][32:]))
            return CommandResult(
                0,
                "example.pl. 3600 IN DS " + wrapped_ds + "\n",
                "",
            )
        raise AssertionError(command)

    (tmp_path / "Kexample.pl.+013+12345.key").write_text("key")
    (tmp_path / "Kexample.pl.+013+12345.private").write_text("private")
    zone = Zone(
        "example.pl",
        Path("/zones/example.pl"),
        dnssec_policy="default",
        inline_signing=True,
        key_directory=tmp_path,
    )

    report = DnssecReporter(command_runner=runner).collect(zone, tmp_path)

    assert report.status == "PASS"
    assert report.loaded is True
    assert report.signing is True
    assert report.dnskey_records == (DNSKEY,)
    assert len(report.rrsig_records) == 1
    assert report.calculated_ds == (expected_ds,)
    assert report.parent_ds_matches is True
    assert len(report.key_files) == 2


def test_report_warns_when_parent_ds_is_missing() -> None:
    def runner(command: list[str], timeout: int) -> CommandResult:
        if command[:2] == ["rndc", "zonestatus"]:
            return CommandResult(0, "loaded", "")
        if command[:3] == ["rndc", "dnssec", "-status"]:
            return CommandResult(0, "zone signing: yes", "")
        if "DNSKEY" in command:
            return CommandResult(
                0,
                "example.pl. 3600 IN DNSKEY " + DNSKEY + "\n"
                "example.pl. 3600 IN RRSIG DNSKEY 13 2 3600 signature\n",
                "",
            )
        return CommandResult(0, "", "")

    zone = Zone(
        "example.pl",
        Path("/zones/example.pl"),
        dnssec_policy="default",
        inline_signing=True,
    )
    report = DnssecReporter(command_runner=runner).collect(zone)

    assert report.status == "WARN"
    assert report.parent_ds_matches is False
    assert "Brak rekordu DS" in report.warnings[0]


def test_unsigned_zone_is_reported_without_failure() -> None:
    def runner(command: list[str], timeout: int) -> CommandResult:
        if command[:2] == ["rndc", "zonestatus"]:
            return CommandResult(0, "loaded", "")
        if command[:3] == ["rndc", "dnssec", "-status"]:
            return CommandResult(0, "Zone does not have dnssec-policy", "")
        return CommandResult(0, "", "")

    report = DnssecReporter(command_runner=runner).collect(
        Zone("unsigned.pl", Path("/zones/unsigned.pl"))
    )

    assert report.status == "UNSIGNED"
    assert report.configured is False
    assert report.signing is False
    assert report.parent_ds_matches is None
    assert report.dnskey_records == ()
    assert report.warnings == ()
