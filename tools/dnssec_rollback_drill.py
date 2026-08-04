#!/usr/bin/env python3
"""Kontrolowany test produkcyjnego rollbacku DNSSEC na strefie testowej."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from zonectl.core.config import DEFAULT_CONFIG, DEFAULT_GROUPS, DEFAULT_ZONES, ToolkitConfig
from zonectl.core.dnssec_enable_plan import DnssecEnablePlanner
from zonectl.core.dnssec_enable_transaction import (
    DnssecEnableStep,
    DnssecEnableTransaction,
)
from zonectl.core.runner import run


DRILL_ZONE = "zonectl-test.invalid"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--zone", default=DRILL_ZONE)
    result.add_argument("--confirm")
    result.add_argument("--execute", action="store_true")
    result.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    result.add_argument("--zones", type=Path, default=DEFAULT_ZONES)
    result.add_argument("--groups", type=Path, default=DEFAULT_GROUPS)
    result.add_argument("--zone-directory", type=Path, default=Path("/var/lib/bind/Primary"))
    result.add_argument("--key-directory", type=Path, default=Path("/var/lib/bind/keys"))
    result.add_argument(
        "--backup-root",
        type=Path,
        default=Path("/var/backups/zonectl-dnssec-enable/drills/backups"),
    )
    result.add_argument(
        "--manifest-directory",
        type=Path,
        default=Path("/var/backups/zonectl-dnssec-enable/drills/manifests"),
    )
    result.add_argument("--root-config", type=Path, default=Path("/etc/bind/named.conf"))
    result.add_argument("--json", action="store_true")
    return result


def forced_failure_after_dnssec_observed(zone: str) -> DnssecEnableStep:
    last_message = ""
    for _attempt in range(40):
        outcome = run(["rndc", "dnssec", "-status", zone], 30)
        last_message = (outcome.stdout or outcome.stderr).strip()
        if outcome.returncode == 0 and "zone signing" in outcome.stdout.casefold():
            return DnssecEnableStep(
                "forced-dnssec-failure",
                False,
                "DNSSEC zaobserwowany; wymuszono awarię kontrolną",
            )
        time.sleep(0.25)
    return DnssecEnableStep(
        "forced-dnssec-failure",
        False,
        "Wymuszono rollback po limicie oczekiwania: " + (last_message or "brak statusu"),
    )


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    normalized = args.zone.rstrip(".").casefold()
    if normalized != DRILL_ZONE:
        raise SystemExit(f"BŁĄD: drill jest dozwolony wyłącznie dla {DRILL_ZONE}")
    if args.execute and args.confirm != DRILL_ZONE:
        raise SystemExit(f"BŁĄD: wykonanie wymaga --confirm {DRILL_ZONE}")

    config = ToolkitConfig(args.config, args.zones, args.groups).load()
    discovered = config.discovered_zone(args.zone)
    if discovered is None:
        raise SystemExit("BŁĄD: strefa testowa nie jest aktywna lub nie została wykryta")
    plan = DnssecEnablePlanner().plan(
        discovered,
        key_directory=args.key_directory,
        zone_directory=args.zone_directory,
    )
    result = DnssecEnableTransaction(
        args.backup_root,
        args.manifest_directory,
        root_config=args.root_config,
        dnssec_verifier=forced_failure_after_dnssec_observed,
    ).apply(plan, commit=args.execute, activate=args.execute)

    if args.json:
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    else:
        print(f"Transakcja: {result.transaction_id}")
        print(f"Strefa:     {result.zone}")
        print(f"Status:     {result.status}")
        if result.backup_directory:
            print(f"Backup:     {result.backup_directory}")
        if result.manifest:
            print(f"Manifest:   {result.manifest}")
        for step in result.steps:
            print(f"[{'OK' if step.ok else 'BŁĄD'}] {step.name}: {step.message}")

    if args.execute:
        return 0 if result.status == "ROLLED-BACK" and result.rolled_back else 1
    return 0 if result.status == "DRY-RUN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
