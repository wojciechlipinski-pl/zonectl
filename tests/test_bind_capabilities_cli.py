import json

from zonectl import cli
from zonectl.core.bind_capabilities import BindCapabilities


def report(status: str = "PASS") -> BindCapabilities:
    return BindCapabilities(
        detected=True,
        version="9.20.4-1-Debian",
        series="9.20",
        status=status,
        dnssec_policy=True,
        inline_signing_in_policy=True,
        nsec3_iterations_zero_required=True,
        findings=(),
    )


def test_bind_capabilities_text_is_read_only(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.BindCapabilityDetector, "detect", lambda self: report())

    assert cli.main(["bind", "capabilities"]) == 0
    output = capsys.readouterr().out
    assert "MOŻLIWOŚCI BIND — TYLKO ODCZYT" in output
    assert "9.20.4-1-Debian" in output
    assert "niczego nie zmieniono" in output


def test_bind_capabilities_json_and_warning_exit(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli.BindCapabilityDetector, "detect", lambda self: report("WARN")
    )

    assert cli.main(["bind", "capabilities", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["series"] == "9.20"
    assert payload["status"] == "WARN"
