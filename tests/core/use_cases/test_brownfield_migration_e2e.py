from pathlib import Path

import pytest

from meminit.core.use_cases.check_repository import CheckRepositoryUseCase
from meminit.core.use_cases.fix_repository import FixRepositoryUseCase
from meminit.core.use_cases.scan_repository import ScanRepositoryUseCase


def test_brownfield_migration_flow_scan_fix_check(tmp_path: Path):
    """
    End-to-end brownfield confidence test:
    - repo has existing docs in a nonstandard ADR directory (docs/adrs)
    - one file has no frontmatter and a noncompliant filename
    - scan suggests mapping
    - fix can remediate mechanical issues
    - check is green afterwards
    """
    # Brownfield docs layout
    adrs_dir = tmp_path / "docs" / "adrs"
    adrs_dir.mkdir(parents=True)

    # minimal schema/config to operate
    (tmp_path / "docs" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs" / "00-governance" / "metadata.schema.json").write_text(
        """{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["document_id","type","title","status","version","last_updated","owner","docops_version"],
  "properties": {
    "document_id": { "type": "string" },
    "type": { "type": "string" },
    "title": { "type": "string" },
    "status": { "type": "string" },
    "version": { "type": "string" },
    "last_updated": { "type": "string" },
    "owner": { "type": "string" },
    "docops_version": { "type": "string" }
  },
  "additionalProperties": true
}""",
        encoding="utf-8",
    )

    (tmp_path / "docops.config.yaml").write_text(
        """project_name: Example
repo_prefix: EXAMPLE
docops_version: '2.0'
docs_root: docs
schema_path: docs/00-governance/metadata.schema.json
type_directories:
  ADR: adrs
""",
        encoding="utf-8",
    )

    # Brownfield doc: missing frontmatter and bad filename
    (adrs_dir / "Bad_Name.md").write_text("# ADR: Brownfield decision\n\nBody.\n", encoding="utf-8")

    # Scan should not propose ADR override (already configured)
    scan = ScanRepositoryUseCase(str(tmp_path)).execute()
    assert scan.docs_root == "docs"
    assert "ADR" not in scan.suggested_type_directories

    # Fix should remediate
    fix = FixRepositoryUseCase(str(tmp_path))
    report = fix.execute(dry_run=False)
    assert report is not None

    # Final check should be green
    violations = CheckRepositoryUseCase(root_dir=str(tmp_path)).execute()
    assert violations == []
