from elkman_dns.core.zone_model import ChangeKind, ZoneModel
from elkman_dns.core.zone_parser import DNSRecord


def make_record(
    owner: str = "www.example.pl.",
    address: str = "192.0.2.10",
) -> DNSRecord:
    return DNSRecord(
        owner=owner,
        ttl=300,
        rrclass="IN",
        rtype="A",
        rdata=address,
        raw="",
    )


def test_delete_existing_record_creates_pending_delete_change() -> None:
    record = make_record()
    model = ZoneModel("example.pl", [record])

    removed = model.delete(0)

    assert removed == record
    assert model.records == ()
    assert model.change_count == 1
    assert model.dirty is True

    change = model.pending_changes[0]

    assert change.kind is ChangeKind.DELETE
    assert change.before == record
    assert change.after is None


def test_delete_new_record_cancels_pending_add_change() -> None:
    model = ZoneModel("example.pl", [])
    record = make_record()

    index = model.add(record)
    removed = model.delete(index)

    assert removed == record
    assert model.records == ()
    assert model.pending_changes == ()
    assert model.change_count == 0
    assert model.dirty is False


def test_delete_rejects_invalid_index() -> None:
    model = ZoneModel("example.pl", [make_record()])

    try:
        model.delete(1)
    except IndexError as exc:
        assert "poza zakresem" in str(exc)
    else:
        raise AssertionError("Oczekiwano IndexError")
