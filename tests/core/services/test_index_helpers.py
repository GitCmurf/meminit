"""Test index_helpers module."""
from pathlib import Path

import pytest

from meminit.core.services.index_helpers import build_index_output_data, filter_index_edges


def test_filter_index_edges_no_filter():
    """With no filters, all edges should be returned."""
    report = type(
        "Report",
        (),
        {
            "documents": [
                {"document_id": "DOC-001"},
                {"document_id": "DOC-002"},
            ],
            "edges": [
                {"source": "DOC-001", "target": "DOC-002"},
            ],
        },
    )()

    result = filter_index_edges(report, status_filter=None, impl_state_filter=None)
    assert len(result) == 1
    assert result[0] == {"source": "DOC-001", "target": "DOC-002"}


def test_filter_index_edges_with_status_filter():
    """With status filter, edges should only include nodes in filtered documents."""
    report = type(
        "Report",
        (),
        {
            "documents": [
                {"document_id": "DOC-001", "status": "Approved"},
            ],
            "edges": [
                {"source": "DOC-001", "target": "DOC-002"},
            ],
        },
    )()

    result = filter_index_edges(report, status_filter=["Approved"], impl_state_filter=None)
    assert len(result) == 0  # DOC-002 not in filtered documents


def test_filter_index_edges_with_impl_state_filter():
    """With impl_state filter, edges should only include nodes in filtered documents."""
    report = type(
        "Report",
        (),
        {
            "documents": [
                {"document_id": "DOC-001", "impl_state": "Done"},
                {"document_id": "DOC-002", "impl_state": "Done"},
            ],
            "edges": [
                {"source": "DOC-001", "target": "DOC-002"},
            ],
        },
    )()

    result = filter_index_edges(report, status_filter=None, impl_state_filter=["Done"])
    assert len(result) == 1


def test_filter_index_edges_edge_without_source():
    """Edge with missing source but target in documents should be included (no-filter path).

    When no filters are active, filter_index_edges returns all edges without
    validation. The function relies on upstream filtering of documents.
    """
    report = type(
        "Report",
        (),
        {
            "documents": [
                {"document_id": "DOC-001"},
            ],
            "edges": [
                {"target": "DOC-001"},
            ],
        },
    )()

    result = filter_index_edges(report, status_filter=None, impl_state_filter=None)
    assert len(result) == 1  # No-filter path returns all edges


def test_filter_index_edges_edge_without_target():
    """Edge with missing target but source in documents should be included (no-filter path).

    When no filters are active, filter_index_edges returns all edges without
    validation. The function relies on upstream filtering of documents.
    """
    report = type(
        "Report",
        (),
        {
            "documents": [
                {"document_id": "DOC-001"},
            ],
            "edges": [
                {"source": "DOC-001"},
            ],
        },
    )()

    result = filter_index_edges(report, status_filter=None, impl_state_filter=None)
    assert len(result) == 1  # No-filter path returns all edges


def test_filter_index_edges_empty_report():
    """Empty report should return empty edges."""
    report = type("Report", (), {"documents": [], "edges": []})()

    result = filter_index_edges(report, status_filter=None, impl_state_filter=None)
    assert len(result) == 0


def test_build_index_output_data_basic():
    """Basic data assembly without filters."""
    report = type(
        "Report",
        (),
        {
            "index_path": Path("/repo/index.json"),
            "document_count": 2,
            "catalog_path": Path("/repo/catalog.md"),
            "kanban_path": Path("/repo/kanban.md"),
            "documents": [{"document_id": "DOC-001"}, {"document_id": "DOC-002"}],
            "edges": [{"source": "DOC-001", "target": "DOC-002"}],
            "rebuild": {"mode": "full"},
        },
    )()

    result = build_index_output_data(report, Path("/repo"))
    assert result["node_count"] == 2
    assert result["edge_count"] == 1
    assert result["filtered"] is False
    assert result["rebuild"] == {"mode": "full"}
    assert "index_path" in result
    assert "catalog_path" in result
    assert "kanban_path" in result


def test_build_index_output_data_with_filter():
    """Data assembly with status filter should be marked as filtered."""
    report = type(
        "Report",
        (),
        {
            "index_path": Path("/repo/index.json"),
            "document_count": 1,
            "catalog_path": None,
            "kanban_path": None,
            "documents": [{"document_id": "DOC-001"}],
            "edges": [],
            "rebuild": {"mode": "incremental"},
        },
    )()

    result = build_index_output_data(report, Path("/repo"), status_filter=["Approved"])
    assert result["filtered"] is True
    assert result["edge_count"] == 0
    assert "catalog_path" not in result
    assert "kanban_path" not in result


def test_build_index_output_data_explicit_filtered():
    """filtered=True should use provided flag instead of computing from filters."""
    report = type(
        "Report",
        (),
        {
            "index_path": Path("/repo/index.json"),
            "document_count": 2,
            "catalog_path": None,
            "kanban_path": None,
            "documents": [{"document_id": "DOC-001"}, {"document_id": "DOC-002"}],
            "edges": [{"source": "DOC-001", "target": "DOC-002"}],
        },
    )()

    # Even with no filters, filtered=True is respected
    result = build_index_output_data(report, Path("/repo"), filtered=True)
    assert result["filtered"] is True
    # But no filtering happens when filtered is explicitly provided
    assert result["edge_count"] == 1