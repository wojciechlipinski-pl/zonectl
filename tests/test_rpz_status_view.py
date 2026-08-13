from zonectl.core.bind_environment_report import RpzEnvironment
from zonectl.ui.rpz_status_view import RpzStatusView


def _rpz(**changes) -> RpzEnvironment:
    values = {
        "zone": "cert-rpz.local",
        "source_file": "/etc/bind/domains_rpz.db",
        "mode": "EXTERNAL",
        "health": "ACTIVE",
        "age_seconds": 280,
        "max_age_seconds": 600,
        "serial": "1786608925",
        "nodes": 278030,
        "loaded": True,
        "timer_unit": "update-cert-rpz.timer",
        "timer_enabled": True,
        "timer_active": True,
        "service_unit": "update-cert-rpz.service",
        "service_result": "success",
        "updater_path": "/usr/local/sbin/update-cert-rpz.sh",
        "findings": (),
    }
    values.update(changes)
    return RpzEnvironment(**values)


def test_builds_external_active_rpz_panel() -> None:
    view = RpzStatusView.build(_rpz())
    text = "\n".join(view.lines)
    assert view.title == "RPZ: cert-rpz.local — ACTIVE"
    assert "Tryb zarządzania      EXTERNAL" in text
    assert "Wiek                  4 min 40 s" in text
    assert "Serial                1786608925" in text
    assert "Liczba węzłów         278030" in text
    assert "Stan timera           enabled, active" in text
    assert "Widok tylko do odczytu" in text


def test_panel_shows_failures_and_warnings() -> None:
    view = RpzStatusView.build(
        _rpz(
            health="FAILED",
            timer_active=False,
            service_result="exit-code",
            findings=("BIND nie potwierdził załadowania strefy RPZ",),
        )
    )
    text = "\n".join(view.lines)
    assert view.health == "FAILED"
    assert "disabled" not in text
    assert "enabled, inactive" in text
    assert "OSTRZEŻENIA" in text
    assert "BIND nie potwierdził" in text
