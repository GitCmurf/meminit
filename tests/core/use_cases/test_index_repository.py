"""Tests for index_repository use case (PRD-007 Phase 2).

Covers: state merge, catalog/kanban generation, filtering, sanitization,
and backward compatibility for resolve/identify/link.
"""

import json
import time
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
{extra_frontmatter}---
# {doc_type}: {title}
{body}
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
    body: str = "",
    extra_frontmatter: str = "",
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
        extra_frontmatter=extra_frontmatter,
        body=body,
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
    assert payload["output_schema_version"] == "2.0"
    assert payload["data"]["nodes"][0]["document_id"] == "EXAMPLE-ADR-001"
    assert "run_id" not in payload
    assert "root" not in payload
    assert "generated_at" not in payload["data"]


def test_index_repository_persisted_json_is_stable_across_runs(tmp_path):
    """Persisted index excludes runtime metadata that would churn between runs."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    use_case = IndexRepositoryUseCase(str(tmp_path))

    first_report = use_case.execute()
    first_payload = json.loads(first_report.index_path.read_text(encoding="utf-8"))

    second_report = use_case.execute()
    second_payload = json.loads(second_report.index_path.read_text(encoding="utf-8"))

    assert first_payload == second_payload


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
    doc = payload["data"]["nodes"][0]
    assert doc["impl_state"] == "In Progress"
    assert doc["updated_by"] == "GitCmurf"
    assert doc["notes"] == "Phase 1"


def test_index_without_project_state(tmp_path):
    """Without state file, JSON has no impl_state fields."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")

    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    payload = json.loads(report.index_path.read_text(encoding="utf-8"))
    doc = payload["data"]["nodes"][0]
    assert "impl_state" not in doc
    assert "updated_by" not in doc


def test_index_derived_fields_always_emitted_without_state(tmp_path):
    """Documents without state entries still get derived fields, but are not ready."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")

    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    payload = json.loads(report.index_path.read_text(encoding="utf-8"))
    doc = payload["data"]["nodes"][0]
    assert doc["ready"] is False
    assert doc["open_blockers"] == []
    assert doc["unblocks"] == []


def test_index_derived_fields_mixed_state_and_no_state(tmp_path):
    """Index-only governed documents preserve incoming unblocks from tracked entries."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    _setup_doc(tmp_path, "EXAMPLE-ADR-002")
    _setup_state_file(tmp_path, {
        "EXAMPLE-ADR-001": {
            "impl_state": "Not Started",
            "updated": "2026-04-20T10:00:00+00:00",
            "updated_by": "test",
            "depends_on": ["EXAMPLE-ADR-002"],
        }
    })

    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    payload = json.loads(report.index_path.read_text(encoding="utf-8"))
    nodes = {n["document_id"]: n for n in payload["data"]["nodes"]}

    assert nodes["EXAMPLE-ADR-001"]["ready"] is False
    assert "EXAMPLE-ADR-002" in nodes["EXAMPLE-ADR-001"]["open_blockers"]

    assert nodes["EXAMPLE-ADR-002"]["ready"] is False
    assert nodes["EXAMPLE-ADR-002"]["open_blockers"] == []
    assert nodes["EXAMPLE-ADR-002"]["unblocks"] == ["EXAMPLE-ADR-001"]


# ---------------------------------------------------------------------------
# Catalog generation
# ---------------------------------------------------------------------------

def test_index_generates_catalog_md_by_default(tmp_path):
    """catalog.md is generated with --output-catalog by default."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001", title="First ADR", status="Draft")

    use_case = IndexRepositoryUseCase(str(tmp_path), output_catalog=True)
    report = use_case.execute()

    assert report.catalog_path is not None
    assert report.catalog_path.exists()
    assert report.catalog_path.name == "catalog.md"
    content = report.catalog_path.read_text(encoding="utf-8")
    assert "# Project Dashboard" in content
    assert "EXAMPLE-ADR-001" in content
    assert "First ADR" in content


def test_index_catalog_name_allows_catalog_md_override(tmp_path):
    """Users can override the default catalogue name."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001", title="First ADR", status="Draft")

    report = IndexRepositoryUseCase(
        str(tmp_path), output_catalog=True, catalog_name="catalog.md"
    ).execute()

    assert report.catalog_path is not None
    assert report.catalog_path.name == "catalog.md"
    assert report.catalog_path.exists()


