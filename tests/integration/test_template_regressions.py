import os
import pytest
from pathlib import Path
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
    result = runner.invoke(cli, [
        "new", "PRD", "Regression Test PRD", 
        "--owner", "Tester",
        "--description", "Testing for duplicate frontmatter"
    ])
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
    for i, line in enumerate(lines[second_dash_idx + 1:], second_dash_idx + 1):
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
    
    result = runner.invoke(cli, [
        "new", "FDD", "Regression Test FDD", 
        "--owner", "Tester"
    ])
    assert result.exit_code == 0
    
    fdd_path = tmp_path / "docs" / "50-fdd"
    files = list(fdd_path.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text()
    
    lines = content.splitlines()
    assert lines[0] == "---"
    second_dash_idx = lines.index("---", 1)
    for i, line in enumerate(lines[second_dash_idx + 1:], second_dash_idx + 1):
        if line.strip() == "---":
             pytest.fail(f"Possible duplicate frontmatter detected at line {i+1}: {line}")

    assert "{{document_id}}" not in content
    assert "Regression Test FDD" in content
