from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class KeyBinding:
    key: str
    description: str

    def render(self) -> str:
        return f"{self.key} {self.description}"


RECORD_VIEW_BINDINGS: tuple[KeyBinding, ...] = (
    KeyBinding("↑/↓", "wybór"),
    KeyBinding("/", "szukaj"),
    KeyBinding("n/N", "następny/poprzedni"),
    KeyBinding("c", "wyczyść"),
    KeyBinding("s", "sortuj"),
    KeyBinding("Ins", "dodaj"),
    KeyBinding("F4", "edytuj"),
    KeyBinding("Del", "usuń"),
    KeyBinding("p", "zmiany"),
    KeyBinding("F3", "diff"),
    KeyBinding("x", "eksport"),
    KeyBinding("b", "masowe"),
    KeyBinding("u", "cofnij"),
    KeyBinding("F2", "zapisz"),
    KeyBinding("q", "powrót"),
)


def render_footer(
    bindings: Sequence[KeyBinding] = RECORD_VIEW_BINDINGS,
    *,
    read_only: bool = False,
) -> str:
    blocked = {"Ins", "F4", "Del", "b", "u", "F2"} if read_only else set()
    return (
        " "
        + "   ".join(
            binding.render() for binding in bindings if binding.key not in blocked
        )
        + " "
    )
