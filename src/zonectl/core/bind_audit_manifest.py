"""Privacy-safe serialization helpers for BIND access audit manifests."""

from __future__ import annotations

import re
from dataclasses import asdict, is_dataclass
from typing import Any, Iterable, cast


REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = re.compile(
    r"(?:^|_)(?:secret|password|passphrase|token|private[_-]?key)(?:$|_)",
    re.IGNORECASE,
)
_SENSITIVE_TEXT = (
    re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"\bsecret\s+\"[^\"]+\"\s*;", re.IGNORECASE),
    re.compile(r"\bPrivate-key-format\s*:", re.IGNORECASE),
)


def safe_manifest_payload(result: object, allowed_fields: Iterable[str]) -> dict[str, Any]:
    """Return only explicitly allowed, recursively sanitized result fields."""
    if isinstance(result, type) or not is_dataclass(result):
        raise TypeError("Manifest source must be a dataclass instance")
    source: dict[str, Any] = asdict(cast(Any, result))
    payload = {
        field: source[field]
        for field in allowed_fields
        if field in source
    }
    sanitized = _sanitize(payload)
    if not isinstance(sanitized, dict):
        raise TypeError("Sanitized manifest payload must be a dictionary")
    return cast(dict[str, Any], sanitized)


def _sanitize(value: Any, *, key: str = "") -> Any:
    if key and _SENSITIVE_KEYS.search(key):
        return REDACTED
    if isinstance(value, dict):
        return {
            str(item_key): _sanitize(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize(item) for item in value]
    if isinstance(value, str) and any(pattern.search(value) for pattern in _SENSITIVE_TEXT):
        return REDACTED
    return value
