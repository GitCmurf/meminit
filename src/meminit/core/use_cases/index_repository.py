"""Build or update the repository index with optional state merge, views, and filtering.

Enhancements:
- Merge ``project-state.yaml`` into per-document records (additive only).
- Generate ``catalog.md`` — table view with composite grouping and activity-recency sort.
- Generate ``kanban.md`` — pure Markdown fallback + HTML kanban board (with CSS hiding).
- Generate ``kanban.css`` — companion stylesheet.
- Filter by ``--status`` and ``--impl-state``.
- Sanitize all user-controlled fields in rendered output.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import frontmatter

from meminit.core.domain.entities import Severity
from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.diagnostics import (
    canonicalize_advice_list,
    canonicalize_warning_list,
)
from meminit.core.services.output_contracts import OUTPUT_SCHEMA_VERSION_V2
from meminit.core.services.path_utils import relative_path_string
from meminit.core.services.project_state import (
    ImplState,
    ProjectState,
    load_project_state,
    validate_project_state,
)
from meminit.core.services.repo_config import load_repo_layout
from meminit.core.services.safe_fs import ensure_safe_write_path
from meminit.core.services.sanitization import (
    MAX_NOTES_LENGTH,
    escape_markdown_table,
    sanitize_field,
    sanitize_html,
    validate_actor,
)
from meminit.core.services.warning_codes import WarningCode
from meminit.core.services import graph


def _json_default(obj: Any) -> str:
    """JSON serializer for date/datetime objects from frontmatter."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _safe_css_slug(value: str, *, default: str = "unknown") -> str:
    """Return a conservative CSS-safe slug for class names."""
    slug = re.sub(r"[^a-z0-9_-]+", "-", str(value).strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or default


def _normalize_related_ids(value: Any) -> Optional[List[str]]:
    """Ensure related_ids is always a list of strings or None."""
    if value is None:
        return None
    if isinstance(value, str):
        return [value] if value.strip() else None
    if isinstance(value, (list, tuple)):
        return [v for v in value if isinstance(v, str) and v.strip()]
    return None


def _remove_stale_artifacts(
    index_dir: Path,
    catalog_name: Optional[str] = None,
    *,
    remove_index: bool = False,
) -> None:
    """Best-effort removal of generated index-side artifacts.

    Only removes Meminit-generated files so that user-managed files
    (e.g. ``README.md``) in the index directory are never touched.
    Filesystem errors are silently swallowed so the caller's structured
    graph diagnostic is never masked.
    """
    known: set[Path] = set()
    if remove_index:
        known.add(index_dir / "meminit.index.json")

    # Fixed generated view files.
    known.add(index_dir / "kanban.md")
    known.add(index_dir / "kanban.css")
    if catalog_name:
        known.add(index_dir / Path(catalog_name).name)

    # Transitional cleanup: discover the catalog filename from a previous
    # successful run that still persisted legacy catalog_path metadata.
    old_index = index_dir / "meminit.index.json"
    try:
        old_data = json.loads(old_index.read_text(encoding="utf-8")).get("data", {})
        old_catalog = old_data.get("catalog_path")
        if isinstance(old_catalog, str) and old_catalog.strip():
            known.add(index_dir / Path(old_catalog).name)
    except (OSError, json.JSONDecodeError, AttributeError):
        pass

    # Marker-based discovery for Meminit-generated Markdown views. This
    # catches historical custom catalog names without touching user files.
    for candidate in index_dir.glob("*.md"):
        try:
            first_line = candidate.read_text(encoding="utf-8").splitlines()[:1]
        except OSError:
            continue
        if first_line and first_line[0] in {
            "<!-- MEMINIT_GENERATED: catalog -->",
            "<!-- MEMINIT_GENERATED: kanban -->",
        }:
            known.add(candidate)

    for path in known:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def _build_persisted_index_payload(
    *,
    layout_namespaces: Sequence[Any],
    document_count: int,
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]],
    advice: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build the stable on-disk index artifact.

    Persisted index files are committed and consumed across environments, so
    runtime-only correlation metadata belongs in CLI JSON output, not here.
    """
    return {
        "output_schema_version": OUTPUT_SCHEMA_VERSION_V2,
        "success": True,
        "command": "index",
        "data": {
            "index_version": "1.0",
            "graph_schema_version": "1.0",
            "node_count": len(nodes),
            "edge_count": len(edges),
            "namespaces": [
                {
                    "namespace": ns.namespace,
                    "docs_root": ns.docs_root,
                    "repo_prefix": ns.repo_prefix,
                }
                for ns in layout_namespaces
            ],
            "document_count": document_count,
            "nodes": nodes,
            "edges": edges,
        },
        "warnings": warnings,
        "violations": [],
        "advice": advice,
    }


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IndexBuildReport:
    index_path: Path
    document_count: int
    catalog_path: Optional[Path] = None
    kanban_path: Optional[Path] = None
    kanban_css_path: Optional[Path] = None
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    documents: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)
    advice: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Composite grouping
# ---------------------------------------------------------------------------

_GROUP_ORDER = [
    "Active Work",
    "Governance Pending",
    "Reference",
    "Done",
    "Superseded",
]


def _assign_group(doc_status: str, impl_state: Optional[str]) -> str:
    """Assign a composite group label using status + impl_state grouping rules."""
    status_lower = (doc_status or "").strip().lower()
    state_lower = (impl_state or "").strip().lower()

    if status_lower == "superseded":
        return "Superseded"

    if impl_state and state_lower == "done":
        return "Done"

    if impl_state and state_lower in (
        "in progress",
        "blocked",
        "qa required",
        "not started",
    ):
        return "Active Work"

    if status_lower in ("draft", "in review"):
        return "Governance Pending"

    # Approved docs with no impl_state entry.
    return "Reference"


# ---------------------------------------------------------------------------
# Activity recency
# ---------------------------------------------------------------------------


def _activity_recency(
    frontmatter_updated: Any,
    state_updated: Optional[datetime],
) -> datetime:
    """Compute activity recency as max(state.updated, frontmatter.last_updated)."""
    fm_dt: Optional[datetime] = None
    if isinstance(frontmatter_updated, datetime):
        fm_dt = (
            frontmatter_updated
            if frontmatter_updated.tzinfo
            else frontmatter_updated.replace(tzinfo=timezone.utc)
        )
    elif isinstance(frontmatter_updated, date):
        fm_dt = datetime(
            frontmatter_updated.year,
            frontmatter_updated.month,
            frontmatter_updated.day,
            tzinfo=timezone.utc,
        )
    elif isinstance(frontmatter_updated, str):
        try:
            fm_dt = datetime.fromisoformat(frontmatter_updated)
            if fm_dt.tzinfo is None:
                fm_dt = fm_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    candidates = [dt for dt in (fm_dt, state_updated) if dt is not None]
    if not candidates:
        return datetime.min.replace(tzinfo=timezone.utc)
    return max(candidates)


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def _canonicalize_filter(
    raw_values: Optional[str],
    valid_values: Sequence[str],
    flag_name: str,
) -> Optional[List[str]]:
    """Parse and canonicalize a comma-separated filter string.

    Returns None if *raw_values* is None (no filter applied).
    Raises ``MeminitError`` with ``E_INVALID_FILTER_VALUE`` for unknown values.
    """
    if not raw_values:
        return None
    result: List[str] = []
    seen: set[str] = set()
    for part in raw_values.split(","):
        part = part.strip()
        if not part:
            continue

        # Normalize underscores to spaces for matching (e.g. IN_PROGRESS -> In Progress)
        normalized_part = part.replace("_", " ").lower()

        matched = None
        for valid in valid_values:
            if valid.lower() == normalized_part:
                matched = valid
                break

        if matched is None:
            raise MeminitError(
                code=ErrorCode.E_INVALID_FILTER_VALUE,
                message=f"Unknown {flag_name} value: '{part}'",
                details={
                    "value": part,
                    "valid_values": list(valid_values),
                },
            )

        if matched not in seen:
            result.append(matched)
            seen.add(matched)

    return result or None


VALID_DOC_STATUSES = ["Draft", "In Review", "Approved", "Superseded"]


def _apply_filters(
    entries: List[Dict[str, Any]],
    status_filter: Optional[List[str]],
    impl_state_filter: Optional[List[str]],
) -> List[Dict[str, Any]]:
    """Filter entries by governance status and/or impl_state (AND semantics)."""
    result = entries
    if status_filter:
        result = [e for e in result if e.get("status") in status_filter]
    if impl_state_filter:
        result = [e for e in result if e.get("impl_state") in impl_state_filter]
    return result


# ---------------------------------------------------------------------------
# Catalog (table view) generation
# ---------------------------------------------------------------------------


def _format_md_table(headers: List[str], rows: List[List[str]]) -> str:
    """Format a simple, unpadded Markdown table.

    Padding is not used because different rendering clients (GitHub, MkDocs)
    handle tables uniquely, making raw text padding brittle and cosmetic.
    """
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("-" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _generate_catalog(
    entries: List[Dict[str, Any]],
    generated_at: str,
    status_filter: Optional[List[str]] = None,
    impl_state_filter: Optional[List[str]] = None,
) -> str:
    """Generate catalog table view with dynamic padding and composite grouping."""
    lines: List[str] = []
    lines.append("<!-- MEMINIT_GENERATED: catalog -->")
    lines.append("")
    lines.append("# Project Dashboard")
    lines.append("")
    lines.append(f"_Auto-generated by `meminit index`. Last built: {generated_at}._")
    lines.append("")

    # Filter header (FR-3 amendment).
    filters_active: List[str] = []
    if status_filter:
        filters_active.append(f"status: {', '.join(status_filter)}")
    if impl_state_filter:
        filters_active.append(f"impl_state: {', '.join(impl_state_filter)}")
    if filters_active:
        lines.append(f"**Filters:** {'; '.join(filters_active)}")
        lines.append("")

    # Group entries.
    groups: Dict[str, List[Dict[str, Any]]] = {g: [] for g in _GROUP_ORDER}
    for entry in entries:
        group = _assign_group(entry.get("status", ""), entry.get("impl_state"))
        if group not in groups:
            groups[group] = []
        groups[group].append(entry)

    # Sort within groups by activity recency (descending).
    for group_entries in groups.values():
        group_entries.sort(
            key=lambda e: e.get("_recency", datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True,
        )

    headers = [
        "ID",
        "Title",
        "Type",
        "Doc Status",
        "Impl State",
        "Last Active",
        "Owner",
    ]

    for group_name in _GROUP_ORDER:
        group_entries = groups.get(group_name, [])
        lines.append(f"## {group_name}")
        lines.append("")

        if not group_entries:
            lines.append("_No documents currently in this state._")
            lines.append("")
            continue

        rows = []
        for entry in group_entries:
            recency: Optional[datetime] = entry.get("_recency")
            last_active = recency.strftime("%Y-%m-%d") if recency else ""

            # Fields like title, owner are already HTML escaped during scan.
            # Others like document_id, type, status, impl_state MUST be escaped here
            # because they are rendered directly in the Markdown table (which can render HTML).
            row = [
                escape_markdown_table(sanitize_html(str(entry.get("document_id", "")))),
                escape_markdown_table(entry.get("title", "")),
                escape_markdown_table(sanitize_html(str(entry.get("type", "")))),
                escape_markdown_table(sanitize_html(str(entry.get("status", "")))),
                escape_markdown_table(sanitize_html(str(entry.get("impl_state", "")))),
                last_active,
                escape_markdown_table(entry.get("owner", "")),
            ]
            rows.append(row)

        lines.append(_format_md_table(headers, rows))
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Kanban (board view) generation
# ---------------------------------------------------------------------------

_KANBAN_COLUMNS = ["Not Started", "In Progress", "Blocked", "QA Required", "Done"]


def _generate_kanban(
    entries: List[Dict[str, Any]],
    generated_at: str,
    project_name: str,
    root_dir: Path,
    index_dir: Path,
) -> str:
    """Generate kanban.md content (FR-4).

    Structure:
    1. Pure Markdown fallback (wrapped in div.kanban-fallback, hidden by CSS)
    2. Enhanced HTML kanban board
    """
    lines: List[str] = []
    lines.append("<!-- MEMINIT_GENERATED: kanban -->")
    lines.append("")
    lines.append(f"# {project_name} Project Status Board")
    lines.append("")
    # Link the stylesheet for HTML renderers (MkDocs, local browsers).
    lines.append('<link rel="stylesheet" href="kanban.css">')
    lines.append("")
    lines.append(
        '> Use `meminit state set <ID> [--impl-state "<state>"] [--notes "<text>"]` to update items.'
    )
    lines.append(
        "> Use `meminit state --help` for available commands."
    )
    lines.append("")
    lines.append(f"_Auto-generated by `meminit index`. Last built: {generated_at}._")
    lines.append("")

    # Bucket entries by impl_state. Preserve custom states as-is.
    columns: Dict[str, List[Dict[str, Any]]] = {col: [] for col in _KANBAN_COLUMNS}
    for entry in entries:
        impl = entry.get("impl_state", "")
        if not impl:
            continue
        resolved = ImplState.from_string(impl)
        col = resolved.value if resolved else str(impl).strip()
        if not col:
            col = "Not Started"
        if col not in columns:
            columns[col] = []
        columns[col].append(entry)
    ordered_columns = _KANBAN_COLUMNS + sorted(
        [c for c in columns.keys() if c not in _KANBAN_COLUMNS]
    )

    # --- Pure Markdown fallback ---
    lines.append('<div class="kanban-fallback">')
    lines.append("")
    for col_name in ordered_columns:
        col_entries = columns.get(col_name, [])
        col_name_md = sanitize_html(str(col_name))
        lines.append(f"## {col_name_md}")
        lines.append("")
        if not col_entries:
            lines.append("_No items._")
            lines.append("")
        else:
            for entry in col_entries:
                doc_id = sanitize_field(
                    entry.get("document_id", ""), max_length=None, html_escape=True
                )
                doc_id = doc_id or ""
                title = sanitize_field(
                    entry.get("_raw_title", entry.get("title", "")),
                    max_length=None,
                    html_escape=True,
                )
                status = sanitize_field(
                    entry.get("status", ""), max_length=None, html_escape=True
                )
                notes_raw = entry.get("_raw_notes", entry.get("notes"))

                lines.append(f"- **{doc_id}**: {title} ({status})")
                if notes_raw:
                    notes_sanitized = sanitize_field(
                        notes_raw, max_length=500, html_escape=True
                    )
                    if notes_sanitized:
                        lines.append(f"  - {notes_sanitized}")
            lines.append("")
    lines.append("</div>")
    lines.append("")

    # --- Enhanced HTML kanban board (modern) ---
    lines.append(
        '<div class="kanban-board" role="region" aria-label="Project Kanban Board">'
    )
    lines.append("")

    for col_name in ordered_columns:
        col_entries = columns.get(col_name, [])
        col_class = _safe_css_slug(str(col_name), default="not-started")
        col_name_escaped = sanitize_html(str(col_name))

        lines.append(
            f'<section class="kanban-column kanban-{col_class}" aria-label="{col_name_escaped}">'
        )
        lines.append(
            f'<h3>{col_name_escaped} <span class="kanban-count">{len(col_entries)}</span></h3>'
        )

        for entry in col_entries:
            doc_id = sanitize_html(entry.get("document_id", ""))

            doc_path_raw = entry.get("path", "")
            if doc_path_raw:
                try:
                    target_abs = root_dir / doc_path_raw
                    rel_val = os.path.relpath(target_abs, index_dir).replace("\\", "/")
                except (ValueError, OSError):
                    rel_val = ""
            else:
                rel_val = ""

            title_escaped = entry.get("title", "")
            status_raw = entry.get("status", "Draft")
            status_slug = _safe_css_slug(status_raw, default="draft")
            status_escaped = sanitize_html(str(status_raw) if status_raw is not None else "Draft")
            notes_sanitized = entry.get("notes")

            lines.append(f'<article class="kanban-card" aria-label="{title_escaped}">')
            if rel_val:
                lines.append(
                    f'<strong class="card-id"><a href="{sanitize_html(rel_val)}">{doc_id}</a></strong>'
                )
            else:
                lines.append(f'<strong class="card-id">{doc_id}</strong>')
            lines.append(
                f'<span class="card-title kanban-truncate" title="{title_escaped}">{title_escaped}</span>'
            )
            lines.append(
                f'<span class="card-status badge-{status_slug}">{status_escaped}</span>'
            )
            if notes_sanitized:
                lines.append(
                    f'<p class="card-notes kanban-truncate-lines" title="{notes_sanitized}">{notes_sanitized}</p>'
                )
            lines.append("</article>")

        lines.append("</section>")
        lines.append("")

    lines.append("</div>")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Kanban CSS
# ---------------------------------------------------------------------------

KANBAN_CSS = """\
/* MEMINIT_GENERATED: kanban_css */
/* Modern Kanban Board Styles (Glassmorphism & Clean Typography) */

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

