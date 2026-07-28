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
    KeyBinding("e", "edytuj"),
    KeyBinding("p", "zmiany"),
    KeyBinding("q", "powrót"),
)


def render_footer(
    bindings: Sequence[KeyBinding] = RECORD_VIEW_BINDINGS,
) -> str:
    return " " + "   ".join(
        binding.render()
        for binding in bindings
    ) + " "
