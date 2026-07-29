from elkman_dns.core.zone_model import ChangeKind, ZoneModel
from elkman_dns.core.zone_parser import DNSRecord


def record(
    owner: str,
    address: str,
) -> DNSRecord:
    return DNSRecord(
        owner=owner,
        ttl=3600,
        rrclass="IN",
        rtype="A",
        rdata=address,
        raw="",
    )


def test_record_views_mark_unchanged_records() -> None:
    original = record("www.example.pl.", "192.0.2.10")
    model = ZoneModel("example.pl", [original])

    view = model.record_views[0]

    assert view.record == original
    assert view.change_kind is None
    assert view.marker == " "
    assert view.deleted is False


def test_record_views_mark_added_records() -> None:
    model = ZoneModel("example.pl", [])
    model.add(record("new.example.pl.", "192.0.2.20"))

    view = model.record_views[0]

    assert view.change_kind is ChangeKind.ADD
    assert view.marker == "+"


def test_record_views_mark_modified_records() -> None:
    original = record("www.example.pl.", "192.0.2.10")
    updated = record("www.example.pl.", "192.0.2.11")
    model = ZoneModel("example.pl", [original])

    identifier = model.record_views[0].identifier
    model.replace_by_identifier(identifier, updated)

    view = model.record_views[0]

    assert view.record == updated
    assert view.change_kind is ChangeKind.MODIFY
    assert view.marker == "~"


def test_record_views_keep_deleted_records_visible() -> None:
    original = record("www.example.pl.", "192.0.2.10")
    model = ZoneModel("example.pl", [original])

    identifier = model.record_views[0].identifier
    model.delete_by_identifier(identifier)

    view = model.record_views[0]

    assert view.record == original
    assert view.change_kind is ChangeKind.DELETE
    assert view.marker == "-"
    assert view.deleted is True
    assert model.records == ()


def test_deleted_record_cannot_be_deleted_twice() -> None:
    model = ZoneModel(
        "example.pl",
        [record("www.example.pl.", "192.0.2.10")],
    )
    identifier = model.record_views[0].identifier

    model.delete_by_identifier(identifier)

    try:
        model.delete_by_identifier(identifier)
    except RuntimeError as exc:
        assert "już usunięty" in str(exc)
    else:
        raise AssertionError("Oczekiwano RuntimeError")
