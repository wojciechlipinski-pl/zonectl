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
    KeyBinding("a", "dodaj"),
    KeyBinding("e", "edytuj"),
    KeyBinding("Del", "usuń"),
    KeyBinding("p", "zmiany"),
    KeyBinding("d", "diff"),
    KeyBinding("x", "eksport"),
    KeyBinding("u", "cofnij"),
    KeyBinding("F2", "zapisz"),
    KeyBinding("q", "powrót"),
)


def render_footer(
    bindings: Sequence[KeyBinding] = RECORD_VIEW_BINDINGS,
    *,
    read_only: bool = False,
) -> str:
    blocked = {"a", "e", "Del", "u", "F2"} if read_only else set()
    return " " + "   ".join(
        binding.render()
        for binding in bindings
        if binding.key not in blocked
    ) + " "
