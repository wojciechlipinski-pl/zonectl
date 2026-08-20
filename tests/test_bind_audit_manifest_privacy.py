from dataclasses import dataclass

import pytest

from zonectl.core.bind_audit_manifest import REDACTED, safe_manifest_payload


@dataclass
class ExampleResult:
    transaction_id: str = "tx-1"
    reason: str = "kontrolowana zmiana"
    steps: tuple[dict[str, object], ...] = ()
    future_internal_field: str = "must not be serialized"


def test_manifest_uses_an_explicit_field_allowlist() -> None:
    payload = safe_manifest_payload(
        ExampleResult(), ("transaction_id", "reason", "steps")
    )
    assert payload == {
        "transaction_id": "tx-1",
        "reason": "kontrolowana zmiana",
        "steps": [],
    }
    assert "future_internal_field" not in payload


@pytest.mark.parametrize(
    "secret",
    (
        'secret "base64-material";',
        "-----BEGIN PRIVATE KEY-----\nmaterial",
        "Private-key-format: v1.3",
    ),
)
def test_manifest_redacts_secret_material_recursively(secret: str) -> None:
    result = ExampleResult(steps=({"name": "gate", "message": secret},))
    payload = safe_manifest_payload(result, ("steps",))
    assert payload["steps"][0]["message"] == REDACTED
    assert secret not in str(payload)


def test_manifest_redacts_values_of_sensitive_keys() -> None:
    result = ExampleResult(steps=({"token": "abc", "private_key": "xyz"},))
    payload = safe_manifest_payload(result, ("steps",))
    assert payload["steps"][0] == {
        "token": REDACTED,
        "private_key": REDACTED,
    }


def test_manifest_rejects_non_dataclass_sources() -> None:
    with pytest.raises(TypeError):
        safe_manifest_payload({"transaction_id": "tx-1"}, ("transaction_id",))
