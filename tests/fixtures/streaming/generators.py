from __future__ import annotations

import hashlib
from pathlib import Path
from random import Random


DOC_TYPES = [
    ("ADR", "45-adr", "Architectural Decision"),
    ("PRD", "10-prd", "Product Requirement"),
    ("SPEC", "20-specs", "Specification"),
    ("RUNBOOK", "60-runbooks", "Runbook"),
    ("PLAN", "05-planning", "Plan"),
]


def build_streaming_fixture(root: Path, *, count: int, seed: int = 14) -> None:
    """Create a deterministic governed-doc fixture tree."""
    docs_root = root / "docs"
    docs_root.mkdir(parents=True, exist_ok=True)
    (root / "docops.config.yaml").write_text(
        "project_name: Streaming Fixture\n"
        "repo_prefix: FIXTURE\n"
        "docops_version: '2.0'\n"
        "docs_root: docs\n",
        encoding="utf-8",
    )

    rng = Random(seed)
    for index in range(1, count + 1):
        doc_type, subdir, title_prefix = DOC_TYPES[(index - 1) % len(DOC_TYPES)]
        doc_id = f"FIXTURE-{doc_type}-{index:04d}"
        rel_ids = []
        if index > 1 and rng.random() < 0.35:
            previous_type = DOC_TYPES[(index - 2) % len(DOC_TYPES)][0]
            rel_ids.append(f"FIXTURE-{previous_type}-{index - 1:04d}")
        related = (
            "related_ids:\n"
            + "".join(f"  - {item}\n" for item in rel_ids)
            if rel_ids
            else "related_ids: []\n"
        )
        path = docs_root / subdir / f"{doc_type.lower()}-{index:04d}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n"
            f"document_id: {doc_id}\n"
            f"type: {doc_type}\n"
            f"title: {title_prefix} {index:04d}\n"
            "status: Draft\n"
            "version: '0.1'\n"
            "last_updated: '2026-05-06'\n"
            "owner: Fixture Team\n"
            "docops_version: '2.0'\n"
            "area: AGENT\n"
            "description: Deterministic streaming fixture document.\n"
            "keywords: [streaming, fixture]\n"
            f"{related}"
            "---\n\n"
            f"# {title_prefix} {index:04d}\n\n"
            "Fixture body for deterministic streaming and indexing tests.\n",
            encoding="utf-8",
        )


def tree_sha256(root: Path) -> str:
    """Return a stable hash for every file path and byte payload below root."""
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
