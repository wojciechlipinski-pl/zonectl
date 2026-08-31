import curses

from zonectl.core.zone_parser import DNSRecord
from zonectl.ui.records.new_record import NewRecordDialog


class FakeWindow:
    def __init__(self, keys: list[int]):
        self.keys = list(keys)
        self.timeouts: list[int] = []

    def getch(self) -> int:
        if not self.keys:
            return -1
        return self.keys.pop(0)

    def timeout(self, value: int) -> None:
        self.timeouts.append(value)


def record(
    owner: str,
    ttl: int | None,
    rtype: str,
    rdata: str,
) -> DNSRecord:
    return DNSRecord(
        owner=owner,
        ttl=ttl,
        rrclass="IN",
        rtype=rtype,
        rdata=rdata,
        raw="",
    )


def test_default_ttl_uses_apex_soa() -> None:
    records = [
        record(
            "www.example.pl.",
            300,
            "A",
            "192.0.2.1",
        ),
        record(
            "example.pl.",
            7200,
            "SOA",
            "ns.example.pl. hostmaster.example.pl. 1 3600 900 1209600 300",
        ),
    ]

    assert (
        NewRecordDialog.default_ttl(
            "example.pl",
            records,
        )
        == 7200
    )


def test_default_ttl_falls_back_to_first_record() -> None:
    records = [
        record(
            "www.example.pl.",
            600,
            "A",
            "192.0.2.1",
        ),
    ]

    assert (
        NewRecordDialog.default_ttl(
            "example.pl",
            records,
        )
        == 600
    )


def test_default_ttl_falls_back_to_3600() -> None:
    assert (
        NewRecordDialog.default_ttl(
            "example.pl",
            [],
        )
        == 3600
    )


def test_build_record_expands_relative_owner() -> None:
    result, error = NewRecordDialog.build_record(
        zone_name="example.pl",
        owner="www",
        rtype="A",
        ttl_text="3600",
        rdata="192.0.2.15",
    )

    assert error == ""
    assert result is not None
    assert result.owner == "www.example.pl."
    assert result.ttl == 3600
    assert result.rrclass == "IN"
    assert result.rtype == "A"
    assert result.rdata == "192.0.2.15"
    assert result.raw == "www.example.pl. 3600 IN A 192.0.2.15"


def test_build_record_accepts_zone_apex() -> None:
    result, error = NewRecordDialog.build_record(
        zone_name="example.pl",
        owner="@",
        rtype="TXT",
        ttl_text="3600",
        rdata='"verification=test"',
    )

    assert error == ""
    assert result is not None
    assert result.owner == "example.pl."


def test_build_record_accepts_inherited_ttl() -> None:
    result, error = NewRecordDialog.build_record(
        zone_name="example.pl",
        owner="www2",
        rtype="CNAME",
        ttl_text="",
        rdata="@",
    )

    assert error == ""
    assert result is not None
    assert result.ttl is None
    assert result.raw == "www2.example.pl. IN CNAME @"


def test_new_record_dialog_decodes_putty_linux_f2() -> None:
    window = FakeWindow([27, *b"[[B"])

    assert NewRecordDialog._get_key(window) == curses.KEY_F2


def test_new_record_dialog_decodes_xterm_f2() -> None:
    for sequence in (b"OQ", b"[12~"):
        window = FakeWindow([27, *sequence])

        assert NewRecordDialog._get_key(window) == curses.KEY_F2


def test_build_record_rejects_invalid_ipv4() -> None:
    result, error = NewRecordDialog.build_record(
        zone_name="example.pl",
        owner="www",
        rtype="A",
        ttl_text="3600",
        rdata="999.999.999.999",
    )

    assert result is None
    assert "IPv4" in error


def test_build_record_rejects_unknown_type() -> None:
    result, error = NewRecordDialog.build_record(
        zone_name="example.pl",
        owner="www",
        rtype="UNKNOWN",
        ttl_text="3600",
        rdata="value",
    )

    assert result is None
    assert "nieobsługiwany" in error.lower()
