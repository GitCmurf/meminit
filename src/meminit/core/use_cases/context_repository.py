"""Use case: provide repository configuration context for agent bootstrap.

Implements the ``meminit context`` command (PRD-003 FR-6).  Reads the
repository's ``docops.config.yaml`` via ``load_repo_layout()`` and returns a
structured payload that an agent can use to understand namespace layout, type
directories, templates, and exclusion rules.

Deep mode (``--deep``) adds per-namespace document counts with a 2-second
performance budget.  If the budget is exceeded, partial results are returned
with ``deep_incomplete: true`` and a warning.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from meminit.core.services.repo_config import RepoLayout, load_repo_layout


@dataclass
class ContextResult:
    """Result of the context use case."""

    data: Dict[str, Any]
    warnings: List[Dict[str, Any]] = field(default_factory=list)


def _count_governed_markdown(docs_dir: Path) -> int:
    """Count markdown files under a docs directory."""
    if not docs_dir.is_dir():
        return 0
    return sum(1 for _ in docs_dir.rglob("*.md"))


class ContextRepositoryUseCase:
    """Provide repository configuration context for agents."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir).resolve()

    def execute(self, *, deep: bool = False) -> ContextResult:
        """Execute the context use case.

        Args:
            deep: If True, include per-namespace document counts
                (subject to 2-second performance budget).

        Returns:
            ContextResult with structured context data and optional warnings.
        """
        layout: RepoLayout = load_repo_layout(self.root_dir)
        warnings: List[Dict[str, Any]] = []

        namespaces_data: List[Dict[str, Any]] = []
        for ns in sorted(layout.namespaces, key=lambda n: n.namespace):
            ns_entry: Dict[str, Any] = {
                "docs_root": ns.docs_root,
                "excluded_filename_prefixes": sorted(ns.excluded_filename_prefixes),
                "name": ns.namespace,
                "repo_prefix": ns.repo_prefix,
                "type_directories": dict(sorted(ns.type_directories.items())),
            }
            namespaces_data.append(ns_entry)

        # Build allowed_types from all namespaces (union of all type keys).
        all_types: set[str] = set()
        for ns in layout.namespaces:
            all_types.update(ns.type_directories.keys())

        # Build templates from the default namespace.
        default_ns = layout.default_namespace()
        templates: Dict[str, str] = dict(sorted(default_ns.templates.items()))

        context_data: Dict[str, Any] = {
            "allowed_types": sorted(all_types),
            "config_path": "docops.config.yaml",
            "default_owner": default_ns.templates.get("default_owner", "__TBD__"),
            "docops_version": default_ns.docops_version,
            "excluded_filename_prefixes": sorted(default_ns.excluded_filename_prefixes),
            "index_path": layout.index_path,
            "namespaces": namespaces_data,
            "project_name": layout.project_name,
            "repo_prefix": default_ns.repo_prefix,
            "schema_path": default_ns.schema_path,
            "templates": templates,
        }

        if deep:
            budget_seconds = 2.0
            start = time.monotonic()
            deep_incomplete = False

            for ns_entry in namespaces_data:
                elapsed = time.monotonic() - start
                if elapsed >= budget_seconds:
                    deep_incomplete = True
                    ns_entry["document_count"] = None
                    continue

                docs_dir = self.root_dir / ns_entry["docs_root"]
                ns_entry["document_count"] = _count_governed_markdown(docs_dir)

            context_data["deep_incomplete"] = deep_incomplete
            if deep_incomplete:
                warnings.append(
                    {
                        "code": "DEEP_BUDGET_EXCEEDED",
                        "message": (
                            "Deep scan performance budget (2s) exceeded; "
                            "some namespace counts are incomplete."
                        ),
                        "path": "docops.config.yaml",
                    }
                )

        return ContextResult(data=context_data, warnings=warnings)
