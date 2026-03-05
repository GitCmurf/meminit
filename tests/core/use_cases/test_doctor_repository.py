from pathlib import Path

from meminit.core.use_cases.doctor_repository import DoctorRepositoryUseCase


def test_doctor_ok_when_schema_present(tmp_path: Path):
    (tmp_path / "docops.config.yaml").write_text(
        """project_name: Example
repo_prefix: EXAMPLE
docops_version: '2.0'
docs_root: docs
schema_path: docs/00-governance/metadata.schema.json
"""
    )
    gov = tmp_path / "docs" / "00-governance"
    gov.mkdir(parents=True)
    (gov / "metadata.schema.json").write_text('{"type":"object","properties":{}}')

    issues = DoctorRepositoryUseCase(str(tmp_path)).execute()
    assert not any(i.rule == "SCHEMA_MISSING" for i in issues)
    assert not any(i.rule == "SCHEMA_INVALID" for i in issues)


def test_doctor_errors_when_schema_missing(tmp_path: Path):
    (tmp_path / "docops.config.yaml").write_text(
        """project_name: Example
repo_prefix: EXAMPLE
docs_root: docs
schema_path: docs/00-governance/metadata.schema.json
"""
    )
    issues = DoctorRepositoryUseCase(str(tmp_path)).execute()
    assert any(i.rule == "SCHEMA_MISSING" for i in issues)


def test_doctor_errors_on_invalid_repo_prefix(tmp_path: Path):
    (tmp_path / "docops.config.yaml").write_text(
        """project_name: Example
repo_prefix: bad-prefix
docs_root: docs
schema_path: docs/00-governance/metadata.schema.json
"""
    )
    gov = tmp_path / "docs" / "00-governance"
    gov.mkdir(parents=True)
    (gov / "metadata.schema.json").write_text('{"type":"object","properties":{}}')

    issues = DoctorRepositoryUseCase(str(tmp_path)).execute()
    assert any(i.rule == "CONFIG_INVALID" for i in issues)


def test_doctor_validates_project_state_ok(tmp_path: Path):
    """PRD-007: Valid project-state.yaml emits no issues."""
    (tmp_path / "docops.config.yaml").write_text("repo_prefix: TST\ndocs_root: docs")
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs" / "TST-001.md").write_text("---\ndocument_id: TST-001\n---")
    
    state_dir = tmp_path / "docs" / "01-indices"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "project-state.yaml").write_text(
        "documents:\n  TST-001:\n    impl_state: Done\n"
    )
    issues = DoctorRepositoryUseCase(str(tmp_path)).execute()
    # We only care about state issues here
    assert not any(i.rule.startswith("E_STATE_") for i in issues)
    assert not any(i.rule.startswith("W_STATE_") for i in issues)


def test_doctor_emits_yaml_malformed_on_bad_state(tmp_path: Path):
    """PRD-007: Malformed project-state.yaml emits E_STATE_YAML_MALFORMED."""
    (tmp_path / "docops.config.yaml").write_text("repo_prefix: TST\ndocs_root: docs")
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs" / "TST-001.md").write_text("---\ndocument_id: TST-001\n---")
    
    state_dir = tmp_path / "docs" / "01-indices"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "project-state.yaml").write_text(
        "documents:\n  TST-001:\n    impl_state: [unclosed list\n\n"
    )
    issues = DoctorRepositoryUseCase(str(tmp_path)).execute()
    assert any(i.rule == "E_STATE_YAML_MALFORMED" for i in issues)


def test_doctor_emits_schema_violation_on_invalid_entry(tmp_path: Path):
    """PRD-007: Invalid state entry emits correct warning code."""
    (tmp_path / "docops.config.yaml").write_text("repo_prefix: TST\ndocs_root: docs")
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs" / "TST-001.md").write_text("---\ndocument_id: TST-001\n---")
    
    state_dir = tmp_path / "docs" / "01-indices"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "project-state.yaml").write_text(
        "documents:\n  TST-001:\n    impl_state: 123  # invalid enum value\n"
    )
    issues = DoctorRepositoryUseCase(str(tmp_path)).execute()
    assert any(i.rule == "E_STATE_SCHEMA_VIOLATION" for i in issues)
