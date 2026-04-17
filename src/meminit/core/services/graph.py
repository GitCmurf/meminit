"""Graph extraction and validation for the repository index.

Provides edge extraction from frontmatter and markdown body links,
deduplication, deterministic sorting, and six graph integrity checks
that run during index build.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from meminit.core.domain.entities import Severity
from meminit.core.services.error_codes import ErrorCode
from meminit.core.services.validators import LinkChecker

# Reuse the same regex that LinkChecker uses for body-link extraction.
_LINK_REGEX = LinkChecker.LINK_REGEX


@dataclass(frozen=True)
class Edge:
    """A directed relationship between two document IDs."""

    source: str  # document_id of the referencing document
    target: str  # document_id of the referenced document
    edge_type: str  # "related" | "supersedes" | "references"

    def to_dict(self) -> Dict[str, str]:
        return {
            "source": self.source,
            "target": self.target,
            "edge_type": self.edge_type,
        }

    @staticmethod
    def sort_key(edge: Edge) -> Tuple[str, str, str]:
        return (edge.source, edge.target, edge.edge_type)


# ---------------------------------------------------------------------------
# Edge extraction
# ---------------------------------------------------------------------------


def extract_frontmatter_edges(
    doc_id: str,
    related_ids: Optional[Sequence[str]],
    superseded_by: Optional[str],
) -> List[Edge]:
    """Extract ``related`` and ``supersedes`` edges from frontmatter fields."""
    edges: List[Edge] = []

    if related_ids:
        for rid in related_ids:
            if isinstance(rid, str) and rid.strip() and rid.strip() != doc_id:
                edges.append(Edge(source=doc_id, target=rid.strip(), edge_type="related"))

    if superseded_by and isinstance(superseded_by, str) and superseded_by.strip():
        target = superseded_by.strip()
        if target != doc_id:
            edges.append(Edge(source=doc_id, target=target, edge_type="supersedes"))

    return edges


def extract_reference_edges(
    doc_id: str,
    source_path: Path,
    body: str,
    path_to_doc_id: Dict[str, str],
    root_dir: Path,
) -> List[Edge]:
    """Extract ``references`` edges from markdown body links.

    Uses the same regex as ``LinkChecker`` to find relative links, resolves
    them against the source file and root directory, and looks up the target
    in the path-to-document-ID map.
    """
    edges: List[Edge] = []
    seen_targets: Set[str] = set()
    source_dir = source_path.parent
    root_resolved = root_dir.resolve()

    for match in _LINK_REGEX.finditer(body):
        _, link_target = match.groups()

        lower_target = link_target.lower()
        if lower_target.startswith(("http://", "https://", "mailto:")) or link_target.startswith("#"):
            continue

        # Strip fragments.
        if "#" in link_target:
            link_target, _fragment = link_target.split("#", 1)
            if not link_target:
                continue

        # Resolve relative to source file, then normalise against root.
        try:
            resolved = (source_dir / link_target).resolve()
            rel = resolved.relative_to(root_resolved).as_posix()
        except (ValueError, OSError):
            continue

        target_id = path_to_doc_id.get(rel)
        if target_id and target_id != doc_id and target_id not in seen_targets:
            edges.append(Edge(source=doc_id, target=target_id, edge_type="references"))
            seen_targets.add(target_id)

    return edges


def deduplicate_edges(edges: List[Edge]) -> List[Edge]:
    """Remove duplicate edges (same source + target + edge_type)."""
    seen: set = set()
    result: List[Edge] = []
    for edge in edges:
        key = Edge.sort_key(edge)
        if key not in seen:
            seen.add(key)
            result.append(edge)
    return result


def sort_edges(edges: List[Edge]) -> List[Edge]:
    """Sort edges by ``(source, target, edge_type)`` for deterministic output."""
    return sorted(edges, key=Edge.sort_key)


def build_edge_set(
    entries: List[Dict[str, Any]],
    path_to_doc_id: Dict[str, str],
    root_dir: Path,
) -> List[Edge]:
    """Orchestrate the full edge extraction pipeline.

    1. Extract frontmatter edges (related + supersedes).
    2. Extract reference edges from markdown bodies.
    3. Deduplicate.
    4. Sort.
    """
    all_edges: List[Edge] = []

    for entry in entries:
        doc_id = entry.get("document_id", "")
        source_path = root_dir / entry.get("path", "")
        body = entry.get("_body", "")

        all_edges.extend(
            extract_frontmatter_edges(
                doc_id,
                entry.get("related_ids"),
                entry.get("superseded_by"),
            )
        )
        if body:
            all_edges.extend(
                extract_reference_edges(
                    doc_id,
                    source_path,
                    body,
                    path_to_doc_id,
                    root_dir,
                )
            )

    return sort_edges(deduplicate_edges(all_edges))


# ---------------------------------------------------------------------------
# Graph integrity validation
# ---------------------------------------------------------------------------


def _check_duplicate_document_ids(
    doc_id_paths: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    """GRAPH_DUPLICATE_DOCUMENT_ID: same document_id in multiple files."""
    errors: List[Dict[str, Any]] = []
    for doc_id, paths in sorted(doc_id_paths.items()):
        if len(paths) > 1:
            errors.append(
                {
                    "code": ErrorCode.GRAPH_DUPLICATE_DOCUMENT_ID.value,
                    "message": f"Duplicate document_id '{doc_id}' in: {', '.join(sorted(paths))}",
                    "severity": Severity.ERROR.value,
                    "path": paths[0],
                    "line": 0,
                }
            )
    return errors


def _check_supersession_cycle(
    edges: List[Edge],
) -> List[Dict[str, Any]]:
    """GRAPH_SUPERSESSION_CYCLE: supersession chain forms a cycle."""
    # Build adjacency list for supersedes edges only.
    adj: Dict[str, List[str]] = {}
    for edge in edges:
        if edge.edge_type == "supersedes":
            adj.setdefault(edge.source, []).append(edge.target)

    errors: List[Dict[str, Any]] = []
    visited: Set[str] = set()
    rec_stack: Set[str] = set()

    def _dfs(node: str, path: List[str]) -> None:
        visited.add(node)
        rec_stack.add(node)

        for neighbor in adj.get(node, []):
            if neighbor not in visited:
                _dfs(neighbor, path + [neighbor])
            elif neighbor in rec_stack:
                # Found cycle — extract the portion from the cycle start.
                cycle_start = path.index(neighbor) if neighbor in path else -1
                cycle = path[cycle_start:] + [neighbor]
                errors.append(
                    {
                        "code": ErrorCode.GRAPH_SUPERSESSION_CYCLE.value,
                        "message": f"Supersession cycle detected: {' -> '.join(cycle)}",
                        "severity": Severity.ERROR.value,
                        "path": "",
                        "line": 0,
                    }
                )

        rec_stack.discard(node)

    for node in sorted(adj):
        if node not in visited:
            _dfs(node, [node])

    return errors


def _check_dangling_targets(
    edges: List[Edge],
    known_doc_ids: Set[str],
) -> List[Dict[str, Any]]:
    """Dangling edge targets: related_ids or superseded_by pointing to unknown document IDs."""
    from meminit.core.services.warning_codes import WarningCode

    _CODE_MAP = {
        "related": WarningCode.W_GRAPH_DANGLING_RELATED_ID,
        "supersedes": WarningCode.W_GRAPH_DANGLING_SUPERSEDED_BY,
    }
    _FIELD_MAP = {
        "related": "related_ids",
        "supersedes": "superseded_by",
    }

    warnings: List[Dict[str, Any]] = []
    for edge in edges:
        if edge.edge_type in _CODE_MAP and edge.target not in known_doc_ids:
            warnings.append(
                {
                    "code": _CODE_MAP[edge.edge_type],
                    "message": f"{_FIELD_MAP[edge.edge_type]} target '{edge.target}' not found in index (declared by '{edge.source}')",
                    "severity": Severity.WARNING.value,
                    "path": "",
                    "line": 0,
                }
            )
    return warnings


def _check_supersession_status_mismatch(
    entries: List[Dict[str, Any]],
    edges: List[Edge],
) -> List[Dict[str, Any]]:
    """GRAPH_SUPERSESSION_STATUS_MISMATCH: superseded_by without Superseded status or vice versa."""
    from meminit.core.services.warning_codes import WarningCode

    # Build lookup: doc_id → set of supersedes edge targets (where doc_id is the source).
    has_supersedes_edge: Set[str] = set()
    for edge in edges:
        if edge.edge_type == "supersedes":
            has_supersedes_edge.add(edge.source)

    # Build lookup: doc_id → superseded_by value from frontmatter.
    has_superseded_by: Set[str] = set()
    for entry in entries:
        sb = entry.get("superseded_by")
        if sb and isinstance(sb, str) and sb.strip():
            has_superseded_by.add(entry["document_id"])

    warnings: List[Dict[str, Any]] = []

    for entry in entries:
        doc_id = entry["document_id"]
        status = (entry.get("status") or "").strip()
        has_sb = doc_id in has_superseded_by
        is_superseded = status.lower() == "superseded"

        if has_sb and not is_superseded:
            warnings.append(
                {
                    "code": WarningCode.W_GRAPH_SUPERSESSION_STATUS_MISMATCH,
                    "message": f"Document '{doc_id}' has superseded_by set but status is '{status}' (expected 'Superseded')",
                    "severity": Severity.WARNING.value,
                    "path": entry.get("path", ""),
                    "line": 0,
                }
            )
        elif is_superseded and not has_sb:
            warnings.append(
                {
                    "code": WarningCode.W_GRAPH_SUPERSESSION_STATUS_MISMATCH,
                    "message": f"Document '{doc_id}' has status 'Superseded' but no superseded_by field",
                    "severity": Severity.WARNING.value,
                    "path": entry.get("path", ""),
                    "line": 0,
                }
            )

    return warnings


def _check_related_id_asymmetry(
    edges: List[Edge],
) -> List[Dict[str, Any]]:
    """GRAPH_RELATED_ID_ASYMMETRY: A lists B in related_ids but B does not list A."""
    # Collect all related pairs.
    related_pairs: set = set()
    for edge in edges:
        if edge.edge_type == "related":
            related_pairs.add((edge.source, edge.target))

    advice: List[Dict[str, Any]] = []
    seen: set = set()

    for source, target in sorted(related_pairs):
        reverse = (target, source)
        if reverse not in related_pairs:
            key = tuple(sorted((source, target)))
            if key not in seen:
                seen.add(key)
                advice.append(
                    {
                        "code": "GRAPH_RELATED_ID_ASYMMETRY",
                        "message": f"'{source}' lists '{target}' in related_ids but '{target}' does not list '{source}'",
                    }
                )

    return advice


def validate_graph_integrity(
    entries: List[Dict[str, Any]],
    edges: List[Edge],
    known_doc_ids: Set[str],
    doc_id_paths: Dict[str, List[str]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Run all six graph integrity checks.

    Returns:
        (warnings, advice, errors) where:
        - warnings: non-fatal diagnostics for the warnings array
        - advice: informational diagnostics for the advice array
        - errors: fatal diagnostics — if non-empty, the caller should halt build
    """
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    advice: List[Dict[str, Any]] = []

    # Fatal checks.
    errors.extend(_check_duplicate_document_ids(doc_id_paths))
    errors.extend(_check_supersession_cycle(edges))

    # Non-fatal checks (only run if no fatal errors to avoid noise).
    if not errors:
        warnings.extend(_check_dangling_targets(edges, known_doc_ids))
        warnings.extend(_check_supersession_status_mismatch(entries, edges))
        advice.extend(_check_related_id_asymmetry(edges))

    return warnings, advice, errors
