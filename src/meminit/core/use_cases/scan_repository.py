from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
import datetime
import hashlib
import logging

import yaml

from meminit.core.services.repo_config import load_repo_layout
from meminit.core.services.scan_plan import MigrationPlan
from meminit.core.services.heuristics import HeuristicsService

TYPE_ALIASES: Dict[str, List[str]] = {
    "ADR": ["adrs", "decisions"],
    "PRD": ["prds"],
    "FDD": ["fdds"],
    "SPEC": ["specs"],
    "DESIGN": ["designs"],
    "PLAN": ["plans", "planning"],
    "STRAT": ["strategy", "strategies"],
    "RUNBOOK": ["runbooks"],
    "GUIDE": ["guides"],
}


@dataclass(frozen=True)
class ScanReport:
    docs_root: Optional[str]
    suggested_type_directories: Dict[str, str]
    markdown_count: int
    governed_markdown_count: int
    notes: List[str]
    ambiguous_types: Dict[str, List[str]]
    suggested_namespaces: List[Dict[str, str]]
    configured_namespaces: List[Dict[str, object]]
    overlapping_namespaces: List[Dict[str, str]]
    plan: Optional[MigrationPlan] = None

    def as_dict(self) -> dict:
        d = {
            "docs_root": self.docs_root,
            "suggested_type_directories": self.suggested_type_directories,
            "markdown_count": self.markdown_count,
            "governed_markdown_count": self.governed_markdown_count,
            "notes": self.notes,
            "ambiguous_types": self.ambiguous_types,
            "suggested_namespaces": self.suggested_namespaces,
            "configured_namespaces": self.configured_namespaces,
            "overlapping_namespaces": self.overlapping_namespaces,
        }
        if self.plan:
            d["plan"] = self.plan.as_dict()
        return d


