import tempfile
from pathlib import Path

from meminit.core.use_cases.check_repository import CheckRepositoryUseCase


def run_debug():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        gov = repo / "docs" / "00-governance"
        gov.mkdir(parents=True)
        # Minimal schema requiring last_updated
        (gov / "metadata.schema.json").write_text(
            '{"type": "object", "required": ["last_updated"], "properties": {"document_id": {"type": "string"}, "last_updated": {"type": "string"}}}'
        )

        docs = repo / "docs" / "45-adr"
        docs.mkdir(parents=True)
        bad_file = docs / "Bad Name.md"
        bad_file.write_text(
            """---
document_id: MEMINIT-ADR-005
type: ADR
---
# Content
"""
        )

        checker = CheckRepositoryUseCase(str(repo))
        violations = checker.execute()

        print(f"Found {len(violations)} violations:")
        for v in violations:
            print(f"- Rule: {v.rule} | Msg: {v.message} | File: {v.file}")


if __name__ == "__main__":
    run_debug()
