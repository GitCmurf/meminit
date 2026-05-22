import os
from pathlib import Path

# Files that are allowed to contain legacy references for historical reasons (e.g. approved plans/PRDs)
EXCLUDED_FILES = {
    "docs/05-planning/plan-012-phase-3-detailed-implementation-plan.md",
    "docs/10-prd/prd-005-agent-interface-v2.md",
    "docs/10-prd/prd-008-greenfield-init.md",
    "docs/05-planning/plan-016-adoption-and-dogfooding-sequencing.md",
}


def test_no_legacy_codex_paths():
    """Scans src/ and docs/ to verify that no legacy '.codex/' path references exist."""
    repo_root = Path(__file__).parent.parent
    src_dir = repo_root / "src"
    docs_dir = repo_root / "docs"

    violations = []
    pattern = ".codex/"

    for directory in [src_dir, docs_dir]:
        for root, dirs, files in os.walk(directory):
            # Skip build and metadata directories
            dirs[:] = [
                d for d in dirs if not d.endswith(".egg-info") and d not in ("build", "dist")
            ]
            for file in files:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(repo_root).as_posix()

                # Skip excluded files
                if rel_path in EXCLUDED_FILES:
                    continue

                # Skip binary files or schema JSONs if not necessary, but scanning text files is best
                if file_path.suffix in [".png", ".jpg", ".jpeg", ".pyc"]:
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8")
                    if pattern in content:
                        # Find line number(s)
                        lines = content.splitlines()
                        for line_idx, line in enumerate(lines, 1):
                            if pattern in line:
                                violations.append(f"{rel_path}:{line_idx}: {line.strip()}")
                except Exception:
                    # Ignore decode errors for binary/unknown formats
                    pass

    assert not violations, f"Found legacy '.codex/' path references:\n" + "\n".join(violations)
