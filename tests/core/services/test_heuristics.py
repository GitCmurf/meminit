"""Tests for HeuristicsService (Finding #6)."""

from pathlib import Path
from typing import Any

import pytest

from meminit.core.services.heuristics import HeuristicsService
from meminit.core.services.repo_config import RepoConfig, RepoLayout
from meminit.core.services.scan_plan import PlanActionType


def _make_layout(tmp_path: Path) -> RepoLayout:
    """Build a minimal RepoLayout for testing."""
    root_dir = tmp_path
    config = RepoConfig(
        root_dir=root_dir,
        namespace="default",
        project_name="Test",
        repo_prefix="TST",
        docops_version="2.0",
        docs_root="docs",
        schema_path="docs/00-governance/metadata.schema.json",
        excluded_paths=(),
        excluded_filename_prefixes=(),
        excluded_files=(),
        type_directories={"ADR": "adr", "PRD": "prd", "GOV": "gov"},
        templates={},
        document_types={},
        valid_impl_states=(),
        valid_doc_statuses=(),
        catalog_name="catalog.md",
    )
    return RepoLayout(
        root_dir=root_dir,
        project_name="Test",
        namespaces=(config,),
        index_path="docs/01-indices/meminit.index.json",
        catalog_name="catalog.md",
    )


def _make_service_with_doc(
    tmp_path: Path, rel_path: str, content: str
) -> tuple[HeuristicsService, Path]:
    """Create a HeuristicsService and a document file in the repo."""
    doc_path = tmp_path / rel_path
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(content, encoding="utf-8")
    layout = _make_layout(tmp_path)
    return HeuristicsService(tmp_path, layout), doc_path


class TestGeneratePlanActions:
    """Tests for HeuristicsService.generate_plan_actions."""

    def test_missing_frontmatter_inserts_metadata(self, tmp_path):
        """File without frontmatter gets an INSERT_METADATA_BLOCK action."""
        service, doc_path = _make_service_with_doc(
            tmp_path,
            "docs/adr/test-decision.md",
            "# Test Decision\n\nSome content.",
        )
        actions = service.generate_plan_actions([doc_path])
        assert len(actions) == 1
        assert actions[0].action == PlanActionType.INSERT_METADATA_BLOCK
        assert actions[0].metadata_patch is not None
        assert "type" in actions[0].metadata_patch
        assert "title" in actions[0].metadata_patch

    def test_complete_frontmatter_no_metadata_action(self, tmp_path):
        """File with complete frontmatter gets no metadata action."""
        content = (
            "---\ndocument_id: TST-ADR-001\ntype: ADR\n"
            "title: Test\nowner: Me\nstatus: Draft\nversion: 0.1\n"
            "docops_version: 2.0\nlast_updated: 2026-01-01\n---\n# Test\n"
        )
        service, doc_path = _make_service_with_doc(
            tmp_path,
            "docs/adr/adr-001.md",
            content,
        )
        actions = service.generate_plan_actions([doc_path])
        # Only move/rename may appear; no metadata-only action
        metadata_actions = [
            a
            for a in actions
            if a.action in (PlanActionType.INSERT_METADATA_BLOCK, PlanActionType.UPDATE_METADATA)
        ]
        assert len(metadata_actions) == 0

    def test_partial_frontmatter_updates_metadata(self, tmp_path):
        """File with partial frontmatter gets UPDATE_METADATA for missing fields."""
        content = "---\ntitle: Test\n---\n# Test\n"
        service, doc_path = _make_service_with_doc(
            tmp_path,
            "docs/adr/adr-001.md",
            content,
        )
        actions = service.generate_plan_actions([doc_path])
        update_actions = [a for a in actions if a.action == PlanActionType.UPDATE_METADATA]
        assert len(update_actions) >= 1
        patch = update_actions[0].metadata_patch
        assert patch is not None
        # Missing fields should be in the patch
        assert "document_id" in patch
        assert "status" in patch

    def test_type_inference_from_path(self, tmp_path):
        """File in type directory infers correct type from path."""
        service, doc_path = _make_service_with_doc(
            tmp_path,
            "docs/adr/adr-001.md",
            "# Test",
        )
        actions = service.generate_plan_actions([doc_path])
        meta = [a for a in actions if a.action == PlanActionType.INSERT_METADATA_BLOCK]
        assert len(meta) == 1
        assert meta[0].metadata_patch["type"] == "ADR"

    def test_type_inference_from_filename(self, tmp_path):
        """File with 'prd' in stem infers PRD type."""
        service, doc_path = _make_service_with_doc(
            tmp_path,
            "docs/misc/my-prd-doc.md",
            "# Product Spec",
        )
        actions = service.generate_plan_actions([doc_path])
        meta = [a for a in actions if a.action == PlanActionType.INSERT_METADATA_BLOCK]
        assert len(meta) == 1
        assert meta[0].metadata_patch["type"] == "PRD"

    def test_requires_move_to_correct_directory(self, tmp_path):
        """File in wrong type directory (frontmatter type != dir) gets MOVE_FILE."""
        content = "---\ntype: ADR\n---\n# Test\n"
        service, doc_path = _make_service_with_doc(
            tmp_path,
            "docs/prd/adr-001.md",
            content,
        )
        actions = service.generate_plan_actions([doc_path])
        move_actions = [a for a in actions if a.action == PlanActionType.MOVE_FILE]
        assert len(move_actions) == 1
        assert "adr" in move_actions[0].target_path

    def test_requires_rename_to_kebab(self, tmp_path):
        """File with non-standard name gets RENAME_FILE action."""
        service, doc_path = _make_service_with_doc(
            tmp_path,
            "docs/adr/My_Bad_File.adr.md",
            "# Test",
        )
        actions = service.generate_plan_actions([doc_path])
        rename_actions = [a for a in actions if a.action == PlanActionType.RENAME_FILE]
        assert len(rename_actions) == 1
        assert "my-bad-file" in rename_actions[0].target_path

    def test_move_and_rename_exclusivity(self, tmp_path):
        """A file needing both move and rename gets MOVE_FILE (not two separate actions)."""
        service, doc_path = _make_service_with_doc(
            tmp_path,
            "docs/prd/BAD_NAME.md",
            "# Test",
        )
        actions = service.generate_plan_actions([doc_path])
        move_actions = [a for a in actions if a.action == PlanActionType.MOVE_FILE]
        rename_actions = [a for a in actions if a.action == PlanActionType.RENAME_FILE]
        # Should not have both move AND rename for the same file
        assert not (move_actions and rename_actions)
        # Should have at least one file-motion action
        all_motion = move_actions + rename_actions
        assert len(all_motion) >= 1

    def test_malformed_file_skipped(self, tmp_path):
        """A non-text/corrupt file is skipped with a warning, not crashed."""
        doc_path = tmp_path / "docs/adr/corrupt.md"
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_bytes(b"\xff\xfe\x00\x01\x02")
        layout = _make_layout(tmp_path)
        service = HeuristicsService(tmp_path, layout)
        actions = service.generate_plan_actions([doc_path])
        assert len(actions) == 0

    def test_excluded_file_skipped(self, tmp_path):
        """File matching excluded_filename_prefixes is skipped."""
        doc_path = tmp_path / "docs/adr/WIP-notes.md"
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text("# WIP", encoding="utf-8")
        root_dir = tmp_path
        config = RepoConfig(
            root_dir=root_dir,
            namespace="default",
            project_name="Test",
            repo_prefix="TST",
            docops_version="2.0",
            docs_root="docs",
            schema_path="docs/00-governance/metadata.schema.json",
            excluded_paths=(),
            excluded_filename_prefixes=("wip-",),
            excluded_files=(),
            type_directories={"ADR": "adr"},
            templates={},
            document_types={},
            valid_impl_states=(),
            valid_doc_statuses=(),
            catalog_name="catalog.md",
        )
        layout = RepoLayout(
            root_dir=root_dir,
            project_name="Test",
            namespaces=(config,),
            index_path="docs/01-indices/meminit.index.json",
            catalog_name="catalog.md",
        )
        service = HeuristicsService(tmp_path, layout)
        actions = service.generate_plan_actions([doc_path])
        assert len(actions) == 0


