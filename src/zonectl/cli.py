from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core.bind import BindService
from .core.config import DEFAULT_CONFIG, DEFAULT_GROUPS, DEFAULT_ZONES, ToolkitConfig
from .core.transaction import TransactionEngine, TransactionResult
from .presentation import transaction_exit_code, transaction_lines
from .ui.curses_app import CursesApp


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="zctl",
        description=f"ZoneCTL {__version__} — Transactional DNS Management Toolkit",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--zones", type=Path, default=DEFAULT_ZONES)
    p.add_argument("--groups", type=Path, default=DEFAULT_GROUPS)
    sub = p.add_subparsers(dest="command")
    sub.add_parser("tui", help="uruchom interfejs terminalowy")
    domains = sub.add_parser("domains", help="wyświetl listę domen")
    domains.add_argument("--grouped", action="store_true", help="pokaż domeny w grupach")
    sub.add_parser("groups", help="wyświetl przypisanie domen do grup")

    tx = sub.add_parser("transaction", aliases=["tx"], help="bezpieczne transakcje na plikach stref")
    txsub = tx.add_subparsers(dest="tx_command", required=True)
    check = txsub.add_parser("check", help="sprawdź aktywny lub wskazany plik strefy")
    check.add_argument("zone")
    check.add_argument("--source", type=Path)
    check.add_argument("--json", action="store_true")
    apply = txsub.add_parser("apply", help="zwaliduj i atomowo podmień plik strefy")
    apply.add_argument("zone")
    apply.add_argument("--source", type=Path, required=True)
    apply.add_argument("--commit", action="store_true", help="wykonaj zmianę; bez tej opcji działa dry-run")
    apply.add_argument("--json", action="store_true")

    verify = txsub.add_parser("verify", help="zweryfikuj aktualnie załadowaną strefę")
    verify.add_argument("zone")
    verify.add_argument("--json", action="store_true")

    rollback = txsub.add_parser("rollback", help="przywróć wskazany backup")
    rollback.add_argument("zone")
    rollback.add_argument("--backup", type=Path, required=True)
    rollback.add_argument("--commit", action="store_true")
    rollback.add_argument("--json", action="store_true")
    backups = txsub.add_parser("backups", help="pokaż backupy strefy")
    backups.add_argument("zone")
    backups.add_argument("--limit", type=int, default=20)
    history = txsub.add_parser("history", help="pokaż historię transakcji")
    history.add_argument("zone", nargs="?")
    history.add_argument("--limit", type=int, default=50)
    history.add_argument("--json", action="store_true")
    history.add_argument(
        "--events",
        action="store_true",
        help="pokaż surowe zdarzenia audytowe zamiast manifestów",
    )
    show = txsub.add_parser(
        "show",
        help="pokaż pełny wynik wskazanej transakcji",
    )
    show.add_argument("transaction_id")
    show.add_argument("--json", action="store_true")

    legacy = sub.add_parser("legacy", help="uruchom zgodne polecenie silnika 2.2.0")
    legacy.add_argument("arguments", nargs=argparse.REMAINDER)
    return p


def legacy_main(arguments: list[str]) -> int:
    from . import legacy_v220
    old_argv = sys.argv
    try:
        sys.argv = ["zctl"] + arguments
        return int(legacy_v220.main() or 0)
    finally:
        sys.argv = old_argv


def grouped_lines(config: ToolkitConfig, zones):
    groups: dict[str, list[str]] = {}
    for zone in zones:
        groups.setdefault(zone.group, []).append(zone.name)
    ordered = [g for g in config.group_order if g in groups]
    ordered += sorted((g for g in groups if g not in ordered and g != "Pozostałe"), key=str.casefold)
    if "Pozostałe" in groups:
        ordered.append("Pozostałe")
    for group in ordered:
        yield f"[{group}]"
        for name in sorted(groups[group], key=str.casefold):
            yield f"  {name}"


def print_transaction(result: TransactionResult, as_json: bool = False) -> int:
    if as_json:
        from dataclasses import asdict
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    else:
        print("\n".join(transaction_lines(result)))

    return transaction_exit_code(result)


def transaction_main(args, config: ToolkitConfig) -> int:
    engine = TransactionEngine(config)
    try:
        if args.tx_command == "check":
            return print_transaction(engine.validate(args.zone, args.source), args.json)
        if args.tx_command == "apply":
            return print_transaction(engine.apply(args.zone, args.source, args.commit), args.json)
        if args.tx_command == "verify":
            return print_transaction(engine.verify(args.zone), args.json)
        if args.tx_command == "rollback":
            return print_transaction(engine.rollback(args.zone, args.backup, args.commit), args.json)
        if args.tx_command == "backups":
            for path in engine.backups(args.zone, max(1, args.limit)):
                print(path)
            return 0
        if args.tx_command == "history":
            if args.events:
                records = engine.audit.read(
                    args.zone,
                    max(1, args.limit),
                )
            else:
                records = engine.history(
                    args.zone,
                    max(1, args.limit),
                )

            if args.json:
                print(
                    json.dumps(
                        records,
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                for record in records:
                    if args.events:
                        print(
                            f"{record.get('timestamp', '-')}"
                            f"  {record.get('zone', '-'):<30}"
                            f" {record.get('outcome', '-'):<16}"
                            f" {record.get('action', '-')}"
                            f"  user={record.get('user', '-')}"
                        )
                    else:
                        print(
                            f"{record.get('saved_at', '-')}"
                            f"  {record.get('zone', '-'):<30}"
                            f" {record.get('outcome', record.get('status', '-')):<16}"
                            f" {record.get('transaction_id', '-')}"
                        )
            return 0
        if args.tx_command == "show":
            return print_transaction(
                engine.load_transaction(args.transaction_id),
                args.json,
            )
    except (RuntimeError, OSError) as exc:
        print(f"BŁĄD: {exc}", file=sys.stderr)
        return 2
    return 2


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "legacy":
        return legacy_main(args.arguments)
    try:
        config = ToolkitConfig(args.config, args.zones, args.groups).load()
    except RuntimeError as exc:
        print(f"BŁĄD: {exc}", file=sys.stderr)
        return 2
    if args.command in {"transaction", "tx"}:
        return transaction_main(args, config)
    zones = config.zones()
    if args.command == "domains":
        if args.grouped:
            print("\n".join(grouped_lines(config, zones)))
        else:
            for zone in zones:
                print(zone.name)
        return 0
    if args.command == "groups":
        print("\n".join(grouped_lines(config, zones)))
        return 0
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("BŁĄD: TUI wymaga interaktywnego terminala. Użyj: zctl domains", file=sys.stderr)
        return 2
    CursesApp(
        zones,
        BindService(config),
        config.group_order,
        config=config,
    ).run()
    return 0


def deprecated_main(argv: list[str] | None = None) -> int:
    print(
        "UWAGA: polecenie 'elkman-dns' jest przestarzałe; użyj 'zctl'.",
        file=sys.stderr,
    )
    return main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