def test_index_catalog_not_generated_without_flag(tmp_path):
    """catalogue.md is NOT generated without the flag."""
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
    ids = {d["document_id"] for d in payload["data"]["nodes"]}
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
    doc = payload["data"]["nodes"][0]
    # Existing required fields for downstream consumers.
    assert "document_id" in doc
    assert "path" in doc
    assert "type" in doc
    assert "title" in doc
    assert "status" in doc
    # Graph fields present in node entries.
    assert "area" in doc
    assert "keywords" in doc
    assert "related_ids" in doc
    assert "superseded_by" in doc


# ---------------------------------------------------------------------------
# Graph integration tests (Phase 2)
# ---------------------------------------------------------------------------


def test_index_generates_related_edges(tmp_path):
    """related_ids in frontmatter produces 'related' edges."""
    _setup_doc(
        tmp_path, "EXAMPLE-ADR-001",
        extra_frontmatter="related_ids:\n  - EXAMPLE-ADR-002\n",
    )
    _setup_doc(tmp_path, "EXAMPLE-ADR-002", filename="adr-002.md")

    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    payload = json.loads(report.index_path.read_text(encoding="utf-8"))
    related_edges = [e for e in payload["data"]["edges"] if e["edge_type"] == "related"]
    assert len(related_edges) == 1
    assert related_edges[0]["source"] == "EXAMPLE-ADR-001"
    assert related_edges[0]["target"] == "EXAMPLE-ADR-002"
    assert related_edges[0]["guaranteed"] is True
    assert related_edges[0]["context"] == "frontmatter.related_ids"


def test_index_generates_supersedes_edges(tmp_path):
    """superseded_by in frontmatter produces 'supersedes' edges."""
    _setup_doc(
        tmp_path, "EXAMPLE-ADR-001",
        status="Superseded",
        extra_frontmatter="superseded_by: EXAMPLE-ADR-002\n",
    )
    _setup_doc(tmp_path, "EXAMPLE-ADR-002", filename="adr-002.md")

    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    payload = json.loads(report.index_path.read_text(encoding="utf-8"))
    supersedes_edges = [e for e in payload["data"]["edges"] if e["edge_type"] == "supersedes"]
    assert len(supersedes_edges) == 1
    assert supersedes_edges[0]["source"] == "EXAMPLE-ADR-002"
    assert supersedes_edges[0]["target"] == "EXAMPLE-ADR-001"
    assert supersedes_edges[0]["guaranteed"] is True
    assert supersedes_edges[0]["context"] == "frontmatter.superseded_by"


def test_index_generates_reference_edges(tmp_path):
    """Body links to other governed docs produce 'references' edges."""
    _setup_doc(
        tmp_path, "EXAMPLE-ADR-001",
        body="See [ADR-002](adr-002.md) for details.",
    )
    _setup_doc(tmp_path, "EXAMPLE-ADR-002", filename="adr-002.md")

    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    payload = json.loads(report.index_path.read_text(encoding="utf-8"))
    ref_edges = [e for e in payload["data"]["edges"] if e["edge_type"] == "references"]
    assert len(ref_edges) == 1
    assert ref_edges[0]["source"] == "EXAMPLE-ADR-001"
    assert ref_edges[0]["target"] == "EXAMPLE-ADR-002"
    assert ref_edges[0]["guaranteed"] is False
    assert ref_edges[0]["context"] == "body.markdown_link"


def test_index_edges_sorted_deterministically(tmp_path):
    """Edges are sorted by (source, target, edge_type)."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001", extra_frontmatter="related_ids:\n  - EXAMPLE-ADR-003\n  - EXAMPLE-ADR-002\n")
    _setup_doc(tmp_path, "EXAMPLE-ADR-002", filename="adr-002.md", body="See [ADR 003](adr-003.md).")
    _setup_doc(tmp_path, "EXAMPLE-ADR-003", filename="adr-003.md")

    use_case = IndexRepositoryUseCase(str(tmp_path))
    use_case.execute()

    payload = json.loads(
        (tmp_path / "docs" / "01-indices" / "meminit.index.json").read_text(encoding="utf-8")
    )
    edge_keys = [(e["source"], e["target"], e["edge_type"]) for e in payload["data"]["edges"]]
    assert edge_keys == sorted(edge_keys)


def test_index_byte_identity(tmp_path):
    """Two index runs on same content produce byte-identical JSON."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001", title="Stable ADR")
    _setup_doc(tmp_path, "EXAMPLE-ADR-002", filename="adr-002.md", title="Other ADR")

    use_case = IndexRepositoryUseCase(str(tmp_path))
    first_report = use_case.execute()
    first_bytes = first_report.index_path.read_bytes()

    second_report = use_case.execute()
    second_bytes = second_report.index_path.read_bytes()

    assert first_bytes == second_bytes


