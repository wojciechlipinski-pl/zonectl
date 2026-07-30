from __future__ import annotations

import curses
from dataclasses import dataclass
from pathlib import Path

from zonectl.core.models import Zone
from zonectl.core.transaction import StepResult, TransactionResult
from zonectl.core.zone_edit_session import ZoneEditSession
from zonectl.core.zone_parser import DNSRecord
from zonectl.ui.curses_app import CursesApp


@dataclass
class RecordingEngine:
    target: Path
    calls: int = 0
    last_commit: bool | None = None

    def apply(
        self,
        zone_name: str,
        source: Path,
        commit: bool = False,
        metadata: dict[str, object] | None = None,
    ) -> TransactionResult:
        self.calls += 1
        self.last_commit = commit

        result = TransactionResult(
            transaction_id="pending-changes-test",
            zone=zone_name,
            committed=commit,
            status="COMMIT" if commit else "DRY-RUN",
            steps=[
                StepResult(
                    name="named-checkzone",
                    ok=True,
                    message="OK",
                )
            ],
        )

        if commit:
            self.target.write_text(
                source.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

        return result


class FakeWindow:
    def erase(self) -> None:
        pass

    def getmaxyx(self) -> tuple[int, int]:
        return 30, 120

    def addnstr(self, *args) -> None:
        pass

    def refresh(self) -> None:
        pass


def replacement(
    original: DNSRecord,
    address: str,
) -> DNSRecord:
    return DNSRecord(
        owner=original.owner,
        ttl=original.ttl,
        rrclass=original.rrclass,
        rtype=original.rtype,
        rdata=address,
        raw=original.raw,
    )


def test_pending_changes_f2_commits_and_reloads_session(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "example.pl"
    source.write_text(
        "$TTL 3600\n"
        "www 300 IN A 192.0.2.10\n",
        encoding="utf-8",
    )
    zone = Zone(name="example.pl", file=source)
    engine = RecordingEngine(source)
    session = ZoneEditSession(zone, engine)
    old_model = session.model
    view = old_model.record_views[0]

    old_model.replace_by_identifier(
        view.identifier,
        replacement(view.record, "192.0.2.40"),
    )

    assert old_model.change_count == 1
    assert old_model.dirty is True

    app = CursesApp([zone], bind=object())
    shown_results: list[TransactionResult] = []

    monkeypatch.setattr(
        app,
        "_get_key",
        lambda win: curses.KEY_F2,
    )
    monkeypatch.setattr(
        app,
        "_transaction_result_view",
        lambda win, result: shown_results.append(result),
    )

    app._pending_changes_view(
        FakeWindow(),
        session,
        old_model,
        zone,
    )

    assert engine.calls == 1
    assert engine.last_commit is True
    assert shown_results[0].status == "COMMIT"
    assert shown_results[0].committed is True

    assert session.model is not old_model
    assert session.model.dirty is False
    assert session.model.change_count == 0
    assert session.model.records[0].rdata == "192.0.2.40"
    assert source.read_text(encoding="utf-8") == (
        "$TTL 3600\n"
        "www\t300\tIN\tA\t192.0.2.40\n"
    )
