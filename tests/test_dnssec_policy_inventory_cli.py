import json
from pathlib import Path

from zonectl.cli import main
from zonectl.core.bind_capabilities import BindCapabilities


def mock_capabilities(monkeypatch) -> None:
    monkeypatch.setattr(
        "zonectl.cli.BindCapabilityDetector.detect",
        lambda self: BindCapabilities(
            detected=True,
            version="9.20.26",
            series="9.20",
            status="PASS",
            dnssec_policy=True,
            inline_signing_in_policy=True,
            nsec3_iterations_zero_required=True,
            findings=(),
        ),
    )


def bind_config(tmp_path: Path, algorithm: str = "ED25519") -> Path:
    zone = tmp_path / "alpha.db"
    zone.write_text("", encoding="utf-8")
    root = tmp_path / "named.conf"
    root.write_text(
        f'''dnssec-policy modern {{
  keys {{ csk lifetime unlimited algorithm {algorithm}; }};
}};
zone "alpha.example.test" {{
  type primary; file "{zone}"; dnssec-policy modern;
}};
''',
        encoding="utf-8",
    )
    return root


def test_text_report_is_read_only_and_independent_of_toolkit_config(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    mock_capabilities(monkeypatch)
    root = bind_config(tmp_path)
    assert main(["dnssec", "policies", "--root-config", str(root)]) == 0
    output = capsys.readouterr().out
    assert "POLITYKI DNSSEC/KASP" in output
    assert "[PASS] modern" in output
    assert "alpha.example.test" in output
    assert "niczego nie zmieniono" in output


def test_json_report_is_stable_and_allowlisted(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    mock_capabilities(monkeypatch)
    root = bind_config(tmp_path)
    assert main(["dnssec", "policies", "--root-config", str(root), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    modern = next(
        policy for policy in payload["policies"] if policy["name"] == "modern"
    )
    assert modern["keys"][0]["algorithm"] == "ED25519"
    assert set(modern) == {
        "name",
        "built_in",
        "keys",
        "inline_signing",
        "nsec3",
        "nsec3_iterations",
        "nsec3_optout",
        "timing",
        "cds_digest_types",
        "cdnskey",
        "offline_ksk",
        "status",
        "warnings",
        "zones",
        "bind_compatibility",
        "compatibility_findings",
    }
    assert payload["bind_capabilities"]["version"] == "9.20.26"


def test_blocked_policy_returns_nonzero(tmp_path: Path, capsys, monkeypatch) -> None:
    mock_capabilities(monkeypatch)
    root = bind_config(tmp_path, "RSASHA1")
    assert main(["dnssec", "policies", "--root-config", str(root)]) == 1
    assert "[BLOCKED] modern" in capsys.readouterr().out
