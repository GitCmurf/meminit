"""Tests for index_repository use case (PRD-007 Phase 2).

Covers: state merge, catalog/kanban generation, filtering, sanitization,
and backward compatibility for resolve/identify/link.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.use_cases.index_repository import (
    IndexRepositoryUseCase,
    _safe_css_slug,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DOC_FRONTMATTER = """\
---
document_id: {doc_id}
type: {doc_type}
title: {title}
status: {status}
version: 0.1
last_updated: {last_updated}
owner: {owner}
docops_version: 2.0
---

# {doc_type}: {title}
"""


def _setup_doc(
    root: Path,
    doc_id: str,
    doc_type: str = "ADR",
    title: str = "Test Document",
    status: str = "Draft",
    owner: str = "Test",
    last_updated: str = "2025-12-21",
    subdir: str = "45-adr",
    filename: str | None = None,
) -> Path:
    """Create a governed document under docs/."""
    docs_dir = root / "docs" / subdir
    docs_dir.mkdir(parents=True, exist_ok=True)
    fname = filename or f"{doc_type.lower()}-{doc_id.split('-')[-1]}.md"
    doc_path = docs_dir / fname
    content = DOC_FRONTMATTER.format(
        doc_id=doc_id,
        doc_type=doc_type,
        title=title,
        status=status,
        last_updated=last_updated,
        owner=owner,
    )
    doc_path.write_text(content, encoding="utf-8")
    return doc_path


def _setup_state_file(root: Path, documents: dict) -> Path:
    """Create project-state.yaml under docs/01-indices/."""
    state_path = root / "docs" / "01-indices" / "project-state.yaml"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.dump({"documents": documents}, default_flow_style=False)
    state_path.write_text(content, encoding="utf-8")
    return state_path


# ---------------------------------------------------------------------------
# Basic backward compatibility
# ---------------------------------------------------------------------------

def test_index_repository_builds_index(tmp_path):
    """Existing behavior: builds JSON index with expected shape."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    assert report.document_count == 1
    index_path = tmp_path / "docs" / "01-indices" / "meminit.index.json"
    assert report.index_path == index_path
    text = index_path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    payload = json.loads(text)
    assert payload["output_schema_version"] == "1.0"  # Backward compat
    assert payload["documents"][0]["document_id"] == "EXAMPLE-ADR-001"


def test_index_repository_excludes_wip(tmp_path):
    """WIP files are excluded from the index."""
    docs_dir = tmp_path / "docs" / "45-adr"
    docs_dir.mkdir(parents=True, exist_ok=True)
    doc_path = docs_dir / "WIP-adr-002.md"
    doc_path.write_text(
        "---\n"
        "document_id: EXAMPLE-ADR-002\n"
        "type: ADR\n"
        "title: WIP\n"
        "status: Draft\n"
        "version: 0.1\n"
        "last_updated: 2025-12-21\n"
        "owner: Test\n"
        "docops_version: 2.0\n"
        "---\n\n"
        "# ADR: WIP\n",
        encoding="utf-8",
    )
    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()
    assert report.document_count == 0


# ---------------------------------------------------------------------------
# State merge
# ---------------------------------------------------------------------------

def test_index_merges_project_state(tmp_path):
    """When project-state.yaml exists, JSON includes impl_state fields."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    _setup_state_file(tmp_path, {
        "EXAMPLE-ADR-001": {
            "impl_state": "In Progress",
            "updated": "2026-03-05T10:00:00Z",
            "updated_by": "GitCmurf",
            "notes": "Phase 1",
        }
    })

    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    payload = json.loads(report.index_path.read_text(encoding="utf-8"))
    doc = payload["documents"][0]
    assert doc["impl_state"] == "In Progress"
    assert doc["updated_by"] == "GitCmurf"
    assert doc["notes"] == "Phase 1"


def test_index_without_project_state(tmp_path):
    """Without state file, JSON has no impl_state fields."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")

    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    payload = json.loads(report.index_path.read_text(encoding="utf-8"))
    doc = payload["documents"][0]
    assert "impl_state" not in doc
    assert "updated_by" not in doc


# ---------------------------------------------------------------------------
# Catalog generation
# ---------------------------------------------------------------------------

