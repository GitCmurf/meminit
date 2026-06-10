import os
from pathlib import Path

# Files that are allowed to contain legacy references for historical reasons (e.g. approved plans/PRDs)
EXCLUDED_FILES = {
    "docs/05-planning/plan-012-phase-3-detailed-implementation-plan.md",
    "docs/10-prd/prd-005-agent-interface-v2.md",
    "docs/10-prd/prd-008-greenfield-init.md",
}


def test_no_legacy_codex_paths():
    """P1-02: Scans src/, docs/, and root-level Markdown to verify no legacy '.codex/'
    path references exist (e.g. README advertising the legacy skill path)."""
    repo_root = Path(__file__).parent.parent
    src_dir = repo_root / "src"
    docs_dir = repo_root / "docs"

    violations = []
    pattern = ".codex/"

    # Collect the files to scan: everything under src/ and docs/, plus root-level
    # Markdown (README.md, etc.). Root Markdown is included so user-facing claims
    # don't drift back to the legacy path. We scope the path-style pattern to text
    # files; non-Markdown root files (e.g. .pre-commit-config.yaml's exclusion regex,
    # scripts referencing the `codex` CLI binary) are intentionally out of scope.
    files_to_scan: list[Path] = []
    for directory in [src_dir, docs_dir]:
        for root, dirs, files in os.walk(directory):
            # Skip build and metadata directories
            dirs[:] = [
                d for d in dirs if not d.endswith(".egg-info") and d not in ("build", "dist")
            ]
            files_to_scan.extend(Path(root) / file for file in files)
    files_to_scan.extend(sorted(repo_root.glob("*.md")))

    for file_path in files_to_scan:
        rel_path = file_path.relative_to(repo_root).as_posix()

        # Skip excluded files (future-projection design text only)
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

    assert not violations, (
        "Found legacy '.codex/' path references. "
        "After PLAN-016 remediation, only future-projection design text should reference .codex.\n"
        "Current exclusions are limited to historical approved documents.\n" + "\n".join(violations)
    )
