"""Tests for graph extraction and validation (Phase 2)."""

from pathlib import Path

import pytest

from meminit.core.services.graph import (
    Edge,
    build_edge_set,
    deduplicate_edges,
    extract_frontmatter_edges,
    extract_reference_edges,
    sort_edges,
    validate_graph_integrity,
)


# ---------------------------------------------------------------------------
# Edge extraction
# ---------------------------------------------------------------------------


class TestExtractFrontmatterEdges:
    def test_related_ids_produces_directed_edges(self):
        edges = extract_frontmatter_edges(
            "REPO-ADR-001",
            related_ids=["REPO-PRD-001", "REPO-ADR-002"],
            superseded_by=None,
        )
        assert len(edges) == 2
        assert edges[0] == Edge(source="REPO-ADR-001", target="REPO-PRD-001", edge_type="related", context="frontmatter.related_ids")
        assert edges[1] == Edge(source="REPO-ADR-001", target="REPO-ADR-002", edge_type="related", context="frontmatter.related_ids")

    def test_superseded_by_produces_supersedes_edge(self):
        edges = extract_frontmatter_edges(
            "REPO-ADR-002",
            related_ids=None,
            superseded_by="REPO-ADR-003",
        )
        assert len(edges) == 1
        assert edges[0] == Edge(source="REPO-ADR-003", target="REPO-ADR-002", edge_type="supersedes", context="frontmatter.superseded_by")

    def test_no_fields_produces_empty_list(self):
        edges = extract_frontmatter_edges("REPO-ADR-001", related_ids=None, superseded_by=None)
        assert edges == []

    def test_empty_related_ids_produces_empty_list(self):
        edges = extract_frontmatter_edges("REPO-ADR-001", related_ids=[], superseded_by=None)
        assert edges == []

    def test_self_reference_related_skipped(self):
        edges = extract_frontmatter_edges(
            "REPO-ADR-001",
            related_ids=["REPO-ADR-001"],
            superseded_by=None,
        )
        assert edges == []

    def test_self_reference_superseded_by_creates_edge(self):
        """Self-referential superseded_by creates an edge (cycle detection catches it)."""
        edges = extract_frontmatter_edges(
            "REPO-ADR-001",
            related_ids=None,
            superseded_by="REPO-ADR-001",
        )
        assert len(edges) == 1
        assert edges[0] == Edge(source="REPO-ADR-001", target="REPO-ADR-001", edge_type="supersedes", context="frontmatter.superseded_by")

    def test_non_string_related_ids_filtered(self):
        edges = extract_frontmatter_edges(
            "REPO-ADR-001",
            related_ids=["REPO-PRD-001", 123, None, ""],
            superseded_by=None,
        )
        assert len(edges) == 1
        assert edges[0].target == "REPO-PRD-001"


class TestExtractReferenceEdges:
    def test_resolves_body_link_to_known_doc(self):
        root = Path("/repo")
        path_to_doc_id = {"docs/45-adr/adr-002.md": "REPO-ADR-002"}
        body = "See [ADR-002](../45-adr/adr-002.md) for details."
        edges = extract_reference_edges(
            "REPO-ADR-001", root / "docs/10-prd/prd-001.md", body, path_to_doc_id, root,
        )
        assert len(edges) == 1
        assert edges[0] == Edge(source="REPO-ADR-001", target="REPO-ADR-002", edge_type="references", guaranteed=False, context="body.markdown_link")

    def test_ignores_external_links(self):
        root = Path("/repo")
        body = "See [external](https://example.com) and [mail](mailto:a@b.com)."
        edges = extract_reference_edges(
            "REPO-ADR-001", root / "docs/45-adr/adr-001.md", body, {}, root,
        )
        assert edges == []

    def test_ignores_anchor_only_links(self):
        root = Path("/repo")
        body = "See [section](#overview)."
        edges = extract_reference_edges(
            "REPO-ADR-001", root / "docs/45-adr/adr-001.md", body, {}, root,
        )
        assert edges == []

    def test_strips_fragment_from_link(self):
        root = Path("/repo")
        path_to_doc_id = {"docs/45-adr/adr-002.md": "REPO-ADR-002"}
        body = "See [link](../45-adr/adr-002.md#section)."
        edges = extract_reference_edges(
            "REPO-ADR-001", root / "docs/10-prd/prd-001.md", body, path_to_doc_id, root,
        )
        assert len(edges) == 1
        assert edges[0].target == "REPO-ADR-002"

    def test_deduplicates_same_target(self):
        root = Path("/repo")
        path_to_doc_id = {"docs/45-adr/adr-002.md": "REPO-ADR-002"}
        body = "See [A](../45-adr/adr-002.md) and [B](../45-adr/adr-002.md)."
        edges = extract_reference_edges(
            "REPO-ADR-001", root / "docs/10-prd/prd-001.md", body, path_to_doc_id, root,
        )
        assert len(edges) == 1

    def test_unknown_target_skipped(self):
        root = Path("/repo")
        body = "See [unknown](../45-adr/adr-999.md)."
        edges = extract_reference_edges(
            "REPO-ADR-001", root / "docs/45-adr/adr-001.md", body, {}, root,
        )
        assert edges == []

    def test_self_reference_skipped(self):
        root = Path("/repo")
        path_to_doc_id = {"docs/45-adr/adr-001.md": "REPO-ADR-001"}
        body = "See [self](adr-001.md)."
        edges = extract_reference_edges(
            "REPO-ADR-001", root / "docs/45-adr/adr-001.md", body, path_to_doc_id, root,
        )
        assert edges == []


