"""Tests for IndexViewService.

Tests the service layer responsible for generating index views (catalog, kanban).
"""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from meminit.core.services.index_view import IndexViewService


def test_catalog_frontmatter_structure():
    """Catalog frontmatter contains required governed fields."""
    generated_at = "2026-06-02T16:53:39Z"
    repo_prefix = "EXAMPLE"
    owner = "test-user"

    frontmatter = IndexViewService._catalog_frontmatter(generated_at, repo_prefix, owner)

    assert isinstance(frontmatter, list)
    assert frontmatter[0] == "---"
    assert f"document_id: {repo_prefix}-INDEX-001" in frontmatter
    assert "type: INDEX" in frontmatter
    assert "title: Project Dashboard" in frontmatter
    assert "status: Draft" in frontmatter
    assert 'version: "1.0"' in frontmatter
    assert "last_updated: 2026-06-02" in frontmatter
    assert f"owner: {owner}" in frontmatter
    assert 'docops_version: "2.0"' in frontmatter
    assert "---" in frontmatter[-2:]


def test_assign_group_superseded():
    """Superseded documents go to Superseded group."""
    assert IndexViewService._assign_group("Superseded", "Done") == "Superseded"
    assert IndexViewService._assign_group("Superseded", None) == "Superseded"


def test_assign_group_done():
    """Documents with impl_state='done' go to Done group."""
    assert IndexViewService._assign_group("Approved", "done") == "Done"
    assert IndexViewService._assign_group("Draft", "Done") == "Done"


def test_assign_group_active_work():
    """Active impl states go to Active Work group."""
    assert IndexViewService._assign_group("Draft", "In Progress") == "Active Work"
    assert IndexViewService._assign_group("Approved", "Blocked") == "Active Work"
    assert IndexViewService._assign_group("Approved", "QA Required") == "Active Work"
    assert IndexViewService._assign_group("Draft", "Not Started") == "Active Work"


def test_assign_group_governance_pending():
    """Draft and In Review status go to Governance Pending."""
    assert IndexViewService._assign_group("Draft", None) == "Governance Pending"
    assert IndexViewService._assign_group("In Review", None) == "Governance Pending"


def test_assign_group_reference():
    """Approved docs with no impl_state go to Reference."""
    assert IndexViewService._assign_group("Approved", None) == "Reference"


def test_activity_recency_with_frontmatter_datetime():
    """Activity recency uses frontmatter datetime when available."""
    fm_dt = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    state_dt = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)

    result = IndexViewService._activity_recency(fm_dt, state_dt)
    assert result == fm_dt


def test_activity_recency_with_state_updated():
    """Activity recency uses state.updated when frontmatter unavailable."""
    state_dt = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)

    result = IndexViewService._activity_recency(None, state_dt)
    assert result == state_dt


def test_activity_recency_with_none():
    """Activity recency returns datetime.min when both unavailable."""
    result = IndexViewService._activity_recency(None, None)
    assert result == datetime.min.replace(tzinfo=timezone.utc)


def test_format_md_table():
    """Markdown table formatting produces valid markdown."""
    headers = ["ID", "Title", "Status"]
    rows = [["A-001", "First", "Draft"], ["A-002", "Second", "Approved"]]

    result = IndexViewService._format_md_table(headers, rows)

    assert "| ID | Title | Status |" in result
    assert "| - | - | - |" in result
    assert "| A-001 | First | Draft |" in result
    assert "| A-002 | Second | Approved |" in result


def test_kanban_sort_key_priority_order():
    """Kanban sort key orders by priority first."""
    p1_entry = {
        "priority": "P1",
        "unblocks": [],
        "updated": "2026-04-20T12:00:00Z",
        "document_id": "A-001",
    }
    p2_entry = {
        "priority": "P2",
        "unblocks": [],
        "updated": "2026-04-20T12:00:00Z",
        "document_id": "A-002",
    }

    key1 = IndexViewService._kanban_sort_key(p1_entry)
    key2 = IndexViewService._kanban_sort_key(p2_entry)

    assert key1[0] < key2[0]


def test_kanban_sort_key_unblocks_count():
    """Kanban sort key prefers items that unblock others."""
    unblocks_entry = {
        "priority": "P2",
        "unblocks": ["A-003", "A-004"],
        "updated": "2026-04-20T12:00:00Z",
        "document_id": "A-001",
    }
    no_unblocks_entry = {
        "priority": "P2",
        "unblocks": [],
        "updated": "2026-04-20T12:00:00Z",
        "document_id": "A-002",
    }

    key1 = IndexViewService._kanban_sort_key(unblocks_entry)
    key2 = IndexViewService._kanban_sort_key(no_unblocks_entry)

    assert key1[1] < key2[1]


def test_kanban_badge_prefix():
    """Badge prefix includes priority and blocked status."""
    entry_with_priority = {"priority": "P0", "open_blockers": []}
    assert IndexViewService._kanban_badge_prefix(entry_with_priority) == "[P0] "

    entry_with_blockers = {"priority": None, "open_blockers": ["A-003"]}
    assert IndexViewService._kanban_badge_prefix(entry_with_blockers) == "[blocked] "

    entry_with_both = {"priority": "P1", "open_blockers": ["A-004"]}
    assert IndexViewService._kanban_badge_prefix(entry_with_both) == "[P1][blocked] "

    entry_empty = {"priority": None, "open_blockers": []}
    assert IndexViewService._kanban_badge_prefix(entry_empty) == ""


