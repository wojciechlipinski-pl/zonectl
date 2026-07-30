from zonectl.core.zone_model import ChangeKind, ZoneModel
from zonectl.core.zone_parser import DNSRecord


def test_add_record_creates_pending_add_change() -> None:
    model = ZoneModel("example.pl", [])

    record = DNSRecord(
        owner="www.example.pl.",
        ttl=300,
        rrclass="IN",
        rtype="A",
        rdata="192.0.2.10",
        raw="",
    )

    index = model.add(record)

    assert index == 0
    assert model.records == (record,)
    assert model.change_count == 1
    assert model.dirty is True

    change = model.pending_changes[0]

    assert change.kind is ChangeKind.ADD
    assert change.before is None
    assert change.after == record
