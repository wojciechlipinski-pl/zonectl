"""Side-effect-free presentation model for indeterminate TUI operations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import time

from ..core.models import Health


BRAILLE_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
ASCII_FRAMES = ("|", "/", "-", "\\")


def animation_allowed(
    *,
    interactive: bool,
    json_output: bool = False,
    log_output: bool = False,
) -> bool:
    """Return whether a changing indicator is appropriate for the output."""
    return interactive and not json_output and not log_output


def wait_frames(*, ascii_only: bool = False) -> tuple[str, ...]:
    """Return the stable animation sequence for the active terminal mode."""
    return ASCII_FRAMES if ascii_only else BRAILLE_FRAMES


@dataclass(frozen=True)
class WaitIndicator:
    """Render one deterministic snapshot of an indeterminate operation."""

    label: str
    started_at: float
    clock: Callable[[], float] = time.monotonic
    frames: tuple[str, ...] = BRAILLE_FRAMES
    interval: float = 0.1
    animated: bool = True

    @classmethod
    def start(
        cls,
        label: str,
        *,
        clock: Callable[[], float] = time.monotonic,
        ascii_only: bool = False,
        animated: bool = True,
        interval: float = 0.1,
    ) -> WaitIndicator:
        """Create an indicator whose elapsed time starts at the current clock."""
        clean_label = label.strip()
        if not clean_label:
            raise ValueError("wait indicator label must not be empty")
        if interval <= 0:
            raise ValueError("wait indicator interval must be positive")
        return cls(
            label=clean_label,
            started_at=clock(),
            clock=clock,
            frames=wait_frames(ascii_only=ascii_only),
            interval=interval,
            animated=animated,
        )

    def elapsed(self) -> float:
        """Return monotonic elapsed seconds, clamped against clock rollback."""
        return max(0.0, self.clock() - self.started_at)

    def frame(self) -> str:
        """Return the current animation frame or an empty static marker."""
        if not self.animated:
            return ""
        index = int(self.elapsed() / self.interval) % len(self.frames)
        return self.frames[index]

    def render(self) -> str:
        """Render the current stage and elapsed time without fake progress."""
        marker = self.frame()
        prefix = f"{marker} " if marker else ""
        return f"{prefix}{self.label} — {self.elapsed():.1f} s"


def render_wait_result(
    label: str,
    health: Health,
    *,
    detail: str | None = None,
) -> str:
    """Replace an animation with an explicit semantic completion result."""
    state = {
        Health.PASS: "PASS",
        Health.WARN: "WARN",
        Health.FAIL: "FAIL",
        Health.UNKNOWN: "WARN",
    }[health]
    suffix = f": {detail.strip()}" if detail and detail.strip() else ""
    return f"[{state}] {label.strip()}{suffix}"
