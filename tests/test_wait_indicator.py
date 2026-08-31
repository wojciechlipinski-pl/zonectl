import pytest

from zonectl.core.models import Health
from zonectl.ui.wait_indicator import (
    ASCII_FRAMES,
    BRAILLE_FRAMES,
    WaitIndicator,
    animation_allowed,
    render_wait_result,
    wait_frames,
)


class FakeClock:
    def __init__(self, value: float = 100.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


def test_indicator_advances_deterministically_and_wraps() -> None:
    clock = FakeClock()
    indicator = WaitIndicator.start(
        "Odświeżanie stref",
        clock=clock,
        interval=1.0,
    )

    assert indicator.frame() == BRAILLE_FRAMES[0]
    clock.value += 1.0
    assert indicator.frame() == BRAILLE_FRAMES[1]
    clock.value += 9.0
    assert indicator.frame() == BRAILLE_FRAMES[0]


def test_ascii_fallback_has_portable_frames() -> None:
    clock = FakeClock()
    indicator = WaitIndicator.start(
        "BIND",
        clock=clock,
        ascii_only=True,
        interval=1.0,
    )

    assert wait_frames(ascii_only=True) == ASCII_FRAMES
    assert indicator.frame() == "|"
    clock.value += 2.0
    assert indicator.frame() == "-"


def test_render_shows_stage_and_elapsed_time_without_percentage() -> None:
    clock = FakeClock()
    indicator = WaitIndicator.start("Oczekiwanie na BIND", clock=clock)
    clock.value += 2.4

    rendered = indicator.render()
    assert "Oczekiwanie na BIND" in rendered
    assert "2.4 s" in rendered
    assert "%" not in rendered


def test_static_mode_keeps_useful_text_without_animation() -> None:
    clock = FakeClock()
    indicator = WaitIndicator.start("Raport", clock=clock, animated=False)

    assert indicator.frame() == ""
    assert indicator.render() == "Raport — 0.0 s"


@pytest.mark.parametrize(
    ("interactive", "json_output", "log_output", "expected"),
    [
        (True, False, False, True),
        (False, False, False, False),
        (True, True, False, False),
        (True, False, True, False),
    ],
)
def test_animation_is_disabled_for_machine_readable_output(
    interactive: bool,
    json_output: bool,
    log_output: bool,
    expected: bool,
) -> None:
    assert (
        animation_allowed(
            interactive=interactive,
            json_output=json_output,
            log_output=log_output,
        )
        is expected
    )


def test_clock_rollback_cannot_produce_negative_elapsed_time() -> None:
    clock = FakeClock()
    indicator = WaitIndicator.start("Etap", clock=clock)
    clock.value -= 5

    assert indicator.elapsed() == 0.0


def test_invalid_configuration_is_rejected() -> None:
    with pytest.raises(ValueError, match="label"):
        WaitIndicator.start("   ")
    with pytest.raises(ValueError, match="interval"):
        WaitIndicator.start("Etap", interval=0)


@pytest.mark.parametrize(
    ("health", "state"),
    [
        (Health.PASS, "PASS"),
        (Health.WARN, "WARN"),
        (Health.FAIL, "FAIL"),
        (Health.UNKNOWN, "WARN"),
    ],
)
def test_completion_replaces_spinner_with_semantic_result(
    health: Health,
    state: str,
) -> None:
    assert render_wait_result("Odświeżanie", health, detail="gotowe") == (
        f"[{state}] Odświeżanie: gotowe"
    )
