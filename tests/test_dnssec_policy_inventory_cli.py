import json
from pathlib import Path

from zonectl.cli import main


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
    tmp_path: Path, capsys
) -> None:
    root = bind_config(tmp_path)
    assert main(["dnssec", "policies", "--root-config", str(root)]) == 0
    output = capsys.readouterr().out
    assert "POLITYKI DNSSEC/KASP" in output
    assert "[PASS] modern" in output
    assert "alpha.example.test" in output
    assert "niczego nie zmieniono" in output


def test_json_report_is_stable_and_allowlisted(tmp_path: Path, capsys) -> None:
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
    }


def test_blocked_policy_returns_nonzero(tmp_path: Path, capsys) -> None:
    root = bind_config(tmp_path, "RSASHA1")
    assert main(["dnssec", "policies", "--root-config", str(root)]) == 1
    assert "[BLOCKED] modern" in capsys.readouterr().out
