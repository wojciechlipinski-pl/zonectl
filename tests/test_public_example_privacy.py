from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PATHS = (
    ROOT / "CHANGELOG.md",
    ROOT / "README.md",
    ROOT / "README.pl.md",
    ROOT / "groups.yaml.example",
    ROOT / "docs",
    ROOT / "src",
    ROOT / "tests",
)
FORBIDDEN_NAMES = (
    "elk" "man.pl",
    ".elk" ".pl",
    "egosa" ".org",
    "xn--ek-xqa" ".pl",
)


def _public_text_files() -> list[Path]:
    files: list[Path] = []
    for path in PUBLIC_PATHS:
        if path.is_file():
            files.append(path)
            continue
        files.extend(
            candidate
            for candidate in path.rglob("*")
            if candidate.is_file()
            and candidate.name != Path(__file__).name
            and "__pycache__" not in candidate.parts
            and candidate.suffix in {".md", ".py", ".yaml", ".yml"}
        )
    return files


def test_public_materials_do_not_contain_production_dns_names() -> None:
    findings: list[str] = []
    for path in _public_text_files():
        text = path.read_text(encoding="utf-8", errors="replace").casefold()
        for forbidden in FORBIDDEN_NAMES:
            if forbidden in text:
                findings.append(f"{path.relative_to(ROOT)}: {forbidden}")
    assert not findings, "Production DNS names found:\n" + "\n".join(findings)