def test_index_generates_catalog_md(tmp_path):
    """catalog.md is generated with --output-catalog flag."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001", title="First ADR", status="Draft")

    use_case = IndexRepositoryUseCase(str(tmp_path), output_catalog=True)
    report = use_case.execute()

    assert report.catalog_path is not None
    assert report.catalog_path.exists()
    content = report.catalog_path.read_text(encoding="utf-8")
    assert "# Project Dashboard" in content
    assert "EXAMPLE-ADR-001" in content
    assert "First ADR" in content


def test_index_catalog_not_generated_without_flag(tmp_path):
    """catalog.md is NOT generated without the flag."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()
    assert report.catalog_path is None


# ---------------------------------------------------------------------------
# Kanban generation
# ---------------------------------------------------------------------------

def test_index_generates_kanban_md(tmp_path):
    """kanban.md + kanban.css are generated with --output-kanban flag."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    _setup_state_file(tmp_path, {
        "EXAMPLE-ADR-001": {
            "impl_state": "In Progress",
            "updated": "2026-03-05T10:00:00Z",
            "updated_by": "GitCmurf",
        }
    })

    use_case = IndexRepositoryUseCase(str(tmp_path), output_kanban=True)
    report = use_case.execute()

    assert report.kanban_path is not None
    assert report.kanban_path.exists()
    assert report.kanban_css_path is not None
    assert report.kanban_css_path.exists()

    kanban_content = report.kanban_path.read_text(encoding="utf-8")
    assert "Project Status Board" in kanban_content
    # Check pure markdown fallback
    assert '<div class="kanban-fallback">' in kanban_content
    assert "## In Progress" in kanban_content
    assert "- **EXAMPLE-ADR-001**" in kanban_content
    assert "</div>" in kanban_content
    # Check HTML board
    assert "kanban-board" in kanban_content

    css_content = report.kanban_css_path.read_text(encoding="utf-8")
    assert ".kanban-board" in css_content


def test_index_generates_kanban_with_custom_impl_state_column(tmp_path):
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    _setup_state_file(
        tmp_path,
        {
            "EXAMPLE-ADR-001": {
                "impl_state": "On Hold",
                "updated": "2026-03-05T10:00:00Z",
                "updated_by": "GitCmurf",
            }
        },
    )

    use_case = IndexRepositoryUseCase(str(tmp_path), output_kanban=True)
    report = use_case.execute()
    kanban_content = report.kanban_path.read_text(encoding="utf-8")

    assert "## On Hold" in kanban_content
    assert '<section class="kanban-column kanban-on-hold"' in kanban_content
    assert "- **EXAMPLE-ADR-001**" in kanban_content


def test_index_kanban_sanitizes_markdown_fallback_fields(tmp_path):
    _setup_doc(
        tmp_path,
        "EXAMPLE-ADR-001",
        title='<img src=x onerror=alert("x")>',
        status='<svg onload=alert("s")>',
    )
    _setup_state_file(
        tmp_path,
        {
            "EXAMPLE-ADR-001": {
                "impl_state": "In Progress",
                "updated": "2026-03-05T10:00:00Z",
                "updated_by": "GitCmurf",
                "notes": '<script>alert("n")</script>',
            }
        },
    )

    use_case = IndexRepositoryUseCase(str(tmp_path), output_kanban=True)
    report = use_case.execute()
    kanban_content = report.kanban_path.read_text(encoding="utf-8")

    assert "<img" not in kanban_content
    assert "<svg" not in kanban_content
    assert "<script>" not in kanban_content
    assert "&lt;img" in kanban_content
    assert "&lt;svg" in kanban_content
    assert "&lt;script&gt;" in kanban_content


def test_index_kanban_sanitizes_custom_impl_state_in_html(tmp_path):
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    _setup_state_file(
        tmp_path,
        {
            "EXAMPLE-ADR-001": {
                "impl_state": 'On Hold" autofocus onfocus="alert(1)',
                "updated": "2026-03-05T10:00:00Z",
                "updated_by": "GitCmurf",
            }
        },
    )

    use_case = IndexRepositoryUseCase(str(tmp_path), output_kanban=True)
    report = use_case.execute()
    kanban_content = report.kanban_path.read_text(encoding="utf-8")

    assert '<section class="kanban-column kanban-on-hold-autofocus-onfocus-alert-1"' in kanban_content
    assert 'aria-label="On Hold&quot; autofocus onfocus=&quot;alert(1)"' in kanban_content


def test_index_kanban_document_id_is_sanitized(tmp_path):
    _setup_doc(
        tmp_path,
        'MALICIOUS-ADR-<script>alert(1)</script>',
        title="Normal Title",
        filename="malicious-doc.md",
    )
    _setup_state_file(
        tmp_path,
        {
            'MALICIOUS-ADR-<script>alert(1)</script>': {
                "impl_state": "In Progress",
                "updated": "2026-03-05T10:00:00Z",
                "updated_by": "GitCmurf",
            }
        },
    )

    use_case = IndexRepositoryUseCase(str(tmp_path), output_kanban=True)
    report = use_case.execute()
    kanban_content = report.kanban_path.read_text(encoding="utf-8")

    assert "<script>" not in kanban_content
    assert "&lt;script&gt;" in kanban_content
    assert "MALICIOUS-ADR-" in kanban_content


def test_safe_css_slug_sanitizes_attribute_breaking_chars():
    """CSS slugs must remove unsafe characters."""
    assert _safe_css_slug('Draft" onmouseover="alert(1)') == "draft-onmouseover-alert-1"
    assert _safe_css_slug("  ") == "unknown"


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def test_index_filter_by_impl_state(tmp_path):
    """Filter by impl_state (case-insensitive)."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001", title="Active", status="Draft")
    _setup_doc(
        tmp_path, "EXAMPLE-ADR-002", title="Done",
        status="Approved", filename="adr-002.md",
    )
    _setup_state_file(tmp_path, {
        "EXAMPLE-ADR-001": {
            "impl_state": "In Progress",
            "updated": "2026-03-05T10:00:00Z",
            "updated_by": "test",
        },
        "EXAMPLE-ADR-002": {
            "impl_state": "Done",
            "updated": "2026-03-05T10:00:00Z",
            "updated_by": "test",
        },
    })

    use_case = IndexRepositoryUseCase(
        str(tmp_path), impl_state_filter="in progress"
    )
    report = use_case.execute()
    assert report.document_count == 1

    payload = json.loads(report.index_path.read_text(encoding="utf-8"))
    ids = {d["document_id"] for d in payload["documents"]}
    assert ids == {"EXAMPLE-ADR-001", "EXAMPLE-ADR-002"}


