import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock
from meminit.core.use_cases.migrate_templates import MigrateTemplatesUseCase

def test_migrate_templates_empty_docs_root_v2(tmp_path: Path):
    # Setup config with empty docs_root
    (tmp_path / "docops.config.yaml").write_text("project_name: test\ndocs_root: ''\n")
    
    # Mock load_repo_layout to return a layout where default_namespace().docs_root is empty
    mock_layout = MagicMock()
    mock_ns = MagicMock()
    mock_ns.docs_root = ""
    mock_layout.default_namespace.return_value = mock_ns
    
    with patch("meminit.core.use_cases.migrate_templates.load_repo_layout", return_value=mock_layout):
        use_case = MigrateTemplatesUseCase(str(tmp_path))
        
        # self._docs_root should be empty string
        assert use_case._docs_root == ""

def test_migrate_templates_aborts_on_config_parse_failure(tmp_path: Path):
    # Setup config with invalid YAML
    (tmp_path / "docops.config.yaml").write_text("invalid: [yaml: broken")
    
    # Mock templates dir
    templates_dir = tmp_path / "docs" / "00-governance" / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "template-001-adr.md").write_text("content")
    
    use_case = MigrateTemplatesUseCase(str(tmp_path))
    
    # Execute should return success=False
    report = use_case.execute(migrate_templates=True, rename_files=True, dry_run=False)
    
    assert report.success is False
    assert any("Failed to parse config" in w for w in report.warnings)
    
    # Verify file was NOT renamed (because it aborted)
    assert (templates_dir / "template-001-adr.md").exists()
    assert not (templates_dir / "adr.template.md").exists()