class ScanRepositoryUseCase:
    def __init__(self, root_dir: str):
        self._root_dir = Path(root_dir).resolve()

    def execute(self, generate_plan: bool = False) -> ScanReport:
        layout = load_repo_layout(self._root_dir)
        config_path = self._root_dir / "docops.config.yaml"
        existing_config = self._load_config(config_path)

        docs_root = self._resolve_docs_root(existing_config, layout.default_namespace().docs_root)
        notes: List[str] = []
        suggested_type_directories: Dict[str, str] = {}
        ambiguous_types: Dict[str, List[str]] = {}
        markdown_count = 0
        governed_markdown_count = 0
        suggested_namespaces: List[Dict[str, str]] = []
        configured_namespaces: List[Dict[str, object]] = []
        overlapping_namespaces: List[Dict[str, str]] = []

        if docs_root is None:
            notes.append("No docs root detected (expected `docs/` or docs_root in config).")
            return ScanReport(
                docs_root=None,
                suggested_type_directories={},
                markdown_count=0,
                governed_markdown_count=0,
                notes=notes,
                ambiguous_types={},
                suggested_namespaces=[],
                configured_namespaces=[],
                overlapping_namespaces=[],
            )

        docs_dir = self._root_dir / docs_root
        target_files = []
        if not docs_dir.exists():
            notes.append(f"Docs root configured but missing on disk: {docs_root}")
        else:
            target_files = list(docs_dir.rglob("*.md"))
            markdown_count = len(target_files)

        # Always compute namespace-aware counts when possible.
        configured_namespaces = self._configured_namespaces(layout)
        governed_markdown_count = sum(
            int(ns.get("governed_markdown_count") or 0) for ns in configured_namespaces
        )
        overlapping_namespaces = self._detect_overlapping_namespaces(layout)
        if overlapping_namespaces:
            notes.append(
                "Overlapping namespace roots detected; Meminit assigns each file to the most-specific namespace. "
                "Ensure overlaps are intentional."
            )

        # Only suggest type_directories for the primary docs_root when it exists on disk.
        subdirs = {}
        if docs_dir.exists():
            subdirs = {p.name.lower(): p.name for p in docs_dir.iterdir() if p.is_dir()}

        for doc_type, default_dir in layout.default_namespace().type_directories.items():
            default_name = default_dir.split("/")[-1].lower()
            if default_name in subdirs:
                continue

            candidates = [doc_type.lower(), f"{doc_type.lower()}s"]
            candidates.extend(TYPE_ALIASES.get(doc_type, []))
            matches = []
            for c in candidates:
                key = c.lower()
                if key in subdirs:
                    matches.append(subdirs[key])
            # de-duplicate while preserving order
            deduped = []
            seen = set()
            for m in matches:
                if m not in seen:
                    deduped.append(m)
                    seen.add(m)
            matches = deduped
            if len(matches) == 1:
                suggested_type_directories[doc_type] = matches[0]
            elif len(matches) > 1:
                ambiguous_types[doc_type] = matches

        if not suggested_type_directories:
            notes.append("No alternate type directories detected.")

        suggested_namespaces = self._suggest_namespaces(existing_config, docs_root)
        if suggested_namespaces:
            notes.append(
                "Monorepo docs roots detected; consider configuring `namespaces` for multi-root governance."
            )
        if len(layout.namespaces) > 1:
            notes.append(
                "Repository is already configured with `namespaces`; see `configured_namespaces` for per-namespace stats."
            )

        plan = None
        if target_files and generate_plan:
            heuristics = HeuristicsService(self._root_dir, layout)
            actions = heuristics.generate_plan_actions(target_files)
            if actions:
                config_fingerprint_str = ""
                if config_path.exists():
                    try:
                        config_bytes = config_path.read_bytes()
                        config_fingerprint_str = f"sha256:{hashlib.sha256(config_bytes).hexdigest()}"
                    except (OSError, IOError) as e:
                        logging.debug("Failed to hash config fingerprint: %s", e)
                
                plan = MigrationPlan(
                    plan_version="1.0",
                    generated_at=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    config_fingerprint=config_fingerprint_str,
                    actions=actions
                )

        return ScanReport(
            docs_root=docs_root,
            suggested_type_directories=suggested_type_directories,
            markdown_count=markdown_count,
            governed_markdown_count=governed_markdown_count,
            notes=notes,
            ambiguous_types=ambiguous_types,
            suggested_namespaces=suggested_namespaces,
            configured_namespaces=configured_namespaces,
            overlapping_namespaces=overlapping_namespaces,
            plan=plan,
        )

    def _resolve_docs_root(self, config: dict, default_root: str) -> Optional[str]:
        docs_root = config.get("docs_root")
        if isinstance(docs_root, str) and docs_root.strip():
            return docs_root.strip().strip("/")
        if (self._root_dir / default_root).exists():
            return default_root
        if (self._root_dir / "docs").exists():
            return "docs"
        return None

    def _load_config(self, path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _suggest_namespaces(self, config: dict, primary_docs_root: str) -> List[Dict[str, str]]:
        """
        Suggest namespace blocks for common monorepo structures.

        This is planner-only; it must remain deterministic and should not be used for enforcement.
        """
        configured = set()
        raw_namespaces = config.get("namespaces")
        if isinstance(raw_namespaces, list):
            for item in raw_namespaces:
                if isinstance(item, dict):
                    docs_root = item.get("docs_root")
                    if isinstance(docs_root, str) and docs_root.strip():
                        configured.add(docs_root.strip().strip("/"))

        candidates: list[str] = []
        for pattern in (
            "packages/*/docs",
            "apps/*/docs",
            "services/*/docs",
            "modules/*/docs",
        ):
            for p in sorted(self._root_dir.glob(pattern)):
                if not p.is_dir():
                    continue
                rel = p.relative_to(self._root_dir).as_posix().strip("/")
                candidates.append(rel)

        # De-dup and filter obvious non-candidates.
        out: List[Dict[str, str]] = []
        seen: set[str] = set()
        for rel in candidates:
            if rel in seen:
                continue
            seen.add(rel)
            if rel == primary_docs_root.strip("/"):
                continue
            if rel in configured:
                continue
            # Only suggest if it looks doc-like (has some markdown).
            abs_path = self._root_dir / rel
            md_count = len(list(abs_path.rglob("*.md")))
            if md_count == 0:
                continue

            name = Path(rel).parts[-2] if len(Path(rel).parts) >= 2 else rel.replace("/", "-")
            repo_prefix = "".join(c for c in name.upper() if "A" <= c <= "Z")[:10]
            if len(repo_prefix) < 3:
                repo_prefix = "PKG"
            out.append({"name": name, "docs_root": rel, "repo_prefix_suggestion": repo_prefix})

        return out

    def _configured_namespaces(self, layout) -> List[Dict[str, object]]:
        out: List[Dict[str, object]] = []
        for ns in layout.namespaces:
            exists = ns.docs_dir.exists()
            governed = 0
            if exists:
                for path in ns.docs_dir.rglob("*.md"):
                    owner = layout.namespace_for_path(path)
                    if owner is None or owner.namespace.lower() != ns.namespace.lower():
                        continue
                    if ns.is_excluded(path):
                        continue
                    governed += 1
            out.append(
                {
                    "namespace": ns.namespace,
                    "docs_root": ns.docs_root,
                    "repo_prefix": ns.repo_prefix,
                    "docs_root_exists": exists,
                    "governed_markdown_count": governed,
                }
            )
        return out

    def _detect_overlapping_namespaces(self, layout) -> List[Dict[str, str]]:
        overlaps: List[Dict[str, str]] = []
        items = []
        for ns in layout.namespaces:
            root = str(ns.docs_root or "").strip().strip("/").replace("\\", "/")
            if not root:
                continue
            parts = Path(root).parts
            items.append((ns, root, parts))

        for a, a_root, a_parts in items:
            for b, b_root, b_parts in items:
                if a.namespace == b.namespace:
                    continue
                if len(a_parts) < len(b_parts) and b_parts[: len(a_parts)] == a_parts:
                    overlaps.append(
                        {
                            "parent_namespace": a.namespace,
                            "parent_docs_root": a_root,
                            "child_namespace": b.namespace,
                            "child_docs_root": b_root,
                        }
                    )
        # Deterministic ordering for tests and stable output.
        overlaps.sort(
            key=lambda d: (
                d["parent_docs_root"],
                d["child_docs_root"],
                d["parent_namespace"],
                d["child_namespace"],
            )
        )
        return overlaps
