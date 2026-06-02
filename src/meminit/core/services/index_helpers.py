"""Shared helper functions for index repository operations.

This module provides helper functions used by both the index_repository use case
and CLI output formatting. Extracted to reduce duplication across the codebase.
"""
from typing import Any


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