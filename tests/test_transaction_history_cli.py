from zonectl.cli import parser


def test_history_parser_supports_raw_audit_events() -> None:
    args = parser().parse_args(
        ["tx", "history", "example.pl", "--events", "--limit", "10"]
    )

    assert args.command == "tx"
    assert args.tx_command == "history"
    assert args.zone == "example.pl"
    assert args.events is True
    assert args.limit == 10


def test_show_parser_accepts_transaction_identifier() -> None:
    args = parser().parse_args(
        ["tx", "show", "20260730-170000-example.pl-abcd1234"]
    )

    assert args.command == "tx"
    assert args.tx_command == "show"
    assert (
        args.transaction_id
        == "20260730-170000-example.pl-abcd1234"
    )
