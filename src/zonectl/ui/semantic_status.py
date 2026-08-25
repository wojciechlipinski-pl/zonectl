"""Shared semantic state classification for CLI-like TUI renderers."""

from __future__ import annotations

import re

from ..core.models import Health


PASS_STATES = frozenset({
    "ACTIVE", "COMMIT", "ENABLED", "MATCH", "OK", "OMNIPRESENT",
    "PASS", "READY", "READY-FOR-DS", "SUCCESS", "MANAGED", "NONE",
    "NO-CHANGE", "LOW",
})
WARN_STATES = frozenset({
    "DELAYED", "DISABLED", "DRY-RUN", "DS-CONFIRMATION-REQUIRED",
    "DS-PROPAGATING", "EXTERNAL", "INDETERMINATE", "LEGACY-PRIMARY",
    "MANAGED-LEGACY-PATH", "MEDIUM", "NOT-PUBLISHED", "PENDING",
    "PROPAGATING", "READY-TO-FINALIZE", "RUMOURED", "ROLLED-BACK",
    "UNRETENTIVE", "UNKNOWN", "WARN", "WARNING", "WITHDRAWING",
})
FAIL_STATES = frozenset({
    "BLOCKED", "CONFLICT", "ERROR", "FAIL", "FAILED", "HIGH", "MISMATCH",
    "MISSING", "NOT-AUTH", "ROLLBACK-FAILED", "STALE",
})
NEUTRAL_STATES = frozenset({
    "N/A", "PLAN", "SKIP", "UNSIGNED",
})

_BRACKET_STATE = re.compile(r"\[(?P<state>[A-Z][A-Z_-]*)\]", re.IGNORECASE)
_LABELED_STATE = re.compile(
    r"(?:^|\b)(?:status|stan|etap|ryzyko)\s*[:=]?\s*(?P<state>[A-Z][A-Z_-]*)",
    re.IGNORECASE,
)


def normalize_state(value: object) -> str:
    """Return a stable spelling used by the semantic state tables."""
    return str(value).strip().replace("_", "-").upper()


def state_health(value: object) -> Health | None:
    """Map an explicit state token to health; return None for plain data."""
    state = normalize_state(value)
    if state in PASS_STATES:
        return Health.PASS
    if state in WARN_STATES:
        return Health.WARN
    if state in FAIL_STATES or state.startswith("BLOCKED-"):
        return Health.FAIL
    if state in NEUTRAL_STATES:
        return Health.UNKNOWN
    return None


def text_health(text: object) -> Health | None:
    """Extract a displayed status without coloring unrelated prose."""
    value = str(text)
    for pattern in (_BRACKET_STATE, _LABELED_STATE):
        match = pattern.search(value)
        if match:
            health = state_health(match.group("state"))
            if health is not None:
                return health
    stripped = normalize_state(value)
    if stripped.startswith("BŁĄD"):
        return Health.FAIL
    if stripped.startswith("OSTRZEŻENIE"):
        return Health.WARN
    if stripped in PASS_STATES | WARN_STATES | FAIL_STATES | NEUTRAL_STATES:
        return state_health(stripped)
    return None


def kasp_health(value: object, *, goal: object | None = None) -> Health:
    """Classify a KASP state relative to the policy goal when available."""
    state = normalize_state(value)
    wanted = normalize_state(goal) if goal is not None else ""
    if state == "OMNIPRESENT":
        return Health.PASS
    if state in {"RUMOURED", "UNRETENTIVE"}:
        return Health.WARN
    if state == "HIDDEN":
        return Health.PASS if wanted == "HIDDEN" else Health.WARN
    if state in FAIL_STATES:
        return Health.FAIL
    return Health.WARN


def parse_kasp_line(text: str) -> tuple[str, str] | None:
    """Parse lines emitted by ``rndc dnssec -status`` presentation."""
    match = re.match(r"^\s*-\s*(?P<label>[^:]+):\s*(?P<value>\S+)", text)
    if not match:
        return None
    return match.group("label").strip().casefold(), match.group("value").strip()
