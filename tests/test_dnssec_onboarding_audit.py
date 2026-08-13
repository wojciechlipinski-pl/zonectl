from pathlib import Path
from types import SimpleNamespace

from zonectl.core.dnssec_onboarding_audit import DnssecOnboardingAuditor
from zonectl.core.models import Zone


class _Reporter:
    def __init__(self, **kwargs): pass
    def collect(self, zone, directory):
        return SimpleNamespace(status="PASS", parent_ds_matches=True)


class _Checker:
    def __init__(self, **kwargs): pass
    def collect(self, zone, resolvers):
        return SimpleNamespace(status="PASS", kasp_ready=True)


def test_bulk_audit_marks_fully_valid_zone_ready() -> None:
    auditor = DnssecOnboardingAuditor(
        reporter_factory=_Reporter, checker_factory=_Checker
    )
    result = auditor.audit(
        (Zone("example.pl", Path("/zones/example.pl")),), Path("/keys")
    )
    assert result[0].status == "READY"
    assert result[0].report_status == "PASS"
    assert result[0].delegation_status == "PASS"