.kanban-board {
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  display: flex;
  gap: 1.5rem;
  overflow-x: auto;
  padding: 2rem 0.5rem;
  background: transparent;
}

.kanban-column {
  min-width: 250px;
  flex: 1;
  background: var(--md-code-bg-color, rgba(235, 238, 245, 0.4));
  border-radius: 12px;
  padding: 1rem;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
}

.kanban-count {
  display: inline-block;
  background: rgba(0,0,0,0.1);
  color: inherit;
  border-radius: 9999px;
  padding: 0.1rem 0.6rem;
  font-size: 0.8em;
  font-weight: 600;
  margin-left: 0.5rem;
  vertical-align: middle;
}

.kanban-column h3 {
  margin-top: 0;
  padding-bottom: 0.75rem;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--md-default-fg-color, #222);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.kanban-not-started h3 { border-bottom: 3px solid #94a3b8; }
.kanban-in-progress h3 { border-bottom: 3px solid #3b82f6; }
.kanban-blocked h3 { border-bottom: 3px solid #ef4444; }
.kanban-qa-required h3 { border-bottom: 3px solid #f59e0b; }
.kanban-done h3 { border-bottom: 3px solid #10b981; }

.kanban-card {
  background: var(--md-default-bg-color, #ffffff);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.02);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  position: relative;
  overflow: hidden;
}

.kanban-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 15px rgba(0, 0, 0, 0.06);
}

.card-id {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: var(--md-primary-fg-color, #3b82f6);
}

.card-id a {
  color: inherit;
  text-decoration: none;
}

.card-id a:hover {
  text-decoration: underline;
}

.card-title {
  font-weight: 500;
  font-size: 0.95rem;
  color: var(--md-default-fg-color, #111827);
  line-height: 1.4;
}

.kanban-truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
}

.card-status {
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.25rem 0.6rem;
  border-radius: 4px;
  display: inline-block;
  width: fit-content;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-top: 0.2rem;
}

.badge-draft { background: #e0e7ff; color: #3730a3; border: 1px solid #c7d2fe; }
.badge-in-review { background: #fef08a; color: #854d0e; border: 1px solid #fde047; }
.badge-approved { background: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
.badge-superseded { background: #f3f4f6; color: #374151; border: 1px solid #e5e7eb; }

.card-notes {
  font-size: 0.8rem;
  color: var(--md-default-fg-color--light, #6b7280);
  margin: 0.5rem 0 0;
  line-height: 1.5;
  border-top: 1px dashed rgba(0, 0, 0, 0.08);
  padding-top: 0.5rem;
}

.kanban-truncate-lines {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

@media (max-width: 768px) {
  .kanban-board {
    flex-direction: column;
  }
  .kanban-column {
    min-width: unset;
  }
}

/* Hide fallback when CSS loads */
.kanban-fallback {
  display: none;
}
"""


# ---------------------------------------------------------------------------
# Use case
# ---------------------------------------------------------------------------


class IndexRepositoryUseCase:
    def __init__(
        self,
        root_dir: str,
        *,
        output_catalog: bool = False,
        catalog_name: Optional[str] = None,
        output_kanban: bool = False,
        status_filter: Optional[str] = None,
        impl_state_filter: Optional[str] = None,
    ):
        self._layout = load_repo_layout(root_dir)
        self._root_dir = self._layout.root_dir
        self._output_catalog = output_catalog
        self._catalog_name = catalog_name or getattr(
            self._layout, "catalog_name", "catalog.md"
        )
        self._output_kanban = output_kanban

        valid_statuses = set()
        valid_impl_states = set()
        for ns in self._layout.namespaces:
            valid_statuses.update(ns.valid_doc_statuses)
            valid_impl_states.update(ns.valid_impl_states)
        self._valid_statuses = list(valid_statuses)
        self._valid_impl_states = list(valid_impl_states)

        # Parse and canonicalize filters upfront (raises on invalid values).
        self._status_filter = _canonicalize_filter(
            status_filter, self._valid_statuses, "--status"
        )
        self._impl_state_filter = _canonicalize_filter(
            impl_state_filter, self._valid_impl_states, "--impl-state"
        )

    def execute(self) -> IndexBuildReport:
        any_docs = any(ns.docs_dir.exists() for ns in self._layout.namespaces)
        if not any_docs:
            raise FileNotFoundError(
                "No configured docs roots exist on disk; cannot build index."
            )

        index_path = self._layout.index_file
        ensure_safe_write_path(root_dir=self._root_dir, target_path=index_path)
        index_path.parent.mkdir(parents=True, exist_ok=True)

        warnings_list: List[Dict[str, Any]] = []

        # Load project state (gracefully optional).
        try:
            project_state = load_project_state(self._root_dir)
        except MeminitError as exc:
            from meminit.core.services.project_state import get_state_file_rel_path

            project_state = None
            warnings_list.append(
                {
                    "code": exc.code.value,
                    "message": exc.message,
                    "severity": Severity.ERROR.value,
                    "path": get_state_file_rel_path(self._root_dir),
                    "line": 0,
                }
            )

        # Scan governed documents.
        entries: List[Dict[str, Any]] = []
        known_doc_ids: set[str] = set()
        doc_id_paths: Dict[str, List[str]] = {}  # for duplicate detection
        for ns in self._layout.namespaces:
            if not ns.docs_dir.exists():
                continue
            for path in ns.docs_dir.rglob("*.md"):
                owner = self._layout.namespace_for_path(path)
                if owner is None or owner.namespace.lower() != ns.namespace.lower():
                    continue
                if ns.is_excluded(path):
                    continue
                try:
                    post = frontmatter.load(path)
                except Exception:
                    continue

                doc_id = post.metadata.get("document_id")
                if not isinstance(doc_id, str) or not doc_id.strip():
                    continue
                doc_id = doc_id.strip()
                known_doc_ids.add(doc_id)
                rel_path = path.relative_to(self._root_dir).as_posix()
                doc_id_paths.setdefault(doc_id, []).append(rel_path)

                entry: Dict[str, Any] = {
                    "document_id": doc_id,
                    "path": rel_path,
                    "namespace": ns.namespace,
                    "repo_prefix": ns.repo_prefix,
                    "type": post.metadata.get("type"),
                    "title": sanitize_field(
                        post.metadata.get("title"), max_length=None, html_escape=True
                    ),
                    "_raw_title": post.metadata.get("title"),
                    "status": post.metadata.get("status"),
                    "owner": sanitize_field(
                        post.metadata.get("owner"), max_length=None, html_escape=True
                    ),
                    "last_updated": post.metadata.get("last_updated"),
                    # New graph fields from frontmatter.
                    "area": post.metadata.get("area"),
                    "description": post.metadata.get("description"),
                    "keywords": post.metadata.get("keywords"),
                    "superseded_by": post.metadata.get("superseded_by"),
                    "related_ids": _normalize_related_ids(post.metadata.get("related_ids")),
                }

                # Merge state (additive — new optional fields).
                state_updated: Optional[datetime] = None
                if project_state:
                    state_entry = project_state.get(doc_id)
                    if state_entry:
                        resolved_state = ImplState.from_string(state_entry.impl_state)
                        if resolved_state is not None:
                            entry["impl_state"] = resolved_state.value
                        else:
                            entry["impl_state"] = state_entry.impl_state

                        entry["updated"] = state_entry.updated.isoformat()

                        if state_entry.updated_by and validate_actor(
                            state_entry.updated_by
                        ):
                            entry["updated_by"] = state_entry.updated_by
                        elif state_entry.updated_by == "":
                            entry["updated_by"] = (
                                ""  # preserve explicitly empty string if originally there
                            )

                        if state_entry.notes is not None:
                            sanitized_notes = sanitize_field(
                                state_entry.notes,
                                max_length=MAX_NOTES_LENGTH,
                                html_escape=True,
                            )
                            if sanitized_notes:
                                entry["notes"] = sanitized_notes
                                entry["_raw_notes"] = state_entry.notes

                        state_updated = state_entry.updated

                # Capture body for reference edge extraction (stripped before JSON output).
                entry["_body"] = post.content

                # Compute activity recency (used for sorting, not stored in JSON) - always calculate
                entry["_recency"] = _activity_recency(
                    entry.get("last_updated"),
                    state_updated,
                )

                entries.append(entry)

        # --- Graph pipeline ---

        # Build path → doc_id map and extract edges.
        path_to_doc_id = {e["path"]: e["document_id"] for e in entries}
        all_edges = graph.build_edge_set(entries, path_to_doc_id, self._root_dir)

        # Run graph integrity validation (checks duplicates, cycles, dangling refs, etc.).
        graph_warnings, graph_advice, graph_fatal = graph.validate_graph_integrity(
            entries, all_edges, known_doc_ids, doc_id_paths,
        )
        catalog_out_name = Path(self._catalog_name).name if self._output_catalog else None
        if graph_fatal:
            # Invalidate all stale generated artifacts so downstream
            # commands and human readers don't see outputs from a
            # previous successful run while the repo is unindexable.
            index_dir = self._layout.index_file.parent
            _remove_stale_artifacts(
                index_dir,
                catalog_name=catalog_out_name,
                remove_index=True,
            )

            fatal_code_str = graph_fatal[0].get("code", "GRAPH_DUPLICATE_DOCUMENT_ID")
            try:
                fatal_code = ErrorCode(fatal_code_str)
            except ValueError:
                fatal_code = ErrorCode.GRAPH_DUPLICATE_DOCUMENT_ID
            raise MeminitError(
                code=fatal_code,
                message=graph_fatal[0]["message"],
                details={"errors": graph_fatal},
            )

        warnings_list.extend(graph_warnings)

        # Validate project state (advisory warnings).
        if project_state:
            validation_issues = validate_project_state(
                project_state, known_doc_ids, self._root_dir, self._valid_impl_states
            )
            for issue in validation_issues:
                # Do not raise MeminitError here! Allow it to be passed through as severity="error".
                warnings_list.append(
                    {
                        "code": issue.rule,
                        "message": issue.message,
                        "severity": issue.severity.value,
                        "path": issue.file,
                        "line": issue.line,
                    }
                )

        # Apply filters.
        filtered = _apply_filters(entries, self._status_filter, self._impl_state_filter)

        # Remove stale generated side views from previous runs before writing
        # the current optional outputs. This keeps successful reruns from
        # leaving obsolete catalog/kanban files behind when flags change.
        _remove_stale_artifacts(
            index_path.parent,
            catalog_name=catalog_out_name,
            remove_index=False,
        )

        # Write main index JSON (recency/body fields stripped — internal only).
        # Keep canonical JSON unfiltered for downstream commands that depend on
        # full repository inventory (resolve/identify/link). Filters are for
        # command output and generated views only.
        sorted_entries = sorted(entries, key=lambda e: e.get("document_id", ""))
        json_nodes = [
            {k: v for k, v in e.items() if not k.startswith("_")}
            for e in sorted_entries
        ]
        json_edges = [e.to_dict() for e in all_edges]
        canonical_warnings = canonicalize_warning_list(warnings_list)
        canonical_advice = canonicalize_advice_list(graph_advice)

        payload = _build_persisted_index_payload(
            layout_namespaces=self._layout.namespaces,
            document_count=len(json_nodes),
            nodes=json_nodes,
            edges=json_edges,
            warnings=canonical_warnings,
            advice=canonical_advice,
        )
        index_path.write_text(
            json.dumps(payload, indent=2, default=_json_default) + "\n",
            encoding="utf-8",
        )

        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Generate catalog view (FR-3).
        catalog_path: Optional[Path] = None
        if self._output_catalog:
            catalog_path = index_path.parent / catalog_out_name
            ensure_safe_write_path(root_dir=self._root_dir, target_path=catalog_path)
            catalog_content = _generate_catalog(
                filtered,
                generated_at,
                status_filter=self._status_filter,
                impl_state_filter=self._impl_state_filter,
            )
            catalog_path.write_text(catalog_content, encoding="utf-8")

        # Generate kanban.md + kanban.css (FR-4).
        kanban_path: Optional[Path] = None
        kanban_css_path: Optional[Path] = None
        if self._output_kanban:
            kanban_path = index_path.parent / "kanban.md"
            ensure_safe_write_path(root_dir=self._root_dir, target_path=kanban_path)
            kanban_content = _generate_kanban(
                filtered,
                generated_at,
                project_name=self._layout.project_name,
                root_dir=self._root_dir,
                index_dir=index_path.parent,
            )
            kanban_path.write_text(kanban_content, encoding="utf-8")

            kanban_css_path = index_path.parent / "kanban.css"
            ensure_safe_write_path(root_dir=self._root_dir, target_path=kanban_css_path)
            kanban_css_path.write_text(KANBAN_CSS, encoding="utf-8")

        # Prepare filtered JSON entries for the report/stdout output
        sorted_filtered = sorted(filtered, key=lambda e: e.get("document_id", ""))
        sorted_filtered.sort(
            key=lambda e: e.get("_recency", datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True,
        )
        json_filtered = [
            {k: v for k, v in e.items() if not k.startswith("_")}
            for e in sorted_filtered
        ]

        return IndexBuildReport(
            index_path=index_path,
            document_count=len(filtered),
            catalog_path=catalog_path,
            kanban_path=kanban_path,
            kanban_css_path=kanban_css_path,
            warnings=canonical_warnings,
            documents=json_filtered,
            edges=json_edges,
            advice=canonical_advice,
        )
