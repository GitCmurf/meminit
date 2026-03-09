import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from meminit.core.use_cases.migrate_templates import MigrateTemplatesUseCase
from meminit.core.services.repo_config import load_repo_layout

def test_migrate_templates_empty_docs_root(tmp_path: Path):
    (tmp_path / "docops.config.yaml").write_text("project_name: test\n")
    
    # Mock load_repo_layout to return a layout where default_namespace().docs_root is empty
    mock_layout = MagicMock()
    mock_ns = MagicMock()
    mock_ns.docs_root = ""
    mock_layout.default_namespace.return_value = mock_ns
    
    with patch("meminit.core.use_cases.migrate_templates.load_repo_layout", return_value=mock_layout):
        use_case = MigrateTemplatesUseCase(str(tmp_path))
        
        # The templates prefix should not have a leading slash
        assert use_case._templates_prefix == "00-governance/templates"

def test_migrate_templates_none_default_ns(tmp_path: Path):
    (tmp_path / "docops.config.yaml").write_text("project_name: test\n")
    
    # Mock load_repo_layout to return a layout where default_namespace() is None
    mock_layout = MagicMock()
    mock_layout.default_namespace.return_value = None
    
    # Provide config data
    config_data = {
        "templates": {"NEW_TYPE": "docs/00-governance/templates/new.template.md"},
        "document_types": {}
    }
    
    import yaml
    (tmp_path / "docops.config.yaml").write_text(yaml.dump(config_data))
    
    with patch("meminit.core.use_cases.migrate_templates.load_repo_layout", return_value=mock_layout):
        use_case = MigrateTemplatesUseCase(str(tmp_path))
        
        # Execute should not raise AttributeError
        report = use_case.execute(migrate_templates=True, rename_files=False, dry_run=True)
        
        # Check that it migrated without crashing
        assert report.config_entries_migrated >= 1