def test_index_byte_identity_ignores_catalog_output_flags(tmp_path):
    """Persisted index bytes do not depend on catalog generation flags."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001", title="Stable ADR")

    base_report = IndexRepositoryUseCase(str(tmp_path)).execute()
    base_bytes = base_report.index_path.read_bytes()

    catalog_report = IndexRepositoryUseCase(
        str(tmp_path), output_catalog=True, catalog_name="review-catalog.md"
    ).execute()
    catalog_bytes = catalog_report.index_path.read_bytes()

    assert base_bytes == catalog_bytes
    assert catalog_report.catalog_path is not None
    assert catalog_report.catalog_path.name == "review-catalog.md"
    assert catalog_report.catalog_path.exists()


def test_index_canonicalizes_persisted_diagnostics(tmp_path, monkeypatch):
    """Persisted warnings/advice stay byte-identical across discovery-order changes."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001", title="Stable ADR")

    warning_a = {
        "message": "later warning",
        "code": "GRAPH_SUPERSESSION_STATUS_MISMATCH",
        "path": "docs/45-adr/b.md",
        "line": 9,
        "severity": "warning",
    }
    warning_b = {
        "severity": "warning",
        "message": "earlier warning",
        "code": "GRAPH_DANGLING_RELATED_ID",
        "line": None,
        "path": "docs/45-adr/a.md",
    }
    advice_a = {
        "message": "z advice",
        "code": "GRAPH_RELATED_ID_ASYMMETRY",
        "context": {"rhs": "EXAMPLE-ADR-002", "lhs": "EXAMPLE-ADR-001"},
    }
    advice_b = {
        "context": {"lhs": "EXAMPLE-ADR-003", "rhs": "EXAMPLE-ADR-004"},
        "code": "GRAPH_RELATED_ID_ASYMMETRY",
        "message": "a advice",
    }

    calls = {"count": 0}

    def fake_validate_graph_integrity(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] % 2 == 1:
            return ([warning_a, warning_b], [advice_a, advice_b], [])
        return ([warning_b, warning_a], [advice_b, advice_a], [])

    monkeypatch.setattr(
        "meminit.core.use_cases.index_repository.graph.validate_graph_integrity",
        fake_validate_graph_integrity,
    )

    use_case = IndexRepositoryUseCase(str(tmp_path))
    first_report = use_case.execute()
    first_bytes = first_report.index_path.read_bytes()

    second_report = use_case.execute()
    second_bytes = second_report.index_path.read_bytes()

    assert first_bytes == second_bytes

    payload = json.loads(second_report.index_path.read_text(encoding="utf-8"))
    assert payload["warnings"] == [
        {
            "code": "GRAPH_DANGLING_RELATED_ID",
            "message": "earlier warning",
            "path": "docs/45-adr/a.md",
            "severity": "warning",
        },
        {
            "code": "GRAPH_SUPERSESSION_STATUS_MISMATCH",
            "line": 9,
            "message": "later warning",
            "path": "docs/45-adr/b.md",
            "severity": "warning",
        },
    ]
    assert payload["advice"] == [
        {
            "code": "GRAPH_RELATED_ID_ASYMMETRY",
            "context": {"lhs": "EXAMPLE-ADR-003", "rhs": "EXAMPLE-ADR-004"},
            "message": "a advice",
        },
        {
            "code": "GRAPH_RELATED_ID_ASYMMETRY",
            "context": {"lhs": "EXAMPLE-ADR-001", "rhs": "EXAMPLE-ADR-002"},
            "message": "z advice",
        },
    ]


