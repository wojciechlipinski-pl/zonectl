#!/usr/bin/env python3
"""Print a network-free synthetic ZoneCTL 4.17 migration walkthrough."""

from __future__ import annotations

import json


def main() -> int:
    """Render allowlisted demonstration data without reading local BIND."""

    demo = {
        "zone": "signed.example.test",
        "source_policy": "stable-csk",
        "target_policy": "modern-split",
        "differences": {
            "key_model": "CSK -> KSK+ZSK",
            "algorithms": "ED25519 -> ECDSAP256SHA256",
            "lifetimes": "CSK P1Y -> KSK P2Y, ZSK P90D",
        },
        "ds_impact": "CHANGE_REQUIRED",
        "phases": [
            "PLANNED",
            "POLICY_APPLIED",
            "WAITING_DNSKEY",
            "WAITING_DS",
            "WAITING_PROPAGATION",
            "READY_TO_FINALIZE",
            "COMPLETE",
        ],
        "resolver_requirement": "at least 2 public resolvers",
        "registrar_action": "manual only; ZoneCTL never changes DS",
        "privacy": "no DNSKEY, DS digest, resolver address, or production data",
    }
    print(json.dumps(demo, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
