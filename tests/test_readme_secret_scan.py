import re
from pathlib import Path

AWS_ACCESS_KEY_PATTERN = re.compile(
    r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}"
)


def test_readme_does_not_include_aws_access_key_samples():
    readme = Path(__file__).resolve().parent.parent / "README.md"
    content = readme.read_text(encoding="utf-8")

    assert AWS_ACCESS_KEY_PATTERN.search(content) is None


def test_readme_describes_meminit_instead_of_gitleaks():
    readme = Path(__file__).resolve().parent.parent / "README.md"
    content = readme.read_text(encoding="utf-8")

    assert content.lstrip().startswith("# Meminit")
    assert "gitleaks" not in content.lower()