def test_index_fatal_on_duplicate_document_id(tmp_path):
    """Duplicate document_id across two files raises GRAPH_DUPLICATE_DOCUMENT_ID."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    _setup_doc(tmp_path, "EXAMPLE-ADR-001", filename="adr-duplicate.md")

    use_case = IndexRepositoryUseCase(str(tmp_path))
    with pytest.raises(MeminitError) as exc_info:
        use_case.execute()
    assert exc_info.value.code == ErrorCode.GRAPH_DUPLICATE_DOCUMENT_ID


def test_index_fatal_on_supersession_cycle(tmp_path):
    """Supersession cycle raises error and prevents artifact write."""
    _setup_doc(
        tmp_path, "EXAMPLE-ADR-001",
        status="Superseded",
        extra_frontmatter="superseded_by: EXAMPLE-ADR-002\n",
    )
    _setup_doc(
        tmp_path, "EXAMPLE-ADR-002",
        status="Superseded",
        filename="adr-002.md",
        extra_frontmatter="superseded_by: EXAMPLE-ADR-001\n",
    )

    use_case = IndexRepositoryUseCase(str(tmp_path))
    with pytest.raises(MeminitError) as exc_info:
        use_case.execute()
    assert exc_info.value.code == ErrorCode.GRAPH_SUPERSESSION_CYCLE


def test_index_fatal_on_self_referential_superseded_by(tmp_path):
    """Self-referential superseded_by produces a cycle error and invalidates the index."""
    _setup_doc(
        tmp_path, "EXAMPLE-ADR-001",
        status="Superseded",
        extra_frontmatter="superseded_by: EXAMPLE-ADR-001\n",
    )

    use_case = IndexRepositoryUseCase(str(tmp_path))
    with pytest.raises(MeminitError) as exc_info:
        use_case.execute()
    assert exc_info.value.code == ErrorCode.GRAPH_SUPERSESSION_CYCLE
    assert "EXAMPLE-ADR-001" in exc_info.value.message


def test_index_fatal_invalidates_stale_artifact(tmp_path):
    """Graph fatal errors remove all previously written generated artifacts."""
    # First, create a valid index with catalog (custom name), kanban, and user state.
    index_dir = tmp_path / "docs" / "01-indices"
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / "project-state.yaml").write_text(
        "documents:\n", encoding="utf-8",
    )
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    use_case = IndexRepositoryUseCase(
        str(tmp_path), output_catalog=True, catalog_name="review-catalog.md", output_kanban=True,
    )
    report = use_case.execute()
    index_dir = tmp_path / "docs" / "01-indices"
    assert report.index_path.exists()
    review_catalog = index_dir / "review-catalog.md"
    kanban_path = index_dir / "kanban.md"
    kanban_css_path = index_dir / "kanban.css"
    state_file = index_dir / "project-state.yaml"
    assert review_catalog.exists()
    assert kanban_path.exists()
    assert kanban_css_path.exists()

    # Now introduce a duplicate ID that triggers a fatal error (with default catalog name).
    _setup_doc(tmp_path, "EXAMPLE-ADR-001", filename="adr-dup.md")
    use_case2 = IndexRepositoryUseCase(
        str(tmp_path), output_catalog=True, catalog_name="catalog.md", output_kanban=True,
    )
    with pytest.raises(MeminitError) as exc_info:
        use_case2.execute()
    assert exc_info.value.code == ErrorCode.GRAPH_DUPLICATE_DOCUMENT_ID

    # All stale generated artifacts should be removed, but project-state.yaml must survive.
    assert not report.index_path.exists()
    assert not review_catalog.exists()
    assert not kanban_path.exists()
    assert not kanban_css_path.exists()
    assert state_file.exists()


def test_index_success_cleanup_removes_stale_generated_views(tmp_path):
    """Successful reruns remove obsolete generated views when output flags change."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    index_dir = tmp_path / "docs" / "01-indices"

    first_report = IndexRepositoryUseCase(
        str(tmp_path), output_catalog=True, catalog_name="review-catalog.md", output_kanban=True,
    ).execute()
    assert first_report.catalog_path is not None
    review_catalog = index_dir / "review-catalog.md"
    kanban_path = index_dir / "kanban.md"
    kanban_css_path = index_dir / "kanban.css"
    assert review_catalog.exists()
    assert kanban_path.exists()
    assert kanban_css_path.exists()

    second_report = IndexRepositoryUseCase(str(tmp_path)).execute()
    assert second_report.index_path.exists()
    assert second_report.catalog_path is None
    assert not review_catalog.exists()
    assert not kanban_path.exists()
    assert not kanban_css_path.exists()


