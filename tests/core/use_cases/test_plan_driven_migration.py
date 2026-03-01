import pytest
from pathlib import Path
import frontmatter

from meminit.core.services.repo_config import load_repo_layout
from meminit.core.use_cases.scan_repository import ScanRepositoryUseCase
from meminit.core.use_cases.fix_repository import FixRepositoryUseCase
from meminit.core.services.scan_plan import PlanActionType

def test_plan_driven_migration_e2e(tmp_path: Path):
    # Setup repo
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    
    # 1. Missing frontmatter file
    missing_fm = docs_dir / "adr-001.md"
    missing_fm.write_text("# This is an ADR\nSome content.", encoding="utf-8")
    
    # 2. Misnamed file in correct dir
    adrs_dir = docs_dir / "45-adr"
    adrs_dir.mkdir(parents=True, exist_ok=True)
    misnamed_adr = adrs_dir / "my_poorly named_adr.md"
    post = frontmatter.Post("Content", **{"type": "ADR", "title": "Poorly named", "owner": "GitCmurf", "status": "Draft", "version": "1.0", "docops_version": "2.0"})
    misnamed_adr.write_text(frontmatter.dumps(post), encoding="utf-8")
    
    # 3. Misplaced file 
    misplaced = docs_dir / "prds" / "prd-001.md"
    misplaced.parent.mkdir(parents=True, exist_ok=True)
    post2 = frontmatter.Post("Content", **{"type": "ADR", "title": "Wrong dir", "owner": "GitCmurf", "status": "Draft", "version": "1.0", "docops_version": "2.0"})
    misplaced.write_text(frontmatter.dumps(post2), encoding="utf-8")

    # Scan to generate plan
    scanner = ScanRepositoryUseCase(str(tmp_path))
    report = scanner.execute()
    
    plan = report.plan
    assert plan is not None
    assert len(plan.actions) >= 3
    
    actions_by_type = {}
    for a in plan.actions:
        actions_by_type.setdefault(a.action, []).append(a)
    
    # We should see INSERT_METADATA_BLOCK for adr-001
    assert PlanActionType.INSERT_METADATA_BLOCK in actions_by_type
    
    # We should see RENAME_FILE for my_poorly named_adr
    assert PlanActionType.RENAME_FILE in actions_by_type
    
    # We should see MOVE_FILE for the misplaced ADR
    assert PlanActionType.MOVE_FILE in actions_by_type
    
    # Apply plan
    fixer = FixRepositoryUseCase(str(tmp_path))
    fix_report = fixer.execute(dry_run=False, plan=plan)
    
    # We only care that the target files were fixed, we can ignore other global structural violations (like missing 00-governance layout)
    # The fix should not have failed.
    assert len(fix_report.fixed_violations) > 0
    
    # adr-001.md should now have frontmatter and be moved
    moved_missing = docs_dir / "45-adr" / "adr-001.md"
    updated_missing = frontmatter.load(moved_missing)
    assert updated_missing.metadata.get("type") == "ADR"
    assert updated_missing.metadata.get("title") == "This is an ADR"
    assert "document_id" in updated_missing.metadata
    
    # my_poorly named_adr.md should be renamed
    assert not misnamed_adr.exists()
    renamed = adrs_dir / "my-poorly-named-adr.md"
    assert renamed.exists()
    
    # misplaced should be moved
    assert not misplaced.exists()
    moved = adrs_dir / "prd-001.md"
    assert moved.exists()