def test_index_filter_unknown_value_error(tmp_path):
    """Unknown filter value raises E_INVALID_FILTER_VALUE."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")

    with pytest.raises(MeminitError) as exc_info:
        IndexRepositoryUseCase(str(tmp_path), impl_state_filter="BogusState")

    assert exc_info.value.code == ErrorCode.E_INVALID_FILTER_VALUE


def test_index_filtered_catalog_header(tmp_path):
    """Filtered catalog includes filter info in header."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001", status="Draft")

    use_case = IndexRepositoryUseCase(
        str(tmp_path), output_catalog=True, status_filter="Draft"
    )
    report = use_case.execute()

    content = report.catalog_path.read_text(encoding="utf-8")
    assert "**Filters:**" in content
    assert "Draft" in content


# ---------------------------------------------------------------------------
# Sanitization
# ---------------------------------------------------------------------------

def test_index_sanitizes_html_in_catalog(tmp_path):
    """<script> in notes appears escaped in catalog output."""
    _setup_doc(
        tmp_path, "EXAMPLE-ADR-001", title="<script>xss</script>"
    )

    use_case = IndexRepositoryUseCase(str(tmp_path), output_catalog=True)
    report = use_case.execute()

    content = report.catalog_path.read_text(encoding="utf-8")
    # Title should not contain raw HTML tags in Markdown table.
    assert "<script>" not in content


# ---------------------------------------------------------------------------
# Backward compatibility: resolve/identify/link still work
# ---------------------------------------------------------------------------

def test_index_json_has_required_fields_for_resolve(tmp_path):
    """Index JSON has document_id + path for resolve/identify/link."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    _setup_state_file(tmp_path, {
        "EXAMPLE-ADR-001": {
            "impl_state": "Done",
            "updated": "2026-03-05T10:00:00Z",
            "updated_by": "test",
        }
    })

    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    payload = json.loads(report.index_path.read_text(encoding="utf-8"))
    doc = payload["documents"][0]
    # Existing required fields for downstream consumers.
    assert "document_id" in doc
    assert "path" in doc
    assert "type" in doc
    assert "title" in doc
    assert "status" in doc