def test_index_fatal_preserves_user_managed_files(tmp_path):
    """User-managed files (e.g. README.md) survive graph-fatal cleanup."""
    index_dir = tmp_path / "docs" / "01-indices"
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / "project-state.yaml").write_text(
        "documents:\n", encoding="utf-8",
    )
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    use_case = IndexRepositoryUseCase(
        str(tmp_path), output_catalog=True, catalog_name="catalog.md", output_kanban=True,
    )
    use_case.execute()

    # User adds a review notes file in the index directory.
    readme = index_dir / "README.md"
    readme.write_text("# Review notes\n", encoding="utf-8")
    assert readme.exists()

    # Introduce a duplicate ID to trigger graph fatal.
    _setup_doc(tmp_path, "EXAMPLE-ADR-001", filename="adr-dup.md")
    use_case2 = IndexRepositoryUseCase(str(tmp_path))
    with pytest.raises(MeminitError) as exc_info:
        use_case2.execute()
    assert exc_info.value.code == ErrorCode.GRAPH_DUPLICATE_DOCUMENT_ID

    # User-managed README.md must survive; only Meminit artifacts are removed.
    assert readme.exists()
    assert not (index_dir / "meminit.index.json").exists()
    assert not (index_dir / "kanban.md").exists()
    assert not (index_dir / "kanban.css").exists()
    assert not (index_dir / "catalog.md").exists()
    assert (index_dir / "project-state.yaml").exists()


def test_index_cleanup_removes_legacy_catalog_path_artifact(tmp_path):
    """Cleanup still removes old custom catalogs tracked only via legacy index metadata."""
    index_dir = tmp_path / "docs" / "01-indices"
    index_dir.mkdir(parents=True, exist_ok=True)
    legacy_catalog = index_dir / "legacy-catalog.md"
    legacy_catalog.write_text("# old catalog\n", encoding="utf-8")
    (index_dir / "meminit.index.json").write_text(
        json.dumps({"data": {"catalog_path": "legacy-catalog.md"}}),
        encoding="utf-8",
    )
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")

    report = IndexRepositoryUseCase(str(tmp_path)).execute()

    assert report.index_path.exists()
    assert not legacy_catalog.exists()


def test_index_fatal_cleanup_missing_file_no_mask(tmp_path):
    """Cleanup handles already-missing stale files without masking the graph error."""
    # Introduce a duplicate ID with no prior index files.
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    _setup_doc(tmp_path, "EXAMPLE-ADR-001", filename="adr-dup.md")

    use_case = IndexRepositoryUseCase(str(tmp_path))
    with pytest.raises(MeminitError) as exc_info:
        use_case.execute()
    assert exc_info.value.code == ErrorCode.GRAPH_DUPLICATE_DOCUMENT_ID


def test_index_warns_on_dangling_related(tmp_path):
    """Dangling related_ids target produces a warning."""
    _setup_doc(
        tmp_path, "EXAMPLE-ADR-001",
        extra_frontmatter="related_ids:\n  - EXAMPLE-ADR-999\n",
    )

    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    codes = [w["code"] for w in report.warnings]
    assert "GRAPH_DANGLING_RELATED_ID" in codes

    # Dangling edge is still emitted.
    payload = json.loads(report.index_path.read_text(encoding="utf-8"))
    dangling = [e for e in payload["data"]["edges"] if e["target"] == "EXAMPLE-ADR-999"]
    assert len(dangling) == 1


def test_index_warns_on_supersession_status_mismatch(tmp_path):
    """superseded_by without Superseded status produces a warning."""
    _setup_doc(
        tmp_path, "EXAMPLE-ADR-001",
        status="Draft",
        extra_frontmatter="superseded_by: EXAMPLE-ADR-002\n",
    )
    _setup_doc(tmp_path, "EXAMPLE-ADR-002", filename="adr-002.md")

    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    codes = [w["code"] for w in report.warnings]
    assert "GRAPH_SUPERSESSION_STATUS_MISMATCH" in codes


