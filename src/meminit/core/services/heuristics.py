import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import frontmatter

from meminit.core.services.repo_config import RepoConfig, RepoLayout
from meminit.core.services.safe_yaml import safe_frontmatter_loads
from meminit.core.services.scan_plan import PlanAction, PlanActionType, ActionPreconditions, ActionSafety
from meminit.core.services.path_utils import FILENAME_EXCEPTIONS, normalize_filename_to_kebab_case, compute_file_hash
from meminit.core.services.markdown_utils import extract_title_from_markdown, DEFAULT_DOCOPS_VERSION, DEFAULT_STATUS, DEFAULT_VERSION, DEFAULT_OWNER

class HeuristicsService:

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
                source_sha256 = compute_file_hash(path)
                post = safe_frontmatter_loads(content_bytes.decode("utf-8"))
            except Exception as e:
                logging.warning("meminit scan --plan failed to parse %s: %s", path, e)
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
            inferred_title = extract_title_from_markdown(post.content, path.stem)

            # Path computation
            # 1. Check if filename matches standard (like fix does)
            expected_filename = normalize_filename_to_kebab_case(path).name
            
            # 2. Check if it's in the right type directory
            expected_dir = ns.expected_subdir_for_type(inferred_type)
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
                # Note: document_id uses "__TBD__" placeholder because unique ID generation
                # requires full repository context. It will be replaced during plan execution.
                metadata_patch = {
                    "document_id": DEFAULT_OWNER,  # Placeholder, replaced during execution
                    "type": inferred_type,
                    "title": inferred_title,
                    "status": DEFAULT_STATUS,
                    "version": DEFAULT_VERSION,
                    "owner": DEFAULT_OWNER,
                    "docops_version": ns.docops_version or DEFAULT_DOCOPS_VERSION,
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
                # Note: document_id uses "__TBD__" placeholder because unique ID generation
                # requires full repository context. It will be replaced during plan execution.
                fields_to_patch = [
                    ("document_id", lambda: DEFAULT_OWNER, "document_id: placeholder replaced during execution with unique ID"),
                    ("type", lambda: inferred_type, f"type: {type_rationale}" if type_rationale else "type: inferred"),
                    ("title", lambda: inferred_title, "title: Inferred from heading or filename"),
                    ("status", lambda: DEFAULT_STATUS, "status: set to Draft default"),
                    ("version", lambda: DEFAULT_VERSION, "version: set to 0.1 default"),
                    ("owner", lambda: DEFAULT_OWNER, "owner: set to __TBD__ placeholder"),
                    ("docops_version", lambda: ns.docops_version or DEFAULT_DOCOPS_VERSION, "docops_version: set to default version"),
                    ("last_updated", lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"), "last_updated: set to today"),
                ]
                
                patch = {}
                rationale = []
                for field, default_factory, rationale_msg in fields_to_patch:
                    if field not in post.metadata:
                        patch[field] = default_factory()
                        rationale.append(rationale_msg)
                
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
        # Check against type directories first, as it's the highest confidence signal.
        # This is relative to the namespace's docs_dir.
        abs_path = Path(self.root_dir) / rel_path
        
        # Determine the full docs directory for this namespace
        if ns.docs_root:
            docs_dir = Path(self.root_dir) / ns.docs_root.strip("/").replace("\\", "/")
        else:
            docs_dir = Path(self.root_dir)

        for doc_type, subdir in ns.type_directories.items():
            type_dir_path = docs_dir / subdir
            try:
                abs_path.relative_to(type_dir_path)
                return doc_type, 0.9, f"path_segment:{subdir}"
            except ValueError:
                continue

        stem = Path(rel_path).stem.lower()
        if "adr" in stem or "decision" in stem:
            return "ADR", 0.7, "filename_contains:adr/decision"
        if "prd" in stem or "product" in stem or "req" in stem:
            return "PRD", 0.6, "filename_contains:prd/product/req"
        if "runbook" in stem:
            return "RUNBOOK", 0.8, "filename_contains:runbook"

        return "DOC", 0.4, "fallback default"

    def _compute_renamed_path(self, original_path: Path) -> Path:
        return normalize_filename_to_kebab_case(original_path)

    def _infer_title(self, body: str, fallback_stem: str) -> str:
        return extract_title_from_markdown(body, fallback_stem)
