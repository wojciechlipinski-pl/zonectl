from __future__ import annotations

from dataclasses import dataclass

import pytest

from zonectl.core.models import Zone
from zonectl.core.multi_zone_session import (
    MultiZoneEditSession,
    MultiZoneSessionError,
)
from zonectl.core.transaction import StepResult, TransactionResult
from zonectl.core.zone_edit_session import ZoneSaveResult


@dataclass
class FakeSession:
    zone: Zone
    dirty: bool = True
    validation_ok: bool = True
    commit_ok: bool = True
    closed: bool = False
    discarded: bool = False
    calls: list[bool] | None = None

    def __post_init__(self) -> None:
        self.calls = []

    def save(self, *, commit: bool = False) -> ZoneSaveResult:
        assert self.calls is not None
        self.calls.append(commit)
        ok = self.commit_ok if commit else self.validation_ok
        transaction = TransactionResult(
            transaction_id=f"tx-{self.zone.name}-{commit}",
            zone=self.zone.name,
            committed=commit and ok,
            status=("COMMIT" if commit and ok else "DRY-RUN" if ok else "FAIL"),
            steps=[StepResult("test", ok, "OK" if ok else "FAIL")],
        )
        if transaction.committed:
            self.dirty = False
        return ZoneSaveResult(transaction, self.zone.file)

    def discard(self) -> None:
        self.discarded = True
        self.dirty = False

    def close(self) -> None:
        self.closed = True


def zones() -> list[Zone]:
    return [
        Zone(name="one.example", file=None),
        Zone(name="two.example", file=None),
        Zone(name="three.example", file=None),
    ]


def coordinator(
    sessions: dict[str, FakeSession],
) -> MultiZoneEditSession:
    available = zones()

    def factory(zone: Zone):
        session = FakeSession(zone)
        sessions[zone.name] = session
        return session

    return MultiZoneEditSession(available, factory)


def test_open_reuses_session_and_unknown_zone_is_rejected() -> None:
    sessions: dict[str, FakeSession] = {}
    multi = coordinator(sessions)

    assert multi.open("one.example") is multi.open("one.example")
    assert multi.open_zone_names == ("one.example",)

    with pytest.raises(MultiZoneSessionError, match="Nieznana"):
        multi.open("missing.example")


def test_all_zones_are_validated_before_first_commit() -> None:
    sessions: dict[str, FakeSession] = {}
    multi = coordinator(sessions)
    multi.open("one.example")
    multi.open("two.example")

    result = multi.save_all()

    assert result.ok is True
    assert len(result.validated) == 2
    assert len(result.committed) == 2
    assert sessions["one.example"].calls == [False, True]
    assert sessions["two.example"].calls == [False, True]


def test_validation_failure_prevents_every_commit() -> None:
    sessions: dict[str, FakeSession] = {}
    multi = coordinator(sessions)
    multi.open("one.example")
    multi.open("two.example")
    sessions["two.example"].validation_ok = False

    result = multi.save_all()

    assert result.ok is False
    assert result.failed is not None
    assert sessions["one.example"].calls == [False]
    assert sessions["two.example"].calls == [False]


def test_commit_failure_stops_remaining_zones() -> None:
    sessions: dict[str, FakeSession] = {}
    multi = coordinator(sessions)
    multi.open("one.example")
    multi.open("two.example")
    multi.open("three.example")
    sessions["two.example"].commit_ok = False

    result = multi.save_all()

    assert result.ok is False
    assert len(result.committed) == 1
    assert sessions["one.example"].calls == [False, True]
    assert sessions["two.example"].calls == [False, True]
    assert sessions["three.example"].calls == [False]


def test_dirty_session_requires_explicit_discard() -> None:
    sessions: dict[str, FakeSession] = {}
    multi = coordinator(sessions)
    multi.open("one.example")

    with pytest.raises(MultiZoneSessionError, match="niezapisane"):
        multi.close_zone("one.example")

    multi.close_zone("one.example", discard=True)

    assert sessions["one.example"].discarded is True
    assert sessions["one.example"].closed is True
