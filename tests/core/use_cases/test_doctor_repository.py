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
