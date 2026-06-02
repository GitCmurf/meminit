"""Service for index artifact generation (catalog, kanban)."""

import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

from meminit.core.services.project_state import ImplState
from meminit.core.services.sanitization import escape_markdown_table, sanitize_field, sanitize_html


class IndexViewService:
    """Service for generating index views (catalog markdown, kanban)."""

    # Constants for catalog grouping
    _GROUP_ORDER = [
        "Active Work",
        "Governance Pending",
        "Reference",
        "Done",
        "Superseded",
    ]

    @staticmethod
    def _safe_css_slug(value: str, *, default: str = "unknown") -> str:
        """Return a conservative CSS-safe slug for class names."""
        slug = re.sub(r"[^a-z0-9_-]+", "-", str(value).strip().lower())
        slug = re.sub(r"-{2,}", "-", slug).strip("-")
        return slug or default

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def _catalog_frontmatter(generated_at: str, repo_prefix: str, owner: str = "__TBD__") -> List[str]:
        """Return governed frontmatter for the generated catalog artifact."""
        generated_date = generated_at[:10]
        return [
            "---",
            f"document_id: {repo_prefix}-INDEX-001",
            "type: INDEX",
            "title: Project Dashboard",
            "status: Draft",
            'version: "1.0"',
            f"last_updated: {generated_date}",
            f"owner: {owner}",
            'docops_version: "2.0"',
            "---",
            "",
        ]

    @staticmethod
    def _kanban_sort_key(entry: Dict[str, Any]) -> Tuple:
        """Compute sort key for kanban cards."""
        from meminit.core.services.state_derived import PRIORITY_RANK

        priority = entry.get("priority", "P2") or "P2"
        priority_rank = PRIORITY_RANK.get(priority, PRIORITY_RANK["P2"])
        unblocks_count = -len(entry.get("unblocks", []))
        updated_str = entry.get("updated", "")
        try:
            updated_dt = datetime.fromisoformat(updated_str)
            updated_ts = updated_dt.astimezone(timezone.utc).timestamp()
        except (ValueError, TypeError):
            updated_ts = 0.0
        doc_id = entry.get("document_id", "")
        return (priority_rank, unblocks_count, updated_ts, doc_id)

    @staticmethod
    def _kanban_badge_prefix(entry: Dict[str, Any]) -> str:
        """Generate badge prefix based on priority and blockers."""
        parts: List[str] = []
        priority = entry.get("priority")
        if priority:
            parts.append(f"[{priority}]")
        open_blockers = entry.get("open_blockers", [])
        if open_blockers:
            parts.append("[blocked]")
        return "".join(parts) + " " if parts else ""

    @staticmethod
    def _kanban_header(project_name: str, generated_at: str) -> List[str]:
        """Generate kanban header with generated marker and metadata."""
        lines: List[str] = []
        lines.append("<!-- MEMINIT_GENERATED: kanban -->")
        lines.append("")
        lines.append(f"# {project_name} Project Status Board")
        lines.append("")
        lines.append('<link rel="stylesheet" href="kanban.css">')
        lines.append("")
        lines.append(
            '> Use `meminit state set <ID> [--impl-state "<state>"] [--notes "<text>"]` to update items.'
        )
        lines.append("> Use `meminit state --help` for available commands.")
        lines.append("")
        lines.append(f"_Auto-generated by `meminit index`. Last built: {generated_at}._")
        lines.append("")
        return lines

    def _kanban_bucket_columns(
        self,
        entries: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], List[str]]:
        """Bucket documents into kanban columns based on impl_state."""
        _KANBAN_COLUMNS = ["Not Started", "In Progress", "Blocked", "QA Required", "Done"]
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
        for col_name in columns:
            columns[col_name].sort(key=self._kanban_sort_key)
        ordered_columns = _KANBAN_COLUMNS + sorted(
            [c for c in columns.keys() if c not in _KANBAN_COLUMNS]
        )
        return columns, ordered_columns

    def _kanban_fallback_section(
        self,
        columns: Dict[str, List[Dict[str, Any]]],
        ordered_columns: List[str],
    ) -> List[str]:
        """Generate Markdown fallback section for kanban."""
        lines: List[str] = []
        lines.append('<div class="kanban-fallback">')
        lines.append("")
        for col_name in ordered_columns:
            col_entries = columns.get(col_name, [])
            lines.append(f"## {sanitize_html(str(col_name))}")
            lines.append("")
            if not col_entries:
                lines.append("_No items._")
                lines.append("")
            else:
                for entry in col_entries:
                    lines.extend(self._kanban_fallback_card(entry))
        lines.append("</div>")
        lines.append("")
        return lines

    def _kanban_fallback_card(self, entry: Dict[str, Any]) -> List[str]:
        """Generate Markdown card for fallback kanban."""
        lines: List[str] = []
        doc_id = sanitize_field(entry.get("document_id", ""), max_length=None, html_escape=True) or ""
        title = sanitize_field(
            entry.get("_raw_title", entry.get("title", "")),
            max_length=None,
            html_escape=True,
        )
        status = sanitize_field(entry.get("status", ""), max_length=None, html_escape=True)
        notes_raw = entry.get("_raw_notes", entry.get("notes"))
        badges = self._kanban_badge_prefix(entry)
        lines.append(f"- **{doc_id}**: {badges}{title} ({status})")
        if notes_raw:
            notes_sanitized = sanitize_field(notes_raw, max_length=500, html_escape=True)
            if notes_sanitized:
                lines.append(f"  - {notes_sanitized}")
        return lines

    def _kanban_html_board(
        self,
        columns: Dict[str, List[Dict[str, Any]]],
        ordered_columns: List[str],
        root_dir: Path,
        index_dir: Path,
    ) -> List[str]:
        """Generate HTML board section for kanban."""
        lines: List[str] = []
        lines.append('<div class="kanban-board" role="region" aria-label="Project Kanban Board">')
        lines.append("")
        for col_name in ordered_columns:
            col_entries = columns.get(col_name, [])
            col_class = self._safe_css_slug(str(col_name), default="not-started")
            col_name_escaped = sanitize_html(str(col_name))
            lines.append(
                f'<section class="kanban-column kanban-{col_class}" aria-label="{col_name_escaped}">'
            )
            lines.append(
                f'<h3>{col_name_escaped} <span class="kanban-count">{len(col_entries)}</span></h3>'
            )
            for entry in col_entries:
                lines.extend(self._kanban_html_card(entry, root_dir, index_dir))
            lines.append("</section>")
            lines.append("")
        lines.append("</div>")
        lines.append("")
        return lines

    def _kanban_html_card(
        self,
        entry: Dict[str, Any],
        root_dir: Path,
        index_dir: Path,
    ) -> List[str]:
        """Generate HTML card for a single kanban entry."""
        lines: List[str] = []
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
        title_escaped = sanitize_html(str(entry.get("_raw_title", entry.get("title", ""))))
        status_raw = entry.get("status", "Draft")
        status_slug = self._safe_css_slug(status_raw, default="draft")
        status_escaped = sanitize_html(str(status_raw) if status_raw is not None else "Draft")
        notes_escaped = (
            sanitize_html(str(entry.get("_raw_notes", entry.get("notes"))))
            if (entry.get("notes") or entry.get("_raw_notes"))
            else None
        )
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
        lines.append(f'<span class="card-status badge-{status_slug}">{status_escaped}</span>')
        priority_val = entry.get("priority")
        if priority_val:
            priority_slug = self._safe_css_slug(str(priority_val), default="unknown")
            lines.append(
                f'<span class="card-priority badge-priority-{priority_slug}">{sanitize_html(priority_val)}</span>'
            )
        open_blockers = entry.get("open_blockers", [])
        if open_blockers:
            lines.append(
                f'<span class="card-blocked badge-blocked">{len(open_blockers)} blocked</span>'
            )
        if notes_escaped:
            lines.append(
                f'<p class="card-notes kanban-truncate-lines" title="{notes_escaped}">{notes_escaped}</p>'
            )
        lines.append("</article>")
        return lines

    @staticmethod
    def _get_kanban_css() -> str:
        """Return the CSS for kanban board styling."""
        return """\
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

    def generate_catalog(
        self,
        entries: List[Dict[str, Any]],
        generated_at: str,
        repo_prefix: str,
        status_filter: Optional[List[str]] = None,
        impl_state_filter: Optional[List[str]] = None,
    ) -> str:
        """Generate catalog markdown content with frontmatter and grouping."""
        lines: List[str] = []
        lines.extend(self._catalog_frontmatter(generated_at, repo_prefix))
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
        groups: Dict[str, List[Dict[str, Any]]] = {g: [] for g in self._GROUP_ORDER}
        for entry in entries:
            group = self._assign_group(entry.get("status", ""), entry.get("impl_state"))
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
            "Priority",
            "Ready",
            "Last Active",
            "Owner",
        ]

        for group_name in self._GROUP_ORDER:
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

                priority = entry.get("priority", "")
                if not priority:
                    priority = "\u2014"

                ready_val = entry.get("ready")
                if ready_val is True:
                    ready_display = "\u2705"
                elif ready_val is False and entry.get("open_blockers"):
                    ready_display = "\u23f3"
                else:
                    ready_display = "\u2014"

                row = [
                    escape_markdown_table(sanitize_html(str(entry.get("document_id", "")))),
                    escape_markdown_table(entry.get("title", "")),
                    escape_markdown_table(sanitize_html(str(entry.get("type", "")))),
                    escape_markdown_table(sanitize_html(str(entry.get("status", "")))),
                    escape_markdown_table(sanitize_html(str(entry.get("impl_state", "")))),
                    priority,
                    ready_display,
                    last_active,
                    escape_markdown_table(entry.get("owner", "")),
                ]
                rows.append(row)

            lines.append(self._format_md_table(headers, rows))
            lines.append("")

        return "\n".join(lines)

    def generate_kanban(
        self,
        entries: List[Dict[str, Any]],
        generated_at: str,
        project_name: str,
        root_dir: Path,
        index_dir: Path,
    ) -> str:
        """Generate kanban.md content (FR-4)."""
        lines = self._kanban_header(project_name, generated_at)
        columns, ordered_columns = self._kanban_bucket_columns(entries)
        lines.extend(self._kanban_fallback_section(columns, ordered_columns))
        lines.extend(self._kanban_html_board(columns, ordered_columns, root_dir, index_dir))
        return "\n".join(lines)

    def get_kanban_css(self) -> str:
        """Return the CSS for kanban board styling."""
        return self._get_kanban_css()