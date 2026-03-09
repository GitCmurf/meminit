import pytest
from pathlib import Path
from meminit.core.use_cases.migrate_templates import MigrateTemplatesUseCase
from meminit.core.services.repo_config import load_repo_layout

def test_normalize_template_path_without_trailing_slash(tmp_path: Path):
    (tmp_path / "docops.config.yaml").write_text("project_name: test\n")
    use_case = MigrateTemplatesUseCase(str(tmp_path))
    
    # This should not strip docs/ and prepend docs/00-governance/templates/
    path = "docs/00-governance/templates"
    normalized = use_case._normalize_template_path(path)
    assert normalized == "docs/00-governance/templates"
    
    path_with_slash = "docs/00-governance/templates/"
    normalized_with_slash = use_case._normalize_template_path(path_with_slash)
    assert normalized_with_slash == "docs/00-governance/templates/"
    
    path_nested = "docs/00-governance/templates/adr.template.md"
    normalized_nested = use_case._normalize_template_path(path_nested)
    assert normalized_nested == "docs/00-governance/templates/adr.template.md"
    
    # Edge case: starts with docs/ but not the templates dir
    path_other = "docs/other_dir/adr.template.md"
    normalized_other = use_case._normalize_template_path(path_other)
    assert normalized_other == "docs/00-governance/templates/other_dir/adr.template.md"
