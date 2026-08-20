from __future__ import annotations

import curses
from dataclasses import dataclass
from pathlib import Path

from zonectl.core.models import Zone
from zonectl.core.transaction import TransactionResult
from zonectl.ui.curses_app import CursesApp
from zonectl.ui.dialogs import CursesDialogs
from zonectl.ui.records.renderer import RecordRenderer


@dataclass
class CommitEngine:
    target: Path

    def apply(
        self,
        zone_name: str,
        source: Path,
        commit: bool = False,
        metadata: dict[str, object] | None = None,
    ) -> TransactionResult:
        if commit:
            self.target.write_text(
                source.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        return TransactionResult(
            transaction_id="record-refresh",
            zone=zone_name,
            committed=commit,
            status="COMMIT" if commit else "DRY-RUN",
        )


class FakeWindow:
    def getmaxyx(self) -> tuple[int, int]:
        return 30, 120


def test_f8_delete_commit_rereads_active_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "example.test"
    source.write_text(
        "$TTL 3600\n"
        "@ IN NS ns1.example.test.\n"
        "@ IN NS old.example.test.\n",
        encoding="utf-8",
    )
    zone = Zone(name="example.test", file=source)
    engine = CommitEngine(source)
    app = CursesApp([zone], bind=object())
    app.transaction_engine = engine
    keys = iter((curses.KEY_F8, curses.KEY_F2, ord("q")))
    rendered: list[tuple[str, ...]] = []

    monkeypatch.setattr(app, "_get_key", lambda win: next(keys))
    monkeypatch.setattr(app, "_color", lambda health: 0)
    monkeypatch.setattr(
        app,
        "_transaction_result_view",
        lambda win, result: None,
    )
    monkeypatch.setattr(app, "_start_refresh", lambda force=False: None)
    monkeypatch.setattr(
        CursesDialogs,
        "confirm",
        staticmethod(lambda *args, **kwargs: True),
    )
    monkeypatch.setattr(
        RecordRenderer,
        "draw",
        staticmethod(
            lambda win, **kwargs: rendered.append(
                tuple(
                    view.record.rdata
                    for view in kwargs["records"]
                    if not view.deleted
                )
            )
        ),
    )

    app._records_view(FakeWindow(), zone)

    assert rendered[0] == ("ns1.example.test.", "old.example.test.")
    assert rendered[-1] == ("old.example.test.",)
    assert "ns1.example.test." not in source.read_text(encoding="utf-8")
    assert "old.example.test." in source.read_text(encoding="utf-8")
