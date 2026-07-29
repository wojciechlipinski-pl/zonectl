from elkman_dns.core.zone_document import RecordNode
from elkman_dns.core.zone_document_adapter import (
    ZoneDocumentAdapter,
    ZoneDocumentAdapterError,
)
from elkman_dns.core.zone_file_parser import ZoneFileParser
from elkman_dns.core.zone_model import ChangeKind, ZoneModel
from elkman_dns.core.zone_parser import DNSRecord
from elkman_dns.core.zone_writer import ZoneWriter


def make_record(
    owner: str,
    address: str,
) -> DNSRecord:
    return DNSRecord(
        owner=owner,
        ttl=300,
        rrclass="IN",
        rtype="A",
        rdata=address,
        raw=f"{owner} 300 IN A {address}",
    )


def test_unchanged_model_preserves_document() -> None:
    original = (
        "$TTL 3600\n"
        "\n"
        "www 300 IN A 192.0.2.10\n"
        "mail 300 IN A 192.0.2.20\n"
    )

    document = ZoneFileParser.parse_text(original)
    model = ZoneModel("example.pl", document.records)
    adapter = ZoneDocumentAdapter(document, model)

    adapter.apply()

    assert ZoneWriter().render_document(document) == original


def test_modified_record_updates_only_bound_node() -> None:
    original = (
        "$TTL 3600\n"
        "\n"
        "www     300 IN A 192.0.2.10\n"
        "mail    300 IN A 192.0.2.20\n"
    )

    document = ZoneFileParser.parse_text(original)
    model = ZoneModel("example.pl", document.records)
    adapter = ZoneDocumentAdapter(document, model)

    first_view = model.record_views[0]

    model.replace_by_identifier(
        first_view.identifier,
        make_record("www", "192.0.2.100"),
    )

    adapter.apply()

    nodes = list(document.iter_record_nodes())

    assert nodes[0].modified is True
    assert nodes[0].record.rdata == "192.0.2.100"

    assert nodes[1].modified is False
    assert nodes[1].raw == "mail    300 IN A 192.0.2.20"

    assert ZoneWriter().render_document(document) == (
        "$TTL 3600\n"
        "\n"
        "www\t300\tIN\tA\t192.0.2.100\n"
        "mail    300 IN A 192.0.2.20\n"
    )


def test_deleted_record_is_marked_deleted() -> None:
    document = ZoneFileParser.parse_text(
        "www 300 IN A 192.0.2.10\n"
        "old 300 IN A 192.0.2.20\n"
        "mail 300 IN A 192.0.2.30\n"
    )

    model = ZoneModel("example.pl", document.records)
    adapter = ZoneDocumentAdapter(document, model)

    old_view = model.record_views[1]
    model.delete_by_identifier(old_view.identifier)

    adapter.apply()

    nodes = list(document.iter_record_nodes())

    assert nodes[0].deleted is False
    assert nodes[1].deleted is True
    assert nodes[2].deleted is False

    assert ZoneWriter().render_document(document) == (
        "www 300 IN A 192.0.2.10\n"
        "mail 300 IN A 192.0.2.30\n"
    )


def test_added_record_is_appended_once() -> None:
    document = ZoneFileParser.parse_text(
        "www 300 IN A 192.0.2.10\n"
    )

    model = ZoneModel("example.pl", document.records)
    adapter = ZoneDocumentAdapter(document, model)

    model.add(
        make_record("new", "192.0.2.50")
    )

    adapter.apply()
    adapter.apply()

    nodes = list(document.iter_record_nodes())

    assert len(nodes) == 2
    assert nodes[1].record.owner == "new"
    assert nodes[1].modified is True

    assert ZoneWriter().render_document(document) == (
        "www 300 IN A 192.0.2.10\n"
        "new\t300\tIN\tA\t192.0.2.50\n"
    )


def test_add_then_delete_does_not_leave_node() -> None:
    document = ZoneFileParser.parse_text(
        "www 300 IN A 192.0.2.10\n"
    )

    model = ZoneModel("example.pl", document.records)
    adapter = ZoneDocumentAdapter(document, model)

    model.add(
        make_record("temporary", "192.0.2.60")
    )
    added_view = next(
        view
        for view in model.record_views
        if view.change_kind is ChangeKind.ADD
    )

    adapter.apply()

    model.delete_by_identifier(added_view.identifier)
    adapter.apply()

    nodes = list(document.iter_record_nodes())

    assert len(nodes) == 1
    assert nodes[0].record.owner == "www"


def test_discard_restores_document() -> None:
    original = (
        "$TTL 3600\n"
        "www 300 IN A 192.0.2.10\n"
        "mail 300 IN A 192.0.2.20\n"
    )

    document = ZoneFileParser.parse_text(original)
    model = ZoneModel("example.pl", document.records)
    adapter = ZoneDocumentAdapter(document, model)

    first = model.record_views[0]
    second = model.record_views[1]

    model.replace_by_identifier(
        first.identifier,
        make_record("www", "192.0.2.100"),
    )
    model.delete_by_identifier(second.identifier)
    model.add(
        make_record("new", "192.0.2.200")
    )

    adapter.apply()

    model.discard()
    adapter.discard()

    assert ZoneWriter().render_document(document) == original
    assert model.dirty is False


def test_duplicate_records_are_bound_by_position() -> None:
    original = (
        "same 300 IN A 192.0.2.10\n"
        "same 300 IN A 192.0.2.10\n"
    )

    document = ZoneFileParser.parse_text(original)
    model = ZoneModel("example.pl", document.records)
    adapter = ZoneDocumentAdapter(document, model)

    second = model.record_views[1]

    model.replace_by_identifier(
        second.identifier,
        make_record("same", "192.0.2.99"),
    )

    adapter.apply()

    nodes = list(document.iter_record_nodes())

    assert nodes[0].modified is False
    assert nodes[1].modified is True
    assert nodes[1].record.rdata == "192.0.2.99"


def test_record_count_mismatch_is_rejected() -> None:
    document = ZoneFileParser.parse_text(
        "www 300 IN A 192.0.2.10\n"
    )

    model = ZoneModel(
        "example.pl",
        [
            make_record("www", "192.0.2.10"),
            make_record("mail", "192.0.2.20"),
        ],
    )

    try:
        ZoneDocumentAdapter(document, model)
    except ZoneDocumentAdapterError as exc:
        assert "Liczba rekordów" in str(exc)
    else:
        raise AssertionError(
            "Oczekiwano ZoneDocumentAdapterError"
        )


def test_record_order_mismatch_is_rejected() -> None:
    document = ZoneFileParser.parse_text(
        "www 300 IN A 192.0.2.10\n"
    )

    model = ZoneModel(
        "example.pl",
        [
            make_record("other", "192.0.2.99"),
        ],
    )

    try:
        ZoneDocumentAdapter(document, model)
    except ZoneDocumentAdapterError as exc:
        assert "Kolejność" in str(exc)
    else:
        raise AssertionError(
            "Oczekiwano ZoneDocumentAdapterError"
        )