class TestDeduplicateEdges:
    def test_removes_exact_duplicates(self):
        edges = [
            Edge("A", "B", "related"),
            Edge("A", "B", "related"),
        ]
        assert deduplicate_edges(edges) == [Edge("A", "B", "related")]

    def test_preserves_distinct_edge_types(self):
        edges = [
            Edge("A", "B", "related"),
            Edge("A", "B", "references"),
        ]
        result = deduplicate_edges(edges)
        assert len(result) == 2

    def test_merges_duplicate_logical_edge_with_strongest_provenance(self):
        edges = [
            Edge("A", "B", "related", guaranteed=False, context="body.markdown_link"),
            Edge("A", "B", "related", guaranteed=True, context="frontmatter.related_ids"),
        ]
        result = deduplicate_edges(edges)
        assert result == [
            Edge("A", "B", "related", guaranteed=True, context="frontmatter.related_ids")
        ]


class TestSortEdges:
    def test_sorted_by_source_target_type(self):
        edges = [
            Edge("C", "A", "related"),
            Edge("A", "B", "related"),
            Edge("A", "A", "related"),
        ]
        result = sort_edges(edges)
        assert result == [
            Edge("A", "A", "related"),
            Edge("A", "B", "related"),
            Edge("C", "A", "related"),
        ]


class TestBuildEdgeSet:
    def test_integration_with_mixed_edge_types(self):
        entries = [
            {
                "document_id": "REPO-ADR-001",
                "path": "docs/45-adr/adr-001.md",
                "related_ids": ["REPO-PRD-001"],
                "superseded_by": None,
                "_body": "See [PRD](../10-prd/prd-001.md).",
            },
            {
                "document_id": "REPO-PRD-001",
                "path": "docs/10-prd/prd-001.md",
                "related_ids": None,
                "superseded_by": "REPO-ADR-002",
                "_body": "",
            },
        ]
        path_to_doc_id = {
            "docs/45-adr/adr-001.md": "REPO-ADR-001",
            "docs/10-prd/prd-001.md": "REPO-PRD-001",
        }
        root = Path("/repo")
        edges = build_edge_set(entries, path_to_doc_id, root)

        edge_types = {(e.source, e.target, e.edge_type) for e in edges}
        assert ("REPO-ADR-001", "REPO-PRD-001", "related") in edge_types
        assert ("REPO-ADR-001", "REPO-PRD-001", "references") in edge_types
        assert ("REPO-ADR-002", "REPO-PRD-001", "supersedes") in edge_types
        # Verify deterministic sort.
        assert edges == sorted(edges, key=Edge.sort_key)


# ---------------------------------------------------------------------------
# Graph validation
# ---------------------------------------------------------------------------


class TestCheckDuplicateDocumentIds:
    def test_no_duplicates(self):
        doc_id_paths = {"A": ["a.md"], "B": ["b.md"]}
        assert _check_dup(doc_id_paths) == []

    def test_duplicates_detected(self):
        doc_id_paths = {"A": ["a.md", "b.md"], "B": ["c.md"]}
        errors = _check_dup(doc_id_paths)
        assert len(errors) == 1
        assert errors[0]["code"] == "GRAPH_DUPLICATE_DOCUMENT_ID"
        assert "A" in errors[0]["message"]


class TestCheckSupersessionCycle:
    def test_no_cycle(self):
        edges = [
            Edge("A", "B", "supersedes"),
            Edge("B", "C", "supersedes"),
        ]
        assert _check_cycles(edges) == []

    def test_simple_cycle_ab(self):
        edges = [
            Edge("A", "B", "supersedes"),
            Edge("B", "A", "supersedes"),
        ]
        errors = _check_cycles(edges)
        assert len(errors) == 1
        assert errors[0]["code"] == "GRAPH_SUPERSESSION_CYCLE"

    def test_transitive_cycle(self):
        edges = [
            Edge("A", "B", "supersedes"),
            Edge("B", "C", "supersedes"),
            Edge("C", "A", "supersedes"),
        ]
        errors = _check_cycles(edges)
        assert len(errors) == 1
        assert "A" in errors[0]["message"]

    def test_reports_multiple_distinct_cycles(self):
        edges = [
            Edge("A", "B", "supersedes"),
            Edge("B", "C", "supersedes"),
            Edge("C", "A", "supersedes"),
            Edge("A", "D", "supersedes"),
            Edge("D", "A", "supersedes"),
        ]
        errors = _check_cycles(edges)
        assert len(errors) == 2
        messages = {error["message"] for error in errors}
        assert "Supersession cycle detected: A -> B -> C -> A" in messages
        assert "Supersession cycle detected: A -> D -> A" in messages

    def test_long_chain_no_cycle(self):
        """500-node chain with no cycle completes without error or stack overflow."""
        edges = [
            Edge(f"N{i:03d}", f"N{i+1:03d}", "supersedes") for i in range(500)
        ]
        errors = _check_cycles(edges)
        assert errors == []


