"""Shared helper functions for index repository operations.

This module provides helper functions used by both the index_repository use case
and CLI output formatting. Extracted to reduce duplication across the codebase.
"""
from typing import Any
from pathlib import Path

from meminit.core.services.path_utils import relative_path_string


def filter_index_edges(
    report: Any,
    *,
    status_filter: str | list[str] | None,
    impl_state_filter: str | list[str] | None,
) -> list[dict[str, Any]]:
    """Filter edges to only show relationships between visible documents.

    When filters are active, report.documents contains only the filtered nodes.
    This function ensures edges reference valid nodes (both source and target
    exist in the filtered document list).

    Args:
        report: Index build report containing documents and edges.
        status_filter: Optional status value(s) to filter nodes by.
        impl_state_filter: Optional impl_state value(s) to filter nodes by.

    Returns:
        List of edge dictionaries where both source and target nodes are in
        report.documents. Returns all edges if no filters are specified.
    """
    has_filter = status_filter is not None or impl_state_filter is not None
    if not has_filter:
        return list(report.edges)
    visible_ids = {n["document_id"] for n in report.documents}
    return [
        e for e in report.edges if e.get("source") in visible_ids and e.get("target") in visible_ids
    ]


def build_index_output_data(
    report: Any,
    root_path: Path,
    *,
    status_filter: str | list[str] | None = None,
    impl_state_filter: str | list[str] | None = None,
    filtered: bool | None = None,
) -> dict[str, Any]:
    """Build the data dict for index output (JSON, streaming, or CLI).

    Args:
        report: Index build report containing documents, edges, and paths.
        root_path: Repository root path for computing relative paths.
        status_filter: Optional status filter(s) passed to filter_index_edges.
        impl_state_filter: Optional impl_state filter(s) passed to filter_index_edges.
        filtered: If explicitly provided, use this value for the 'filtered' flag.
                    If None, compute from whether status_filter or impl_state_filter are set.

    Returns:
        Dictionary with index_path, node_count, edge_count, nodes, edges,
        filtered flag, rebuild mode, and optional catalog_path and kanban_path.
    """
    if filtered is None:
        display_edges = filter_index_edges(
            report, status_filter=status_filter, impl_state_filter=impl_state_filter
        )
        is_filtered = status_filter is not None or impl_state_filter is not None
    else:
        display_edges = report.edges
        is_filtered = filtered

    data: dict[str, Any] = {
        "index_path": relative_path_string(report.index_path, root_path),
        "node_count": report.document_count,
        "edge_count": len(display_edges),
        "nodes": report.documents,
        "edges": display_edges,
        "filtered": is_filtered,
        "rebuild": getattr(report, "rebuild", {"mode": "full"}),
    }
    if report.catalog_path:
        data["catalog_path"] = relative_path_string(report.catalog_path, root_path)
    if report.kanban_path:
        data["kanban_path"] = relative_path_string(report.kanban_path, root_path)
    return data