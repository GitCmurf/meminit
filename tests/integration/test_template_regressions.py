import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from meminit.cli.main import cli


def test_new_template_frontmatter_regression(tmp_path, monkeypatch):
    """
    Test that 'meminit new' correctly renders built-in templates (PRD, FDD)
    without duplicate frontmatter blocks or literal {{...}} tokens in output.
    """
    # Initialize a dummy repo
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    # 1. Initialize
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0

    # 2. Create a PRD
    result = runner.invoke(
        cli,
        [
            "new",
            "PRD",
            "Regression Test PRD",
            "--owner",
            "Tester",
            "--description",
            "Testing for duplicate frontmatter",
        ],
    )
    assert result.exit_code == 0

    # Find the created file
    prd_path = tmp_path / "docs" / "10-prd"
    files = list(prd_path.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text()

    # Check for regressions
    # - Should NOT have duplicate frontmatter markers (check literal start and middle)
    # A correct doc has exactly two '---' lines at the top.
    lines = content.splitlines()
    assert lines[0] == "---"

    # Find the second '---'
    try:
        second_dash_idx = lines.index("---", 1)
    except ValueError:
        pytest.fail("Second frontmatter separator '---' not found")

    # There should NOT be a third '---' line (as a standalone line)
    # until we hit tables or other content.
    for i, line in enumerate(lines[second_dash_idx + 1 :], second_dash_idx + 1):
        if line.strip() == "---":
            pytest.fail(f"Possible duplicate frontmatter detected at line {i+1}: {line}")

    # - Should NOT have literal { { variable } } or {{variable}} in metadata
    assert "{{document_id}}" not in content
    assert "{ { document_id } }" not in content
    assert "{{title}}" not in content
    assert "{{owner}}" not in content
    assert "Regression Test PRD" in content
    assert "Tester" in content


def test_new_fdd_interpolation(tmp_path, monkeypatch):
    """Verify FDD template interpolation as well."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    result_init = runner.invoke(cli, ["init"])
    assert result_init.exit_code == 0

    result = runner.invoke(cli, ["new", "FDD", "Regression Test FDD", "--owner", "Tester"])
    assert result.exit_code == 0

    fdd_path = tmp_path / "docs" / "50-fdd"
    files = list(fdd_path.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text()

    lines = content.splitlines()
    assert lines[0] == "---"
    try:
        second_dash_idx = lines.index("---", 1)
    except ValueError:
        pytest.fail("Second frontmatter separator '---' not found")
    for i, line in enumerate(lines[second_dash_idx + 1 :], second_dash_idx + 1):
        if line.strip() == "---":
            pytest.fail(f"Possible duplicate frontmatter detected at line {i+1}: {line}")

    assert "{{document_id}}" not in content
    assert "Regression Test FDD" in content


def test_template_placeholder_syntax_regression(tmp_path, monkeypatch):
    """
    Regression test: templates should use {{variable}} syntax, not { { variable } }.
    This ensures malformed placeholders are not introduced in future template edits.
    """
    from meminit.core.services.repo_config import load_repo_config

    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    result_init = runner.invoke(cli, ["init"])
    assert result_init.exit_code == 0

    repo_config = load_repo_config(str(tmp_path))

    launch_critical_types = ["ADR", "PRD", "FDD", "PLAN", "SPEC", "RUNBOOK", "DESIGN", "LOG", "TASK"]

    for doc_type in launch_critical_types:
        type_config = repo_config.document_types.get(doc_type)
        if not type_config:
            continue

        template_path = None
        if hasattr(type_config, "template") and type_config.template:
            template_path = tmp_path / type_config.template

        if not template_path or not template_path.exists():
            continue

        content = template_path.read_text(encoding="utf-8")

        frontmatter_end = content.find("\n---\n")
        if frontmatter_end == -1:
            continue

        frontmatter = content[:frontmatter_end]

        assert "{ { " not in frontmatter, (
            f"Template for {doc_type} at {template_path} contains malformed "
            "placeholder syntax with spaces. Use '{{variable}}' instead."
        )

        assert "} }" not in frontmatter, (
            f"Template for {doc_type} at {template_path} contains malformed "
            "placeholder syntax with spaces. Use '{{variable}}' instead."
        )
