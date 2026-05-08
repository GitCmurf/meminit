from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from meminit.cli.main import cli


def create_initialized_repo(root: Path) -> None:
    result = CliRunner().invoke(cli, ["init", "--root", str(root), "--format", "json"])
    assert result.exit_code == 0, result.output
    write_doc(
        root,
        "docs/45-adr/adr-001-test.md",
        document_id="TEST-ADR-001",
        doc_type="ADR",
        title="Test ADR",
    )


def write_doc(
    root: Path,
    rel_path: str,
    *,
    document_id: str,
    doc_type: str,
    title: str,
) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"document_id: {document_id}\n"
        f"type: {doc_type}\n"
        f"title: {title}\n"
        "status: Draft\n"
        "version: '0.1'\n"
        "last_updated: '2026-05-03'\n"
        "owner: Test Team\n"
        "docops_version: '2.0'\n"
        "area: TEST\n"
        "description: Test document.\n"
        "keywords: [test]\n"
        "related_ids: []\n"
        "---\n\n"
        f"# {title}\n",
        encoding="utf-8",
    )


def records(output: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in output.splitlines() if line.strip()]


def normalize_stream(output: str) -> list[dict[str, Any]]:
    normalized = records(output)
    for record in normalized:
        record.pop("run_id", None)
        record.pop("started_at", None)
    return normalized
