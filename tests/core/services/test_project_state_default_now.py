import pytest
from pathlib import Path
from datetime import datetime, timezone
import yaml
from meminit.core.services.project_state import load_project_state

def test_load_project_state_with_default_now(tmp_path: Path):
    # Setup test file
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    
    # State file missing the 'updated' field
    yaml_content = """
documents:
  DOC-001:
    impl_state: "In Progress"
    notes: "Some notes"
"""
    state_file.write_text(yaml_content)
    
    # Also need a dummy docops config so get_state_file_rel_path doesn't blow up if it tries to load config
    (tmp_path / "docops.config.yaml").write_text("project_name: test\n")
    
    # Run test
    default_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    
    state = load_project_state(tmp_path, default_now=default_time)
    
    assert state is not None
    assert len(state.schema_violations) == 0
    assert "DOC-001" in state.entries
    assert state.entries["DOC-001"].updated == default_time

def test_load_project_state_without_default_now_fails(tmp_path: Path):
    # Setup test file
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    
    # State file missing the 'updated' field
    yaml_content = """
documents:
  DOC-001:
    impl_state: "In Progress"
"""
    state_file.write_text(yaml_content)
    (tmp_path / "docops.config.yaml").write_text("project_name: test\n")
    
    # Run test without default_now
    state = load_project_state(tmp_path)
    
    assert state is not None
    assert len(state.schema_violations) == 1
    assert "missing or not a valid datetime" in state.schema_violations[0].message
