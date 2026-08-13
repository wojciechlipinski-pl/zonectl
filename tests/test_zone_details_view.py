from pathlib import Path

from zonectl.core.models import Health, Zone, ZoneStatus
from zonectl.ui.zone_details_view import ZoneDetailsView


def test_authoritative_zone_details() -> None:
    zone = Zone(
        "example.pl", Path("/zones/example.pl"), group="Publiczne", dns2=True, he=True
    )
    status = ZoneStatus(
        zone=zone,
        health=Health.PASS,
        local_serial="2026081301",
        dns2_serial="2026081301",
        he_serial="2026081301",
        dnssec=True,
        message="Strefa działa poprawnie",
    )
    view = ZoneDetailsView.build(zone, status)
    text = "\n".join((*view.lines, *view.summary_lines))
    assert view.title == "example.pl"
    assert "Status        PASS" in text
    assert "SOA primary   2026081301" in text
    assert "DNSSEC        AKTYWNY" in text
    assert "Secondary     dns2, HE" in text
    assert view.summary_title == "Stan operacyjny"
    assert "Status        PASS" in "\n".join(view.summary_lines)


def test_rpz_zone_details_keep_numeric_age_and_f3_hint() -> None:
    zone = Zone(
        "cert-rpz.local",
        Path("/etc/bind/domains_rpz.db"),
        health_profile="rpz",
        rpz_max_age=600,
    )
    status = ZoneStatus(
        zone=zone,
        health=Health.PASS,
        file_exists=True,
        file_age_seconds=273,
        message="RPZ poprawna",
    )
    view = ZoneDetailsView.build(zone, status)
    text = "\n".join((*view.lines, *view.summary_lines))
    assert "Profil        RPZ" in text
    assert "Wiek RPZ      4 min 33 s" in text
    assert "Limit wieku   10 min 0 s" in text
    assert "Szczegóły      F3" in text
