from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core.bind import BindService
from .core.config import DEFAULT_CONFIG, DEFAULT_GROUPS, DEFAULT_ZONES, ToolkitConfig
from .core.transaction import TransactionEngine, TransactionResult
from .core.zone_create_transaction import ZoneCreateTransaction
from .core.zone_disable_transaction import (
    ZoneDisableError,
    ZoneDisableTransaction,
)
from .core.zone_restore_transaction import (
    ZoneRestoreError,
    ZoneRestoreTransaction,
)
from .core.zone_quarantine import (
    ZoneQuarantineError,
    ZoneQuarantineTransaction,
)
from .core.zone_quarantine_restore import (
    QuarantineRestoreError,
    QuarantineRestoreTransaction,
)
from .core.zone_lifecycle import (
    ZoneCreateRequest,
    ZoneLifecycleError,
    ZoneLifecyclePlanner,
)
from .core.zone_inventory import ZoneInventory
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

    lifecycle = sub.add_parser(
        "zone",
        help="zarządzaj cyklem życia stref DNS",
    )
    lifecycle_sub = lifecycle.add_subparsers(
        dest="zone_command",
        required=True,
    )
    create_plan = lifecycle_sub.add_parser(
        "create-plan",
        help="pokaż plan utworzenia strefy bez zmian w systemie",
    )
    create_plan.add_argument("name")
    create_plan.add_argument("--primary-ns", required=True)
    create_plan.add_argument("--admin", required=True)
    create_plan.add_argument(
        "--ns",
        action="append",
        required=True,
        dest="nameservers",
    )
    create_plan.add_argument("--ipv4")
    create_plan.add_argument("--ipv6")
    create_plan.add_argument("--www", action="store_true")
    create_plan.add_argument(
        "--zone-directory",
        type=Path,
        default=Path("/var/lib/bind/Primary"),
    )
    create_plan.add_argument(
        "--managed-config",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.conf"),
    )
    create_plan.add_argument(
        "--managed-zone-directory",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.d"),
    )
    create_plan.add_argument("--json", action="store_true")
    create = lifecycle_sub.add_parser(
        "create",
        help="utwórz i aktywuj strefę; bez --commit działa jako dry-run",
    )
    create.add_argument("name")
    create.add_argument("--primary-ns", required=True)
    create.add_argument("--admin", required=True)
    create.add_argument(
        "--ns",
        action="append",
        required=True,
        dest="nameservers",
    )
    create.add_argument("--ipv4")
    create.add_argument("--ipv6")
    create.add_argument("--www", action="store_true")
    create.add_argument(
        "--zone-directory",
        type=Path,
        default=Path("/var/lib/bind/Primary"),
    )
    create.add_argument(
        "--managed-config",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.conf"),
    )
    create.add_argument(
        "--managed-zone-directory",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.d"),
    )
    create.add_argument(
        "--manifest-directory",
        type=Path,
        default=Path("/var/backups/zonectl-zone-create/manifests"),
    )
    create.add_argument(
        "--commit",
        action="store_true",
        help="zapisz pliki, przeładuj BIND i potwierdź strefę",
    )
    create.add_argument("--json", action="store_true")
    disable = lifecycle_sub.add_parser(
        "disable",
        help="odwracalnie wyłącz strefę; bez --commit działa jako dry-run",
    )
    disable.add_argument("name")
    disable.add_argument("--reason", required=True)
    disable.add_argument(
        "--zone-directory",
        type=Path,
        default=Path("/var/lib/bind/Primary"),
    )
    disable.add_argument(
        "--managed-config",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.conf"),
    )
    disable.add_argument(
        "--managed-zone-directory",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.d"),
    )
    disable.add_argument(
        "--disabled-root",
        type=Path,
        default=Path("/var/lib/zonectl/disabled-zones"),
    )
    disable.add_argument(
        "--manifest-directory",
        type=Path,
        default=Path("/var/backups/zonectl-zone-disable/manifests"),
    )
    disable.add_argument(
        "--root-config",
        type=Path,
        default=Path("/etc/bind/named.conf"),
    )
    disable.add_argument("--commit", action="store_true")
    disable.add_argument("--json", action="store_true")
    restore = lifecycle_sub.add_parser(
        "restore",
        help="przywróć wyłączoną strefę; bez --commit działa jako dry-run",
    )
    restore.add_argument("name")
    restore.add_argument(
        "--zone-directory",
        type=Path,
        default=Path("/var/lib/bind/Primary"),
    )
    restore.add_argument(
        "--managed-config",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.conf"),
    )
    restore.add_argument(
        "--managed-zone-directory",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.d"),
    )
    restore.add_argument(
        "--disabled-root",
        type=Path,
        default=Path("/var/lib/zonectl/disabled-zones"),
    )
    restore.add_argument(
        "--manifest-directory",
        type=Path,
        default=Path("/var/backups/zonectl-zone-restore/manifests"),
    )
    restore.add_argument(
        "--root-config",
        type=Path,
        default=Path("/etc/bind/named.conf"),
    )
    restore.add_argument("--commit", action="store_true")
    restore.add_argument("--json", action="store_true")
    quarantine = lifecycle_sub.add_parser(
        "quarantine",
        help="przenieś wyłączoną strefę do pakietu odtworzeniowego",
    )
    quarantine.add_argument("name")
    quarantine.add_argument("--reason", required=True)
    quarantine.add_argument("--confirm")
    quarantine.add_argument(
        "--zone-directory",
        type=Path,
        default=Path("/var/lib/bind/Primary"),
    )
    quarantine.add_argument(
        "--managed-config",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.conf"),
    )
    quarantine.add_argument(
        "--managed-zone-directory",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.d"),
    )
    quarantine.add_argument(
        "--disabled-root",
        type=Path,
        default=Path("/var/lib/zonectl/disabled-zones"),
    )
    quarantine.add_argument(
        "--quarantine-root",
        type=Path,
        default=Path("/var/lib/zonectl/quarantine"),
    )
    quarantine.add_argument("--commit", action="store_true")
    quarantine.add_argument("--json", action="store_true")
    quarantine_restore = lifecycle_sub.add_parser(
        "quarantine-restore",
        help="odtwórz strefę ze wskazanego pakietu kwarantanny",
    )
    quarantine_restore.add_argument("name")
    quarantine_restore.add_argument(
        "--package", type=Path, required=True
    )
    quarantine_restore.add_argument(
        "--zone-directory",
        type=Path,
        default=Path("/var/lib/bind/Primary"),
    )
    quarantine_restore.add_argument(
        "--managed-config",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.conf"),
    )
    quarantine_restore.add_argument(
        "--managed-zone-directory",
        type=Path,
        default=Path("/etc/bind/zonectl-zones.d"),
    )
    quarantine_restore.add_argument(
        "--root-config",
        type=Path,
        default=Path("/etc/bind/named.conf"),
    )
    quarantine_restore.add_argument("--commit", action="store_true")
    quarantine_restore.add_argument("--json", action="store_true")
    inventory = lifecycle_sub.add_parser(
        "inventory",
        help="pokaż wyłączone strefy i pakiety kwarantanny",
    )
    inventory.add_argument(
        "--disabled-root",
        type=Path,
        default=Path("/var/lib/zonectl/disabled-zones"),
    )
    inventory.add_argument(
        "--quarantine-root",
        type=Path,
        default=Path("/var/lib/zonectl/quarantine"),
    )
    inventory.add_argument(
        "--disable-manifest-directory",
        type=Path,
        default=Path("/var/backups/zonectl-zone-disable/manifests"),
    )
    inventory.add_argument("--json", action="store_true")

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
    if args.command == "zone":
        if args.zone_command == "inventory":
            records = ZoneInventory(
                disabled_root=args.disabled_root,
                quarantine_root=args.quarantine_root,
                disable_manifest_directory=args.disable_manifest_directory,
            ).records()
            if args.json:
                print(
                    json.dumps(
                        [record.to_dict() for record in records],
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            elif not records:
                print("Brak wyłączonych i skarantannowanych stref.")
            else:
                print(
                    f"{'STAN':<13} {'STREFA':<32} {'DATA':<25} "
                    "OPERATOR  PRZYCZYNA"
                )
                for record in records:
                    print(
                        f"{record.state:<13} {record.zone:<32} "
                        f"{record.timestamp:<25} {record.operator:<9} "
                        f"{record.reason}"
                    )
                    print(f"  {record.location}")
            return 0
        if args.zone_command == "quarantine-restore":
            name = args.name.strip().rstrip(".").casefold()
            try:
                plan = QuarantineRestoreTransaction.plan(
                    name,
                    package_directory=args.package,
                    zone_file=args.zone_directory / name,
                    active_declaration=(
                        args.managed_zone_directory / f"{name}.conf"
                    ),
                    managed_index=args.managed_config,
                    root_config=args.root_config,
                )
                result = QuarantineRestoreTransaction().apply(
                    plan, commit=args.commit
                )
            except (QuarantineRestoreError, OSError, json.JSONDecodeError) as exc:
                print(f"BŁĄD: {exc}", file=sys.stderr)
                return 2
            if args.json:
                from dataclasses import asdict

                print(
                    json.dumps(
                        asdict(result), ensure_ascii=False, indent=2
                    )
                )
            else:
                print(f"Transakcja: {result.transaction_id}")
                print(f"Strefa:     {result.zone}")
                print(f"Status:     {result.status}")
                print(f"Pakiet:     {result.package_directory}")
                print(f"Commit:     {'TAK' if result.committed else 'NIE'}")
                print(f"Rollback:   {'TAK' if result.rolled_back else 'NIE'}")
                print("\nEtapy:")
                for step in result.steps:
                    marker = "OK" if step.ok else "BŁĄD"
                    print(f"[{marker}] {step.name}: {step.message}")
            return (
                0
                if result.ok
                and result.status in {"DRY-RUN", "RESTORED"}
                else 2
            )
        if args.zone_command == "quarantine":
            name = args.name.strip().rstrip(".").casefold()
            active_declaration = (
                args.managed_zone_directory / f"{name}.conf"
            )
            try:
                plan = ZoneQuarantineTransaction.plan(
                    name,
                    zone_file=args.zone_directory / name,
                    archived_declaration=(
                        args.disabled_root / name / f"{name}.conf"
                    ),
                    active_declaration=active_declaration,
                    managed_index=args.managed_config,
                    quarantine_root=args.quarantine_root,
                    reason=args.reason,
                )
                result = ZoneQuarantineTransaction().apply(
                    plan,
                    commit=args.commit,
                    confirmation=args.confirm,
                )
            except (ZoneQuarantineError, OSError) as exc:
                print(f"BŁĄD: {exc}", file=sys.stderr)
                return 2
            if args.json:
                from dataclasses import asdict

                print(
                    json.dumps(
                        asdict(result), ensure_ascii=False, indent=2
                    )
                )
            else:
                print(f"Transakcja: {result.transaction_id}")
                print(f"Strefa:     {result.zone}")
                print(f"Status:     {result.status}")
                print(f"Przyczyna:  {result.reason}")
                print(f"Commit:     {'TAK' if result.committed else 'NIE'}")
                if result.package_directory:
                    print(f"Pakiet:     {result.package_directory}")
                print("\nEtapy:")
                for step in result.steps:
                    marker = "OK" if step.ok else "BŁĄD"
                    print(f"[{marker}] {step.name}: {step.message}")
            return (
                0
                if result.ok
                and result.status in {"DRY-RUN", "QUARANTINED"}
                else 2
            )
        if args.zone_command == "restore":
            name = args.name.strip().rstrip(".").casefold()
            try:
                plan = ZoneRestoreTransaction.plan(
                    name,
                    zone_file=args.zone_directory / name,
                    declaration_file=(
                        args.managed_zone_directory / f"{name}.conf"
                    ),
                    managed_index=args.managed_config,
                    disabled_root=args.disabled_root,
                    root_config=args.root_config,
                )
                result = ZoneRestoreTransaction(
                    args.manifest_directory,
                ).apply(plan, commit=args.commit)
            except (ZoneRestoreError, OSError) as exc:
                print(f"BŁĄD: {exc}", file=sys.stderr)
                return 2
            if args.json:
                from dataclasses import asdict

                print(
                    json.dumps(
                        asdict(result), ensure_ascii=False, indent=2
                    )
                )
            else:
                print(f"Transakcja: {result.transaction_id}")
                print(f"Strefa:     {result.zone}")
                print(f"Status:     {result.status}")
                print(f"Commit:     {'TAK' if result.committed else 'NIE'}")
                print(f"Rollback:   {'TAK' if result.rolled_back else 'NIE'}")
                if result.manifest:
                    print(f"Manifest:   {result.manifest}")
                print("\nEtapy:")
                for step in result.steps:
                    marker = "OK" if step.ok else "BŁĄD"
                    print(f"[{marker}] {step.name}: {step.message}")
            return (
                0
                if result.ok
                and result.status in {"DRY-RUN", "RESTORED"}
                else 2
            )
        if args.zone_command == "disable":
            name = args.name.strip().rstrip(".").casefold()
            try:
                plan = ZoneDisableTransaction.plan(
                    name,
                    zone_file=args.zone_directory / name,
                    declaration_file=(
                        args.managed_zone_directory / f"{name}.conf"
                    ),
                    managed_index=args.managed_config,
                    root_config=args.root_config,
                    disabled_root=args.disabled_root,
                    reason=args.reason,
                )
                result = ZoneDisableTransaction(
                    args.manifest_directory,
                ).apply(plan, commit=args.commit)
            except (ZoneDisableError, OSError) as exc:
                print(f"BŁĄD: {exc}", file=sys.stderr)
                return 2
            if args.json:
                from dataclasses import asdict

                print(
                    json.dumps(
                        asdict(result), ensure_ascii=False, indent=2
                    )
                )
            else:
                print(f"Transakcja: {result.transaction_id}")
                print(f"Strefa:     {result.zone}")
                print(f"Status:     {result.status}")
                print(f"Przyczyna:  {result.reason}")
                print(f"Commit:     {'TAK' if result.committed else 'NIE'}")
                print(f"Rollback:   {'TAK' if result.rolled_back else 'NIE'}")
                if result.manifest:
                    print(f"Manifest:   {result.manifest}")
                print("\nEtapy:")
                for step in result.steps:
                    marker = "OK" if step.ok else "BŁĄD"
                    print(f"[{marker}] {step.name}: {step.message}")
            return (
                0
                if result.ok
                and result.status in {"DRY-RUN", "DISABLED"}
                else 2
            )
        try:
            plan = ZoneLifecyclePlanner(zones).plan_create(
                ZoneCreateRequest(
                    name=args.name,
                    primary_ns=args.primary_ns,
                    admin=args.admin,
                    nameservers=tuple(args.nameservers),
                    zone_directory=args.zone_directory,
                    managed_config=args.managed_config,
                    managed_zone_directory=args.managed_zone_directory,
                    apex_ipv4=args.ipv4,
                    apex_ipv6=args.ipv6,
                    add_www=args.www,
                )
            )
        except ZoneLifecycleError as exc:
            print(f"BŁĄD: {exc}", file=sys.stderr)
            return 2
        if args.zone_command == "create":
            result = ZoneCreateTransaction(
                args.manifest_directory,
            ).apply(
                plan,
                commit=args.commit,
                activate=args.commit,
            )
            if args.json:
                from dataclasses import asdict

                print(
                    json.dumps(
                        asdict(result),
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                print(f"Transakcja: {result.transaction_id}")
                print(f"Strefa:     {result.zone}")
                print(f"Status:     {result.status}")
                print(f"Commit:     {'TAK' if result.committed else 'NIE'}")
                print(f"Rollback:   {'TAK' if result.rolled_back else 'NIE'}")
                if result.manifest:
                    print(f"Manifest:   {result.manifest}")
                print("\nEtapy:")
                for step in result.steps:
                    marker = "OK" if step.ok else "BŁĄD"
                    print(f"[{marker}] {step.name}: {step.message}")
            return (
                0
                if result.ok and result.status in {"DRY-RUN", "COMMIT"}
                else 2
            )
        if args.json:
            print(
                json.dumps(
                    plan.to_dict(),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print("PLAN UTWORZENIA STREFY — BEZ ZMIAN W SYSTEMIE")
            print(f"Strefa:       {plan.zone_name}")
            print(f"Plik:         {plan.zone_file}")
            print(f"Konfiguracja: {plan.managed_config}")
            print(f"Deklaracja:   {plan.zone_declaration_file}")
            print(f"Serial:       {plan.serial}")
            print("\nPlik strefy:\n")
            print(plan.zone_text, end="")
            print("\nDeklaracja BIND:\n")
            print(plan.bind_declaration, end="")
            print("\nPlanowane etapy:")
            for action in plan.actions:
                print(f"- {action}")
        return 0
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
