from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from zonectl.core.models import Zone
from zonectl.core.transaction import (
    StepResult,
    TransactionResult,
)
from zonectl.core.zone_edit_session import (
    ZoneEditSession,
    ZoneEditSessionError,
)
from zonectl.core.zone_parser import DNSRecord
from zonectl.ui.records.editor import RecordEditor


@dataclass
class FakeEngine:
    target: Path
    committed_content: str | None = None
    calls: int = 0
    last_commit: bool | None = None
    last_source: Path | None = None

    def apply(
        self,
        zone_name: str,
        source: Path,
        commit: bool = False,
        metadata: dict[str, object] | None = None,
    ) -> TransactionResult:
        self.calls += 1
        self.last_commit = commit
        self.last_source = source

        result = TransactionResult(
            transaction_id="test-transaction",
            zone=zone_name,
            committed=False,
        )

        result.steps.append(
            StepResult(
                name="named-checkzone",
                ok=True,
                message="OK",
            )
        )

        if commit:
            content = source.read_text(encoding="utf-8")
            self.target.write_text(content, encoding="utf-8")
            self.committed_content = content
            result.committed = True
            result.status = "COMMIT"
        else:
            result.status = "DRY-RUN"
            result.steps.append(
                StepResult(
                    name="dry-run",
                    ok=True,
                    message="Nie zmieniono pliku",
                )
            )

        return result


def make_zone(path: Path) -> Zone:
    return Zone(
        name="example.pl",
        file=path,
    )


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


def test_session_loads_source_document(
    tmp_path: Path,
) -> None:
    source = tmp_path / "example.pl"
    source.write_text(
        "$TTL 3600\n"
        "www 300 IN A 192.0.2.10\n",
        encoding="utf-8",
    )

    engine = FakeEngine(source)
    session = ZoneEditSession(
        make_zone(source),
        engine,
    )

    assert session.source_path == source.resolve()
    assert len(session.model.records) == 1
    assert session.dirty is False


def test_render_candidate_contains_model_change(
    tmp_path: Path,
) -> None:
    source = tmp_path / "example.pl"
    source.write_text(
        "$TTL 3600\n"
        "www 300 IN A 192.0.2.10\n",
        encoding="utf-8",
    )

    session = ZoneEditSession(
        make_zone(source),
        FakeEngine(source),
    )

    view = session.model.record_views[0]

    session.model.replace_by_identifier(
        view.identifier,
        replacement(
            view.record,
            "192.0.2.20",
        ),
    )

    candidate = session.render_candidate()

    assert candidate == (
        "$TTL 3600\n"
        "www\t300\tIN\tA\t192.0.2.20\n"
    )
    assert session.dirty is True


def test_dry_run_does_not_change_active_file(
    tmp_path: Path,
) -> None:
    source = tmp_path / "example.pl"
    original = (
        "$TTL 3600\n"
        "www 300 IN A 192.0.2.10\n"
    )
    source.write_text(original, encoding="utf-8")

    engine = FakeEngine(source)
    session = ZoneEditSession(
        make_zone(source),
        engine,
    )

    view = session.model.record_views[0]

    session.model.replace_by_identifier(
        view.identifier,
        replacement(
            view.record,
            "192.0.2.30",
        ),
    )

    result = session.save(commit=False)

    assert result.status == "DRY-RUN"
    assert result.committed is False
    assert source.read_text(encoding="utf-8") == original
    assert session.dirty is True
    assert engine.last_commit is False


def test_soa_form_change_uses_automatic_serial_bump(
    tmp_path: Path,
) -> None:
    source = tmp_path / "example.pl"
    original = (
        "$TTL 3600\n"
        "@ 3600 IN SOA ns1.example.pl. hostmaster.example.pl. (\n"
        "    2026082001 ; serial\n"
        "    3600       ; refresh\n"
        "    900        ; retry\n"
        "    1209600    ; expire\n"
        "    300 )      ; minimum\n"
        "@ 3600 IN NS ns1.example.pl.\n"
    )
    source.write_text(original, encoding="utf-8")
    session = ZoneEditSession(
        make_zone(source), FakeEngine(source),
        today_provider=lambda: date(2026, 8, 21),
    )
    view = next(
        item for item in session.model.record_views
        if item.record.rtype == "SOA"
    )
    updated, error = RecordEditor.build_soa_record(
        view.record,
        primary="ns2.example.pl.",
        administrator="dns.example.pl.",
        refresh="7200", retry="1200", expire="604800", minimum="600",
        ttl_text="3600",
    )
    assert error == ""
    assert updated is not None
    session.model.replace_by_identifier(view.identifier, updated)

    candidate = session.render_candidate()
    repeated = session.render_candidate()

    assert "ns2.example.pl. dns.example.pl." in candidate
    assert "2026082101 ; serial" in candidate
    assert "7200       ; refresh" in candidate
    assert "1200        ; retry" in candidate
    assert "604800    ; expire" in candidate
    assert "600 )      ; minimum" in candidate
    assert repeated == candidate
    assert source.read_text(encoding="utf-8") == original


