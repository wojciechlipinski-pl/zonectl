from zonectl.core.zone_model import ChangeKind, ZoneModel
from zonectl.core.zone_parser import DNSRecord
from zonectl.ui.records.controller import RecordController


def make_record(
    owner: str,
    rtype: str = "A",
    ttl: int | None = 3600,
    rdata: str = "192.0.2.1",
) -> DNSRecord:
    return DNSRecord(
        owner=owner,
        ttl=ttl,
        rrclass="IN",
        rtype=rtype,
        rdata=rdata,
        raw="",
    )


def make_controller() -> RecordController:
    model = ZoneModel(
        "example.pl",
        [
            make_record(
                "www.example.pl.",
                ttl=7200,
                rdata="192.0.2.20",
            ),
            make_record(
                "example.pl.",
                rtype="MX",
                ttl=3600,
                rdata="10 mail.example.pl.",
            ),
            make_record(
                "api.example.pl.",
                ttl=300,
                rdata="192.0.2.10",
            ),
        ],
    )

    return RecordController(
        model,
        "example.pl",
    )


def test_default_sort_uses_owner_name() -> None:
    controller = make_controller()

    owners = [
        view.record.relative_owner("example.pl")
        for view in controller.ordered_views()
    ]

    assert owners == ["@", "api", "www"]


def test_sort_by_type() -> None:
    controller = make_controller()
    controller.cycle_sort()

    types = [
        view.record.rtype
        for view in controller.ordered_views()
    ]

    assert types == ["A", "A", "MX"]


def test_sort_by_ttl() -> None:
    controller = make_controller()
    controller.cycle_sort()
    controller.cycle_sort()

    ttls = [
        view.record.ttl
        for view in controller.ordered_views()
    ]

    assert ttls == [300, 3600, 7200]


def test_search_matches_owner_type_ttl_and_value() -> None:
    controller = make_controller()

    controller.set_search("mail.example")
    results = controller.ordered_views()

    assert len(results) == 1
    assert results[0].record.rtype == "MX"

    controller.set_search("7200")
    results = controller.ordered_views()

    assert len(results) == 1
    assert results[0].record.relative_owner("example.pl") == "www"


def test_search_includes_change_marker() -> None:
    controller = make_controller()
    view = controller.model.record_views[0]

    controller.model.replace_by_identifier(
        view.identifier,
        make_record(
            "www.example.pl.",
            ttl=7200,
            rdata="192.0.2.99",
        ),
    )

    controller.set_search("~")
    results = controller.ordered_views()

    assert len(results) == 1
    assert results[0].change_kind is ChangeKind.MODIFY


def test_deleted_records_remain_in_ordered_views() -> None:
    controller = make_controller()
    identifier = controller.model.record_views[0].identifier

    controller.model.delete_by_identifier(identifier)
    views = controller.ordered_views()

    deleted = next(
        view
        for view in views
        if view.identifier == identifier
    )

    assert deleted.deleted is True
    assert deleted.marker == "-"


def test_selection_is_clamped_after_list_shrinks() -> None:
    controller = make_controller()
    views = controller.ordered_views()

    controller.selected = 2
    controller.offset = 2

    controller.set_search("api")
    views = controller.ordered_views()
    controller.clamp_selection(
        views,
        visible_rows=10,
    )

    assert controller.selected == 0
    assert controller.offset == 0


def test_select_identifier_finds_record_after_sorting() -> None:
    controller = make_controller()
    identifier = controller.model.record_views[0].identifier

    controller.cycle_sort()
    views = controller.ordered_views()

    assert controller.select_identifier(
        views,
        identifier,
    )
    assert views[controller.selected].identifier == identifier
