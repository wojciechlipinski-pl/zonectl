from __future__ import annotations

from zonectl.core.dnssec_guidance import build_dnssec_guidance, localize_bind_time
from zonectl.core.dnssec_report import DnssecReport


def report(**changes) -> DnssecReport:
    values = dict(
        zone="example.pl",
        status="WARN",
        configured=True,
        dnssec_policy="default",
        inline_signing=True,
        loaded=True,
        signing=True,
        rndc_status=(),
        key_directory="/keys",
        key_files=(),
        dnskey_records=("257 3 13 key",),
        rrsig_records=("DNSKEY signature",),
        calculated_ds=("12345 13 2 ABCD",),
        parent_ds_records=(),
        parent_ds_matches=False,
        warnings=("Brak DS",),
        errors=(),
        next_key_event=None,
    )
    values.update(changes)
    return DnssecReport(**values)


def test_propagation_blocks_ds_and_exposes_next_event() -> None:
    guidance = build_dnssec_guidance(
        report(
            rndc_status=(
                "  - dnskey: omnipresent",
                "  - zone rrsig: rumoured",
                "  - key rrsig: omnipresent",
            ),
            next_key_event="Wed, 05 Aug 2026 07:41:35 GMT",
        )
    )

    assert guidance.stage == "PROPAGATING"
    assert guidance.progress == "2/3 warunków propagacji gotowych"
    assert guidance.not_before is not None
    assert "2026-08-05" in guidance.not_before
    assert guidance.ds_publication_allowed is False


def test_all_kasp_records_allow_ds_publication() -> None:
    guidance = build_dnssec_guidance(
        report(
            rndc_status=(
                "- dnskey: omnipresent",
                "- ds: hidden",
                "- zone rrsig: omnipresent",
                "- key rrsig: omnipresent",
            )
        )
    )

    assert guidance.stage == "READY_FOR_DS"
    assert guidance.ds_publication_allowed is True
    assert "rejestratora" in guidance.next_action


def test_matching_parent_ds_finishes_deployment() -> None:
    guidance = build_dnssec_guidance(
        report(
            status="PASS",
            parent_ds_records=("12345 13 2 ABCD",),
            parent_ds_matches=True,
            warnings=(),
        )
    )

    assert guidance.stage == "ACTIVE"
    assert guidance.progress == "4/4 warunków gotowych"


def test_unsigned_zone_points_to_enable_plan() -> None:
    guidance = build_dnssec_guidance(
        report(status="UNSIGNED", configured=False, parent_ds_matches=None)
    )

    assert guidance.stage == "UNSIGNED"
    assert guidance.ds_publication_allowed is False
    assert "enable-plan example.pl" in guidance.next_action


def test_json_report_contains_guidance() -> None:
    payload = report().to_dict()
    assert payload["guidance"]["stage"] == "PROPAGATING"


def test_unparseable_bind_time_is_preserved() -> None:
    assert localize_bind_time("unknown") == "unknown"
