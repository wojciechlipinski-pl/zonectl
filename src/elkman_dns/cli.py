from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core.bind import BindService
from .core.config import DEFAULT_CONFIG, DEFAULT_GROUPS, DEFAULT_ZONES, ToolkitConfig
from .core.transaction import TransactionEngine, TransactionResult
from .ui.curses_app import CursesApp


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="elkman-dns", description=f"elkman DNS Toolkit {__version__}")
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

    legacy = sub.add_parser("legacy", help="uruchom zgodne polecenie silnika 2.2.0")
    legacy.add_argument("arguments", nargs=argparse.REMAINDER)
    return p


def legacy_main(arguments: list[str]) -> int:
    from . import legacy_v220
    old_argv = sys.argv
    try:
        sys.argv = ["elkman-dns"] + arguments
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
        print(f"Transakcja: {result.transaction_id}")
        print(f"Strefa:     {result.zone}")
        print(f"Status:     {result.status}")
        print(f"Commit:     {'TAK' if result.committed else 'NIE'}")
        print(f"Rollback:   {'TAK' if result.rolled_back else 'NIE'}")
        if result.backup:
            print(f"Backup:     {result.backup}")
        print()
        for step in result.steps:
            mark = "OK" if step.ok else "BŁĄD"
            print(f"[{mark:<4}] {step.name}: {step.message}")
            if not step.ok:
                if step.stdout.strip():
                    print("  stdout:", step.stdout.strip())
                if step.stderr.strip():
                    print("  stderr:", step.stderr.strip())
    failed = any(not s.ok for s in result.steps)
    return 1 if failed else 0


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
            events = engine.audit.read(args.zone, max(1, args.limit))
            if args.json:
                print(json.dumps(events, ensure_ascii=False, indent=2))
            else:
                for event in events:
                    print(f"{event.get('timestamp','-')}  {event.get('zone','-'):<30} {event.get('outcome','-'):<16} {event.get('action','-')}  user={event.get('user','-')}")
            return 0
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
        print("BŁĄD: TUI wymaga interaktywnego terminala. Użyj: elkman-dns domains", file=sys.stderr)
        return 2
    CursesApp(
        zones,
        BindService(config),
        config.group_order,
        config=config,
    ).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