def test_index_advises_on_related_asymmetry(tmp_path):
    """Asymmetric related_ids produces advice."""
    _setup_doc(
        tmp_path, "EXAMPLE-ADR-001",
        extra_frontmatter="related_ids:\n  - EXAMPLE-ADR-002\n",
    )
    _setup_doc(tmp_path, "EXAMPLE-ADR-002", filename="adr-002.md")

    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    codes = [a["code"] for a in report.advice]
    assert "GRAPH_RELATED_ID_ASYMMETRY" in codes


def test_index_graph_schema_version(tmp_path):
    """Persisted index includes graph_schema_version."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    payload = json.loads(report.index_path.read_text(encoding="utf-8"))
    assert payload["data"]["index_version"] == "1.0"
    assert payload["data"]["graph_schema_version"] == "1.0"
    assert payload["data"]["node_count"] == 1
    assert payload["data"]["edge_count"] == 0
    assert "nodes" in payload["data"]
    assert "edges" in payload["data"]


@pytest.mark.slow
def test_index_handles_500_docs_within_phase_4_budget(tmp_path):
    """Phase 4 index build (scan + state merge + validation + derived fields)
    stays within the 30-second budget for 500 documents."""
    for i in range(500):
        _setup_doc(tmp_path, f"EXAMPLE-ADR-{i:03d}")

    use_case = IndexRepositoryUseCase(str(tmp_path))
    start = time.perf_counter()
    report = use_case.execute()
    elapsed = time.perf_counter() - start

    assert report.document_count == 500
    assert elapsed < 30, f"Index build exceeded Phase 4 budget: {elapsed:.2f}s"


# ---------------------------------------------------------------------------
# BV-C: Stored-XSS via priority in kanban class attribute
# ---------------------------------------------------------------------------

def test_index_kanban_priority_xss_is_sanitized_in_class_attribute(tmp_path):
    """A hand-edited priority with attribute-breaking chars must not escape
    the HTML class attribute in kanban cards (BV-C).

    The execute() gate drops invalid priorities, so a real XSS payload never
    reaches the kanban card. We test two layers:
    1. _safe_css_slug defence-in-depth (direct unit test).
    2. A valid priority (P0) renders with a safe slug in the kanban output.
    """
    assert _safe_css_slug('P0" onclick=alert(1) x="') == "p0-onclick-alert-1-x"
    assert '"' not in _safe_css_slug('P0" onclick=alert(1) x="')

    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    _setup_state_file(
        tmp_path,
        {
            "EXAMPLE-ADR-001": {
                "impl_state": "In Progress",
                "priority": "P0",
                "updated": "2026-03-05T10:00:00Z",
                "updated_by": "GitCmurf",
            }
        },
    )

    use_case = IndexRepositoryUseCase(str(tmp_path), output_kanban=True)
    report = use_case.execute()
    kanban_content = report.kanban_path.read_text(encoding="utf-8")

    assert "badge-priority-p0" in kanban_content
    assert 'onclick' not in kanban_content


def test_index_kanban_title_notes_xss_sanitized(tmp_path):
    """Title and notes with HTML-breaking chars are sanitized in kanban HTML cards."""
    _setup_doc(
        tmp_path, "EXAMPLE-ADR-001",
        title='test" onmouseover="alert(1)',
    )
    _setup_state_file(
        tmp_path,
        {
            "EXAMPLE-ADR-001": {
                "impl_state": "In Progress",
                "notes": '<script>alert("xss")</script>',
                "updated": "2026-03-05T10:00:00Z",
                "updated_by": "GitCmurf",
            }
        },
    )

    use_case = IndexRepositoryUseCase(str(tmp_path), output_kanban=True)
    report = use_case.execute()
    kanban_content = report.kanban_path.read_text(encoding="utf-8")

    start = kanban_content.find('<div class="kanban-board"')
    html_section = kanban_content[start:] if start >= 0 else kanban_content

    assert '<script>' not in html_section
    assert 'onmouseover="' not in html_section
    assert '&lt;script&gt;' in html_section
    assert '&quot;' in html_section


def test_index_invalid_priority_emits_warning_and_is_dropped(tmp_path):
    """Invalid priority values are dropped from the index and produce a
    STATE_INVALID_PRIORITY warning in the envelope (BV-C execute gate)."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    _setup_state_file(
        tmp_path,
        {
            "EXAMPLE-ADR-001": {
                "impl_state": "In Progress",
                "priority": "INVALID",
                "updated": "2026-03-05T10:00:00Z",
                "updated_by": "GitCmurf",
            }
        },
    )

    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    index_path = tmp_path / "docs" / "01-indices" / "meminit.index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))

    node = payload["data"]["nodes"][0]
    assert "priority" not in node, "Invalid priority should be dropped from index node"

    warning_codes = [w["code"] for w in payload.get("warnings", [])]
    assert "STATE_INVALID_PRIORITY" in warning_codes