def test_commit_changes_active_file_and_reloads_session(
    tmp_path: Path,
) -> None:
    source = tmp_path / "example.pl"
    source.write_text(
        "$TTL 3600\n"
        "www 300 IN A 192.0.2.10\n",
        encoding="utf-8",
    )

    engine = FakeEngine(source)
    session = ZoneEditSession(
        make_zone(source),
        engine,
    )

    view = session.model.record_views[0]

    session.model.replace_by_identifier(
        view.identifier,
        replacement(
            view.record,
            "192.0.2.40",
        ),
    )

    result = session.save(commit=True)

    assert result.committed is True
    assert result.status == "COMMIT"
    assert session.dirty is False
    assert engine.last_commit is True

    assert source.read_text(encoding="utf-8") == (
        "$TTL 3600\n"
        "www\t300\tIN\tA\t192.0.2.40\n"
    )

    assert session.model.records[0].rdata == "192.0.2.40"


def test_discard_restores_original_state(
    tmp_path: Path,
) -> None:
    source = tmp_path / "example.pl"
    original = (
        "$TTL 3600\n"
        "www 300 IN A 192.0.2.10\n"
    )
    source.write_text(original, encoding="utf-8")

    session = ZoneEditSession(
        make_zone(source),
        FakeEngine(source),
    )

    view = session.model.record_views[0]

    session.model.replace_by_identifier(
        view.identifier,
        replacement(
            view.record,
            "192.0.2.50",
        ),
    )

    session.discard()

    assert session.dirty is False
    assert session.render_candidate() == original


def test_candidate_is_removed_after_save(
    tmp_path: Path,
) -> None:
    source = tmp_path / "example.pl"
    source.write_text(
        "www 300 IN A 192.0.2.10\n",
        encoding="utf-8",
    )

    engine = FakeEngine(source)
    session = ZoneEditSession(
        make_zone(source),
        engine,
        candidate_directory=tmp_path,
    )

    result = session.save(
        commit=False,
        remove_candidate=True,
    )

    assert result.candidate.exists() is False


def test_missing_zone_file_is_rejected(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.zone"

    try:
        ZoneEditSession(
            make_zone(missing),
            FakeEngine(missing),
        )
    except ZoneEditSessionError as exc:
        assert "nie istnieje" in str(exc)
    else:
        raise AssertionError(
            "Oczekiwano ZoneEditSessionError"
        )


def test_session_automatically_bumps_multiline_soa_serial(
    tmp_path: Path,
) -> None:
    from datetime import date

    source = tmp_path / "example.pl"
    source.write_text(
        "$TTL 3600\n"
        "@ IN SOA ns1.example.pl. hostmaster.example.pl. (\n"
        "    2026072701 ; serial\n"
        "    3600\n"
        "    900\n"
        "    1209600\n"
        "    3600 )\n"
        "www IN A 192.0.2.10\n",
        encoding="utf-8",
    )

    session = ZoneEditSession(
        make_zone(source),
        FakeEngine(source),
        today_provider=lambda: date(2026, 7, 29),
    )

    view = next(
        view
        for view in session.model.record_views
        if view.record.rtype == "A"
    )

    session.model.replace_by_identifier(
        view.identifier,
        replacement(
            view.record,
            "192.0.2.20",
        ),
    )

    candidate = session.render_candidate()

    assert "2026072901 ; serial" in candidate
    assert session.serial_change is not None
    assert session.serial_change.previous == 2026072701
    assert session.serial_change.current == 2026072901


def test_serial_is_bumped_only_once_per_session(
    tmp_path: Path,
) -> None:
    from datetime import date

    source = tmp_path / "example.pl"
    source.write_text(
        "@ IN SOA ns1.example.pl. hostmaster.example.pl. (\n"
        "    2026072901\n"
        "    3600\n"
        "    900\n"
        "    1209600\n"
        "    3600 )\n"
        "www IN A 192.0.2.10\n",
        encoding="utf-8",
    )

    session = ZoneEditSession(
        make_zone(source),
        FakeEngine(source),
        today_provider=lambda: date(2026, 7, 29),
    )

    view = next(
        view
        for view in session.model.record_views
        if view.record.rtype == "A"
    )

    session.model.replace_by_identifier(
        view.identifier,
        replacement(
            view.record,
            "192.0.2.30",
        ),
    )

    first = session.render_candidate()
    second = session.render_candidate()

    assert "2026072902" in first
    assert "2026072902" in second
    assert "2026072903" not in second