class TestInferDocType:
    """Tests for _infer_doc_type helper."""

    def _make_config(self, tmp_path: Path, **overrides: Any) -> RepoConfig:
        defaults = dict(
            root_dir=tmp_path,
            namespace="default",
            project_name="Test",
            repo_prefix="TST",
            docops_version="2.0",
            docs_root="docs",
            schema_path="docs/00-governance/metadata.schema.json",
            excluded_paths=(),
            excluded_filename_prefixes=(),
            excluded_files=(),
            type_directories={},
            templates={},
            document_types={},
            valid_impl_states=(),
            valid_doc_statuses=(),
            catalog_name="catalog.md",
        )
        defaults.update(overrides)
        return RepoConfig(**defaults)

    def _make_layout(self, tmp_path: Path, config: RepoConfig) -> RepoLayout:
        return RepoLayout(
            root_dir=tmp_path,
            project_name="Test",
            namespaces=(config,),
            index_path="index.json",
            catalog_name="catalog.md",
        )

    def test_infer_from_type_directory(self, tmp_path):
        """Path in a known type directory returns that type."""
        config = self._make_config(
            tmp_path,
            type_directories={"ADR": "adr", "SPEC": "spec"},
        )
        layout = self._make_layout(tmp_path, config)
        (tmp_path / "docs" / "adr").mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs" / "spec").mkdir(parents=True, exist_ok=True)
        service = HeuristicsService(tmp_path, layout)
        doc_type, confidence, _ = service._infer_doc_type("docs/adr/test.md", config)
        assert doc_type == "ADR"
        assert confidence >= 0.9

    def test_infer_from_filename_adr(self, tmp_path):
        """Filename with 'adr' in stem returns ADR."""
        config = self._make_config(tmp_path)
        layout = self._make_layout(tmp_path, config)
        service = HeuristicsService(tmp_path, layout)
        doc_type, _, _ = service._infer_doc_type("docs/misc/decision-log.md", config)
        assert doc_type == "ADR"

    def test_infer_from_filename_prd(self, tmp_path):
        """Filename with 'prd' in stem returns PRD."""
        config = self._make_config(tmp_path)
        layout = self._make_layout(tmp_path, config)
        service = HeuristicsService(tmp_path, layout)
        doc_type, _, _ = service._infer_doc_type("docs/misc/product-requirements.md", config)
        assert doc_type == "PRD"

    def test_infer_fallback_default(self, tmp_path):
        """Unknown filename falls back to DOC."""
        config = self._make_config(tmp_path)
        layout = self._make_layout(tmp_path, config)
        service = HeuristicsService(tmp_path, layout)
        doc_type, confidence, _ = service._infer_doc_type("docs/misc/notes.md", config)
        assert doc_type == "DOC"
        assert confidence == 0.4