class TestCheckDanglingTargets:
    def test_all_known(self):
        edges = [Edge("A", "B", "related"), Edge("C", "D", "supersedes")]
        assert _check_dangling(edges, {"A", "B", "C", "D"}) == []

    def test_dangling_related(self):
        edges = [Edge("A", "MISSING", "related")]
        warnings = _check_dangling(edges, {"A"})
        assert len(warnings) == 1
        assert warnings[0]["code"] == "GRAPH_DANGLING_RELATED_ID"
        assert "MISSING" in warnings[0]["message"]

    def test_dangling_superseded(self):
        edges = [Edge("MISSING", "A", "supersedes")]
        warnings = _check_dangling(edges, {"A"})
        assert len(warnings) == 1
        assert warnings[0]["code"] == "GRAPH_DANGLING_SUPERSEDED_BY"
        assert "MISSING" in warnings[0]["message"]


class TestCheckSupersessionStatusMismatch:
    def test_no_mismatch(self):
        entries = [
            {"document_id": "A", "status": "Superseded", "superseded_by": "B"},
        ]
        assert _check_supersession_status(entries) == []

    def test_has_field_wrong_status(self):
        entries = [
            {"document_id": "A", "status": "Draft", "superseded_by": "B"},
        ]
        warnings = _check_supersession_status(entries)
        assert len(warnings) == 1
        assert "Draft" in warnings[0]["message"]

    def test_has_status_no_field(self):
        entries = [
            {"document_id": "A", "status": "Superseded"},
        ]
        warnings = _check_supersession_status(entries)
        assert len(warnings) == 1
        assert "no superseded_by" in warnings[0]["message"]


class TestCheckRelatedIdAsymmetry:
    def test_symmetric_no_advice(self):
        edges = [
            Edge("A", "B", "related"),
            Edge("B", "A", "related"),
        ]
        assert _check_asymmetry(edges) == []

    def test_asymmetric_produces_advice(self):
        edges = [
            Edge("A", "B", "related"),
        ]
        advice = _check_asymmetry(edges)
        assert len(advice) == 1
        assert advice[0]["code"] == "GRAPH_RELATED_ID_ASYMMETRY"
        assert advice[0]["source"] == "A"
        assert advice[0]["target"] == "B"


class TestValidateGraphIntegrity:
    def test_all_clean(self):
        entries = [
            {"document_id": "A", "path": "a.md", "status": "Draft", "related_ids": ["B"]},
            {"document_id": "B", "path": "b.md", "status": "Draft", "related_ids": ["A"]},
        ]
        edges = [
            Edge("A", "B", "related"),
            Edge("B", "A", "related"),
        ]
        warnings, advice, errors = validate_graph_integrity(
            entries, edges, {"A", "B"}, {"A": ["a.md"], "B": ["b.md"]},
        )
        assert errors == []
        assert warnings == []
        assert advice == []

    def test_mixed_issues(self):
        entries = [
            {"document_id": "A", "path": "a.md", "status": "Draft", "related_ids": ["MISSING"]},
        ]
        edges = [Edge("A", "MISSING", "related")]
        warnings, _advice, errors = validate_graph_integrity(
            entries, edges, {"A"}, {"A": ["a.md"]},
        )
        assert errors == []
        assert len(warnings) == 1
        assert "DANGLING" in warnings[0]["code"]

    def test_fatal_duplicate_halts(self):
        entries = [
            {"document_id": "A", "path": "a.md"},
        ]
        doc_id_paths = {"A": ["a.md", "b.md"]}
        warnings, _advice, errors = validate_graph_integrity(
            entries, [], {"A"}, doc_id_paths,
        )
        assert len(errors) == 1
        assert errors[0]["code"] == "GRAPH_DUPLICATE_DOCUMENT_ID"
        # Non-fatal checks should not run when fatal errors exist.
        assert warnings == []


# ---------------------------------------------------------------------------
# Helpers to avoid importing private functions
# ---------------------------------------------------------------------------


def _check_dup(doc_id_paths):
    from meminit.core.services.graph import _check_duplicate_document_ids
    return _check_duplicate_document_ids(doc_id_paths)


def _check_cycles(edges):
    from meminit.core.services.graph import _check_supersession_cycle
    return _check_supersession_cycle(edges)


def _check_dangling(edges, known_ids):
    from meminit.core.services.graph import _check_dangling_targets
    return _check_dangling_targets(edges, known_ids)


def _check_supersession_status(entries):
    from meminit.core.services.graph import _check_supersession_status_mismatch
    return _check_supersession_status_mismatch(entries)


def _check_asymmetry(edges):
    from meminit.core.services.graph import _check_related_id_asymmetry
    return _check_related_id_asymmetry(edges)