def test_index_invalid_priority_single_warning(tmp_path):
    """Invalid priority produces exactly one STATE_INVALID_PRIORITY warning
    in the index envelope — validate_project_state is the sole emitter (AR-new-2)."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    _setup_state_file(
        tmp_path,
        {
            "EXAMPLE-ADR-001": {
                "impl_state": "In Progress",
                "priority": "INVALID",
                "updated": "2026-03-05T10:00:00Z",
                "updated_by": "GitCmurf",
            }
        },
    )

    use_case = IndexRepositoryUseCase(str(tmp_path))
    use_case.execute()

    index_path = tmp_path / "docs" / "01-indices" / "meminit.index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))

    priority_warnings = [
        w for w in payload.get("warnings", []) if w["code"] == "STATE_INVALID_PRIORITY"
    ]
    assert len(priority_warnings) == 1, (
        f"Expected exactly 1 STATE_INVALID_PRIORITY warning, "
        f"got {len(priority_warnings)}: {priority_warnings}"
    )


def test_index_excludes_invalid_priority_entries_before_deriving_readiness(tmp_path):
    """Readiness derivation must match state query handling for corrupted entries."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    _setup_doc(tmp_path, "EXAMPLE-ADR-002")
    _setup_state_file(
        tmp_path,
        {
            "EXAMPLE-ADR-001": {
                "impl_state": "Not Started",
                "priority": "P2",
                "depends_on": ["EXAMPLE-ADR-002"],
                "updated": "2026-03-05T10:00:00Z",
                "updated_by": "GitCmurf",
            },
            "EXAMPLE-ADR-002": {
                "impl_state": "Done",
                "priority": "P9",
                "updated": "2026-03-05T09:00:00Z",
                "updated_by": "GitCmurf",
            },
        },
    )

    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    payload = json.loads(report.index_path.read_text(encoding="utf-8"))
    nodes = {node["document_id"]: node for node in payload["data"]["nodes"]}

    assert nodes["EXAMPLE-ADR-001"]["ready"] is False
    assert nodes["EXAMPLE-ADR-001"]["open_blockers"] == ["EXAMPLE-ADR-002"]
    assert nodes["EXAMPLE-ADR-002"]["impl_state"] == "Done"
    assert nodes["EXAMPLE-ADR-002"]["ready"] is False
    assert nodes["EXAMPLE-ADR-002"]["open_blockers"] == []
    assert nodes["EXAMPLE-ADR-002"]["unblocks"] == ["EXAMPLE-ADR-001"]
    warning_codes = [w["code"] for w in payload.get("warnings", [])]
    assert "STATE_INVALID_PRIORITY" in warning_codes


def test_kanban_sort_key_oldest_first():
    """Older entries sort before newer ones (matches state next queue contract)."""
    from meminit.core.use_cases.index_repository import _kanban_sort_key
    newer = {"priority": "P2", "unblocks": [], "updated": "2026-04-20T12:00:00Z", "document_id": "A-001"}
    older = {"priority": "P2", "unblocks": [], "updated": "2026-04-19T12:00:00Z", "document_id": "A-002"}
    assert _kanban_sort_key(older) < _kanban_sort_key(newer)


def test_index_warns_on_undefined_dependency(tmp_path):
    """Dangling dependency in state produces STATE_UNDEFINED_DEPENDENCY warning."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    _setup_state_file(
        tmp_path,
        {
            "EXAMPLE-ADR-001": {
                "impl_state": "Not Started",
                "depends_on": ["EXAMPLE-ADR-999"],
                "updated": "2026-03-05T10:00:00Z",
                "updated_by": "test",
            }
        },
    )

    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    codes = [w["code"] for w in report.warnings]
    assert "STATE_UNDEFINED_DEPENDENCY" in codes


def test_index_includes_docs_from_nested_namespace(tmp_path):
    """Nested namespace documents are indexed after an outer namespace scan sees them."""
    (tmp_path / "docops.config.yaml").write_text(
        """
