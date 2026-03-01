import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import frontmatter

from meminit.core.services.repo_config import RepoConfig, RepoLayout
from meminit.core.services.scan_plan import PlanAction, PlanActionType, ActionPreconditions, ActionSafety

class HeuristicsService:
    FILENAME_EXCEPTIONS = {
        "README.md",
        "CHANGELOG.md",
        "LICENSE",
        "LICENSE.md",
        "LICENCE",
        "LICENCE.md",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "NOTICE",
        "NOTICE.md",
    }

    def __init__(self, root_dir: Path, layout: RepoLayout):
        self.root_dir = root_dir
        self.layout = layout

    def generate_plan_actions(self, target_files: List[Path]) -> List[PlanAction]:
        actions = []
        for path in target_files:
            ns = self.layout.namespace_for_path(path)
            if not ns or ns.is_excluded(path):
                continue

            try:
                content_bytes = path.read_bytes()
                source_sha256 = f"sha256:{hashlib.sha256(content_bytes).hexdigest()}"
                post = frontmatter.loads(content_bytes.decode("utf-8"))
            except Exception:
                continue

            rel_path = path.relative_to(self.root_dir).as_posix()
            
            # Infer Type
            if post.metadata and "type" in post.metadata and post.metadata["type"]:
                inferred_type = str(post.metadata["type"]).strip().upper()
                type_conf = 1.0
                type_rationale = "frontmatter:type"
            else:
                inferred_type, type_conf, type_rationale = self._infer_doc_type(rel_path, ns)
            
            # Infer Title
            inferred_title = self._infer_title(post.content, path.stem)
            
            # Path computation 
            # 1. Check if filename matches standard (like fix does)
            expected_filename = self._compute_renamed_path(path).name
            
            # 2. Check if it's in the right type directory
            expected_dir = ns.type_directories.get(inferred_type)
            if expected_dir:
                expected_dir_path = self.root_dir
                if ns.docs_root:
                    expected_dir_path = expected_dir_path / ns.docs_root
                expected_dir_path = expected_dir_path / expected_dir
            else:
                expected_dir_path = path.parent
            
            target_path_obj = expected_dir_path / expected_filename
            target_path_rel = target_path_obj.relative_to(self.root_dir).as_posix()
            
            requires_move = target_path_obj.parent != path.parent
            requires_rename = target_path_obj.name != path.name
            
            preconditions = ActionPreconditions(source_sha256=source_sha256)
            
            # Generate Metadata block action
            if not post.metadata:
                metadata_patch = {
                    "document_id": "__TBD__",
                    "type": inferred_type,
                    "title": inferred_title,
                    "status": "Draft",
                    "version": "0.1",
                    "owner": "__TBD__",
                    "docops_version": ns.docops_version or "2.0",
                    "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                }
                rationale = ["File lacks a frontmatter block."]
                if type_rationale:
                    rationale.append(f"type: {type_rationale}")
                
                action = PlanAction(
                    id=PlanAction.generate_id(PlanActionType.INSERT_METADATA_BLOCK.value, rel_path, rel_path),
                    action=PlanActionType.INSERT_METADATA_BLOCK,
                    source_path=rel_path,
                    target_path=rel_path,  # Metadata insert doesn't change path
                    confidence=type_conf,
                    rationale=rationale,
                    preconditions=preconditions,
                    safety=ActionSafety(destructive=False, overwrites=False),
                    metadata_patch=metadata_patch
                )
                actions.append(action)
            else:
                # Update metadata fields if missing
                patch = {}
                rationale = []
                if "document_id" not in post.metadata:
                    patch["document_id"] = "__TBD__"
                    rationale.append("document_id: requires generation")
                if "type" not in post.metadata:
                    patch["type"] = inferred_type
                    if type_rationale: rationale.append(f"type: {type_rationale}")
                if "title" not in post.metadata:
                    patch["title"] = inferred_title
                    rationale.append("title: Inferred from heading or filename")
                if "status" not in post.metadata:
                    patch["status"] = "Draft"
                    rationale.append("status: set to Draft default")
                if "version" not in post.metadata:
                    patch["version"] = "0.1"
                    rationale.append("version: set to 0.1 default")
                if "owner" not in post.metadata:
                    patch["owner"] = "__TBD__"
                    rationale.append("owner: set to __TBD__ placeholder")
                if "docops_version" not in post.metadata:
                    patch["docops_version"] = ns.docops_version or "2.0"
                    rationale.append("docops_version: set to default version")
                if "last_updated" not in post.metadata:
                    patch["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    rationale.append("last_updated: set to today")
                
                if patch:
                    action = PlanAction(
                        id=PlanAction.generate_id(PlanActionType.UPDATE_METADATA.value, rel_path, rel_path),
                        action=PlanActionType.UPDATE_METADATA,
                        source_path=rel_path,
                        target_path=rel_path,
                        confidence=0.9,
                        rationale=rationale,
                        preconditions=preconditions,
                        safety=ActionSafety(destructive=False, overwrites=False),
                        metadata_patch=patch
                    )
                    actions.append(action)

            # Move or Rename actions
            if requires_move or requires_rename:
                action_type = PlanActionType.MOVE_FILE if requires_move else PlanActionType.RENAME_FILE
                rationale = []
                conf = 0.95
                if requires_move:
                    rationale.append(f"Move to conform with target directory for type '{inferred_type}'.")
                    conf = min(conf, type_conf) 
                if requires_rename:
                    rationale.append(f"Rename to '{expected_filename}' to match standard filename conventions.")
                
                action = PlanAction(
                    id=PlanAction.generate_id(action_type.value, rel_path, target_path_rel),
                    action=action_type,
                    source_path=rel_path,
                    target_path=target_path_rel,
                    confidence=conf,
                    rationale=rationale,
                    preconditions=preconditions,
                    safety=ActionSafety(destructive=False, overwrites=False)
                )
                actions.append(action)

        return actions

    def _infer_doc_type(self, rel_path: str, ns: RepoConfig) -> Tuple[str, float, str]:
        parts = Path(rel_path).parts
        docs_root = ns.docs_root.strip("/").replace("\\", "/") if ns.docs_root else ""
        docs_root_parts = tuple(Path(docs_root).parts) if docs_root else ()
        
        if docs_root_parts and tuple(parts[:len(docs_root_parts)]) == docs_root_parts:
            rel_to_docs = Path(*parts[len(docs_root_parts):])
            for doc_type, subdir in ns.type_directories.items():
                sub_parts = Path(subdir).parts
                if rel_to_docs.parts[:len(sub_parts)] == sub_parts:
                    return doc_type, 0.9, f"path_segment:{subdir}"

        stem = Path(rel_path).stem.lower()
        if "adr" in stem or "decision" in stem:
            return "ADR", 0.7, "filename_contains:adr/decision"
        if "prd" in stem or "product" in stem or "req" in stem:
            return "PRD", 0.6, "filename_contains:prd/product/req"
        if "runbook" in stem:
            return "RUNBOOK", 0.8, "filename_contains:runbook"

        return "DOC", 0.4, "fallback default"

    def _infer_title(self, body: str, fallback_stem: str) -> str:
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                title = stripped.lstrip("#").strip()
                if title:
                    return title
        return fallback_stem.replace("-", " ").strip().title() or "Untitled"

    def _compute_renamed_path(self, original_path: Path) -> Path:
        if original_path.name in self.FILENAME_EXCEPTIONS:
            return original_path
        stem = original_path.stem.lower()
        suffix = original_path.suffix.lower()

        stem = stem.replace(" ", "-").replace("_", "-")
        stem = re.sub(r"[^a-z0-9-]", "-", stem)
        stem = re.sub(r"-{2,}", "-", stem).strip("-")
        if not stem:
            stem = "doc"

        return original_path.parent / f"{stem}{suffix}"
