from __future__ import annotations

import re
from pathlib import Path

import pytest

from zonectl.core.record_validation import SUPPORTED_RECORD_TYPES, validate_rdata


ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = (
    ROOT / "docs" / "RECORD_EXAMPLES.md",
    ROOT / "docs" / "en" / "RECORD_EXAMPLES.md",
)
EXAMPLE_ROW = re.compile(
    r"^\| `(?P<rtype>[A-Z]+)` \| `[^`]+` \| `\d+` \| `(?P<rdata>.+)` \|$",
    re.MULTILINE,
)


@pytest.mark.parametrize("document", DOCUMENTS, ids=("polish", "english"))
def test_documented_examples_cover_and_validate_every_supported_type(
    document: Path,
) -> None:
    content = document.read_text(encoding="utf-8")
    examples = {
        match.group("rtype"): match.group("rdata")
        for match in EXAMPLE_ROW.finditer(content)
    }

    assert tuple(examples) == SUPPORTED_RECORD_TYPES
    assert all(
        validate_rdata(rtype, rdata) is None for rtype, rdata in examples.items()
    )


@pytest.mark.parametrize("document", DOCUMENTS, ids=("polish", "english"))
def test_documented_examples_use_only_public_synthetic_names_and_addresses(
    document: Path,
) -> None:
    content = document.read_text(encoding="utf-8").casefold()

    assert "example.test" in content
    assert "192.0.2.10" in content
    assert "2001:db8::10" in content
