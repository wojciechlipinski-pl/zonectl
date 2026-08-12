from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEBIAN = ROOT / "debian"


def test_required_debian_packaging_files_exist() -> None:
    required = {
        "changelog",
        "control",
        "copyright",
        "rules",
        "source/format",
        "zonectl.dirs",
        "zonectl.docs",
        "zonectl.manpages",
    }
    assert all((DEBIAN / name).is_file() for name in required)


def test_debian_version_matches_release() -> None:
    changelog = (DEBIAN / "changelog").read_text(encoding="utf-8")
    assert changelog.startswith("zonectl (4.7.0-1) ")


def test_bind_dependencies_use_supported_lower_bound_without_exact_pin() -> None:
    control = (DEBIAN / "control").read_text(encoding="utf-8")
    assert "bind9 (>= 1:9.20.0)" in control
    assert "bind9-utils (>= 1:9.20.0)" in control
    assert "bind9-dnsutils (>= 1:9.20.0)" in control
    assert "bind9 (= " not in control


def test_maintainer_uses_deliverable_email_address() -> None:
    control = (DEBIAN / "control").read_text(encoding="utf-8")
    changelog = (DEBIAN / "changelog").read_text(encoding="utf-8")
    email = "wojciech.lipinski.elk@gmail.com"
    assert email in control
    assert email in changelog
    assert "@localhost" not in control
    assert "@localhost" not in changelog


def test_package_installation_has_no_bind_maintainer_scripts() -> None:
    forbidden = ("preinst", "postinst", "prerm", "postrm")
    assert not any((DEBIAN / name).exists() for name in forbidden)


def test_package_does_not_own_transaction_backup_directories() -> None:
    directories = (DEBIAN / "zonectl.dirs").read_text(encoding="utf-8")
    assert "var/lib/zonectl" in directories
    assert "var/backups" not in directories


def test_rules_uses_pybuild() -> None:
    rules = (DEBIAN / "rules").read_text(encoding="utf-8")
    assert "--buildsystem=pybuild" in rules
    assert "PYBUILD_SYSTEM=pyproject" in rules
    assert "override_dh_auto_test:" in rules
    assert "PYTHONPATH=src python3 -m pytest -q" in rules


def test_package_exposes_only_zctl_entry_point() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    manpages = (DEBIAN / "zonectl.manpages").read_text(encoding="utf-8")
    assert 'zctl = "zonectl.cli:main"' in pyproject
    assert "elkman-dns =" not in pyproject
    assert "elkman-dns.1" not in manpages