def test_safe_css_slug_removes_unsafe_chars():
    """CSS slug sanitization removes attribute-breaking characters."""
    assert (
        IndexViewService._safe_css_slug('Draft" onmouseover="alert(1)')
        == "draft-onmouseover-alert-1"
    )
    assert IndexViewService._safe_css_slug("  ") == "unknown"
    assert IndexViewService._safe_css_slug("Not Started") == "not-started"


def test_generate_catalog_includes_generated_marker():
    """Catalog includes MEMINIT_GENERATED marker."""
    entries = [
        {
            "document_id": "EXAMPLE-ADR-001",
            "type": "ADR",
            "title": "Test ADR",
            "status": "Draft",
            "impl_state": None,
            "priority": None,
            "ready": None,
            "owner": "Test",
            "_recency": datetime.now(timezone.utc),
        }
    ]
    generated_at = "2026-06-02T16:53:39Z"
    repo_prefix = "EXAMPLE"

    catalog = IndexViewService().generate_catalog(entries, generated_at, repo_prefix)

    assert "<!-- MEMINIT_GENERATED: catalog -->" in catalog
    assert "# Project Dashboard" in catalog


def test_generate_catalog_groups_documents():
    """Catalog groups documents by status/impl_state."""
    entries = [
        {
            "document_id": "EXAMPLE-ADR-001",
            "type": "ADR",
            "title": "Active ADR",
            "status": "Draft",
            "impl_state": "In Progress",
            "priority": "P1",
            "ready": True,
            "owner": "Test",
            "_recency": datetime.now(timezone.utc),
        },
        {
            "document_id": "EXAMPLE-ADR-002",
            "type": "ADR",
            "title": "Done ADR",
            "status": "Approved",
            "impl_state": "done",
            "priority": None,
            "ready": None,
            "owner": "Test",
            "_recency": datetime.now(timezone.utc),
        },
    ]
    generated_at = "2026-06-02T16:53:39Z"
    repo_prefix = "EXAMPLE"

    catalog = IndexViewService().generate_catalog(entries, generated_at, repo_prefix)

    assert "## Active Work" in catalog
    assert "## Done" in catalog
    assert "EXAMPLE-ADR-001" in catalog
    assert "EXAMPLE-ADR-002" in catalog


def test_kanban_header_includes_link_to_css():
    """Kanban header includes CSS stylesheet link."""
    project_name = "Test Project"
    generated_at = "2026-06-02T16:53:39Z"

    header_lines = IndexViewService._kanban_header(project_name, generated_at)
    header = "\n".join(header_lines)

    assert '<link rel="stylesheet" href="kanban.css">' in header
    assert f"# {project_name} Project Status Board" in header
    assert "meminit state" in header


def test_kanban_bucket_columns_by_impl_state():
    """Kanban buckets documents by impl_state."""
    entries = [
        {
            "document_id": "A-001",
            "impl_state": "In Progress",
            "priority": "P1",
            "unblocks": [],
            "updated": "2026-06-02T12:00:00Z",
        },
        {
            "document_id": "A-002",
            "impl_state": "Done",
            "priority": "P2",
            "unblocks": [],
            "updated": "2026-06-02T12:00:00Z",
        },
    ]

    service = IndexViewService()
    columns, ordered_columns = service._kanban_bucket_columns(entries)

    assert "In Progress" in columns
    assert "Done" in columns
    assert len(columns["In Progress"]) == 1
    assert len(columns["Done"]) == 1
    assert columns["In Progress"][0]["document_id"] == "A-001"
    assert columns["Done"][0]["document_id"] == "A-002"


def test_generate_kanban_includes_header():
    """Kanban generation includes header and fallback sections."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root_dir = Path(tmpdir)
        index_dir = root_dir / "docs" / "01-indices"
        index_dir.mkdir(parents=True)

        entries = [
            {
                "document_id": "EXAMPLE-ADR-001",
                "impl_state": "Not Started",
                "priority": "P2",
                "unblocks": [],
                "updated": "2026-06-02T12:00:00Z",
                "title": "Test ADR",
                "status": "Draft",
                "path": "docs/45-adr/001-test.md",
                "_raw_title": "Test ADR",
                "_raw_notes": None,
            }
        ]
        generated_at = "2026-06-02T16:53:39Z"
        project_name = "Test Project"

        kanban = IndexViewService().generate_kanban(
            entries, generated_at, project_name, root_dir, index_dir
        )

        assert "<!-- MEMINIT_GENERATED: kanban -->" in kanban
        assert "# Test Project Project Status Board" in kanban
        assert '<link rel="stylesheet" href="kanban.css">' in kanban
        assert "kanban-board" in kanban
        assert "kanban-fallback" in kanban


def test_get_kanban_css_returns_string():
    """get_kanban_css returns non-empty CSS string."""
    css = IndexViewService().get_kanban_css()

    assert isinstance(css, str)
    assert len(css) > 0
    assert ".kanban-board" in css
    assert ".kanban-card" in css
    assert "MEMINIT_GENERATED: kanban_css" in css