project_name: NestedNamespaces
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
namespaces:
  - name: root
    repo_prefix: MEMINIT
    docs_root: docs
  - name: org
    repo_prefix: ORG
    docs_root: docs/00-governance/org
""".lstrip(),
        encoding="utf-8",
    )
    _setup_doc(tmp_path, "MEMINIT-ADR-001", subdir="45-adr")
    _setup_doc(
        tmp_path,
        "ORG-GOV-001",
        doc_type="GOV",
        title="Org Governance",
        subdir="00-governance/org",
        filename="org-gov-001.md",
    )

    report = IndexRepositoryUseCase(str(tmp_path)).execute()

    ids = {doc["document_id"] for doc in report.documents}
    assert ids == {"MEMINIT-ADR-001", "ORG-GOV-001"}


def test_index_downgrades_planning_fatals_to_read_warnings(tmp_path):
    """Mutation-fatal planning issues are warning severity in index artifacts."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    _setup_state_file(
        tmp_path,
        {
            "EXAMPLE-ADR-001": {
                "impl_state": "Not Started",
                "depends_on": ["EXAMPLE-ADR-001", "not-a-doc-id"],
                "updated": "2026-03-05T10:00:00Z",
                "updated_by": "test",
            }
        },
    )

    use_case = IndexRepositoryUseCase(str(tmp_path))
    use_case.execute()

    index_path = tmp_path / "docs" / "01-indices" / "meminit.index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))

    planning_warnings = [
        w for w in payload.get("warnings", [])
        if w["code"] in {"STATE_SELF_DEPENDENCY", "STATE_INVALID_DEPENDENCY_ID"}
    ]
    assert {w["code"] for w in planning_warnings} == {
        "STATE_SELF_DEPENDENCY",
        "STATE_INVALID_DEPENDENCY_ID",
    }
    assert {w["severity"] for w in planning_warnings} == {"warning"}


def test_index_emits_status_conflict_advisory(tmp_path):
    """Done entry depending on non-Done entry emits advice, not warnings."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    _setup_doc(tmp_path, "EXAMPLE-ADR-002")
    _setup_state_file(
        tmp_path,
        {
            "EXAMPLE-ADR-001": {
                "impl_state": "Done",
                "depends_on": ["EXAMPLE-ADR-002"],
                "updated": "2026-03-05T10:00:00Z",
                "updated_by": "test",
            },
            "EXAMPLE-ADR-002": {
                "impl_state": "In Progress",
                "updated": "2026-03-05T10:00:00Z",
                "updated_by": "test",
            },
        },
    )

    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    index_path = tmp_path / "docs" / "01-indices" / "meminit.index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))

    conflicts = [
        a for a in payload.get("advice", [])
        if a["code"] == "STATE_DEPENDENCY_STATUS_CONFLICT"
    ]
    assert len(conflicts) == 1
    assert conflicts[0]["severity"] == "advisory"
    assert "STATE_DEPENDENCY_STATUS_CONFLICT" not in {
        w["code"] for w in payload.get("warnings", [])
    }
    assert "STATE_DEPENDENCY_STATUS_CONFLICT" in {
        a["code"] for a in report.advice
    }


def test_index_no_duplicate_field_too_long_warnings(tmp_path):
    """STATE_FIELD_TOO_LONG appears once, not duplicated from both validators."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")
    _setup_state_file(
        tmp_path,
        {
            "EXAMPLE-ADR-001": {
                "impl_state": "Not Started",
                "assignee": "x" * 500,
                "updated": "2026-03-05T10:00:00Z",
                "updated_by": "test",
            }
        },
    )

    use_case = IndexRepositoryUseCase(str(tmp_path))
    use_case.execute()

    index_path = tmp_path / "docs" / "01-indices" / "meminit.index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))

    field_too_long = [
        w for w in payload.get("warnings", [])
        if w["code"] == "STATE_FIELD_TOO_LONG"
    ]
    assert len(field_too_long) == 1
