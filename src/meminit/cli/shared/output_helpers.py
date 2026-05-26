"""Shared output helpers for Meminit CLI commands.

Extracted from main.py to improve modularity and reduce monolith risk.
Contains ~500 lines of formatting, rendering, and error handling utilities.
"""

from __future__ import annotations

import click
import contextlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from click import get_current_context
from rich.console import Console

from meminit.core.services.output_contracts import OUTPUT_SCHEMA_VERSION_V2, OUTPUT_SCHEMA_VERSION_V3
from meminit.core.services.output_formatter import format_error_envelope
from meminit.core.services.error_codes import ErrorCode
from meminit.core.exceptions import MeminitError
from meminit.core.services.observability import get_current_run_id
from meminit.cli.streaming import write_ndjson_error, unsupported_ndjson
from meminit.core.services.output_formatter import normalize_correlation_id


# ---------------------------------------------------------------------------
# Rich Console Singleton
# ---------------------------------------------------------------------------

console = Console()


def get_console() -> Console:
    """Helper to get the rich console from context if available."""
    try:
        ctx = get_current_context(silent=True)
        if ctx and hasattr(ctx, "obj") and isinstance(ctx.obj, dict) and "console" in ctx.obj:
            return ctx.obj["console"]
    except Exception:
        pass
    return console


# ---------------------------------------------------------------------------
# Error Handling and Output Envelope
# ---------------------------------------------------------------------------

def _extract_envelope_metadata(output_str: str) -> Optional[Dict[str, Any]]:
    """Parse a CLI envelope string and extract metadata fields for error rebuilding.

    Returns None if the string is not a valid envelope.
    """
    try:
        payload = json.loads(output_str)
    except Exception:
        return None
    if (
        isinstance(payload, dict)
        and payload.get("output_schema_version")
        in (OUTPUT_SCHEMA_VERSION_V2, OUTPUT_SCHEMA_VERSION_V3)
        and isinstance(payload.get("command"), str)
    ):
        return payload
    return None


def _unexpected_error_details(exc: Exception) -> Dict[str, Any]:
    """Return public, non-sensitive details for an unexpected exception."""
    return {"exception": exc.__class__.__name__}


# ---------------------------------------------------------------------------
# Output Writing and Capture
# ---------------------------------------------------------------------------

def is_safe_cli_output_path(path: Path) -> bool:
    """Validate that a CLI output path does not escape the intended directory."""
    try:
        resolved = path.resolve()
        # Simple safety: reject if path tries to escape parent directories
        parts = resolved.parts
        for part in parts:
            if part == "..":
                return False
        return True
    except Exception:
        return False


def _write_output(
    output_str: str,
    output: Optional[str] = None,
    append: bool = False,
    add_newline: bool = True,
) -> None:
    """Write output to stdout or to a file if requested."""
    if output:
        out_path = Path(output)
        if not is_safe_cli_output_path(out_path):
            raise SystemExit(1)
        mode = "a" if append else "w"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, mode, encoding="utf-8") as f:
            f.write(output_str)
            if add_newline:
                f.write("\n")
    else:
        click.echo(output_str, nl=add_newline)


@contextlib.contextmanager
def maybe_capture(output: Optional[str], format: str):
    """Capture console output if output file is specified and format is text."""
    if format == "text" and output:
        capture_obj = None
        try:
            with get_console().capture() as capture:
                capture_obj = capture
                yield
        finally:
            if capture_obj:
                captured_text = capture_obj.get()
                if captured_text.strip():
                    _write_output(
                        captured_text,
                        output=output,
                        append=True,
                        add_newline=False,
                    )
    else:
        yield


# ---------------------------------------------------------------------------
# Markdown Formatting Utilities
# ---------------------------------------------------------------------------

def _md_escape(value: object) -> str:
    """Escape characters for safe embedding inside Markdown table cells."""
    text = "" if value is None else str(value)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


_MD_INLINE_SPECIAL = str.maketrans(
    {
        "\\": "\\\\",
        "*": "\\*",
        "_": "\\_",
        "[": "\\[",
        "]": "\\]",
        "`": "\\`",
        "|": "\\|",
        "<": "&lt;",
        ">": "&gt;",
        "&": "&amp;",
        "\n": " ",
    }
)


def _md_inline(value: object) -> str:
    """Escape a value for safe embedding inside Markdown inline contexts."""
    text = "" if value is None else str(value)
    return text.translate(_MD_INLINE_SPECIAL)


def _md_table(headers: List[str], rows: List[List[str]]) -> str:
    """Build a complete Markdown pipe-delimited table string."""
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        escaped = [_md_escape(cell) for cell in row]
        lines.append("| " + " | ".join(escaped) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Index Data Shaping Utilities
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IndexEdge:
    """Lightweight edge representation for filtering."""
    source: str
    target: str
    type_: str


def _filter_index_edges(
    edges: List[IndexEdge], visible_ids: set
) -> List[IndexEdge]:
    """Filter index edges to only include edges whose source/target are visible."""
    return [
        e
        for e in edges
        if e.source in visible_ids and e.target in visible_ids
    ]


def _flatten_warning_groups(warning_groups: List[Dict]) -> List[Dict]:
    """Flatten grouped warnings into flat list."""
    flat = []
    for group in warning_groups:
        path = group.get("path")
        for w in group.get("warnings", []):
            flat.append(
                {
                    "code": w.get("code"),
                    "path": path,
                    "message": w.get("message"),
                    "line": w.get("line"),
                }
            )
    return flat


def get_severity_value(severity: Any) -> str:
    """Extract string value from severity enum or plain string."""
    if isinstance(severity, str):
        return severity
    if hasattr(severity, "value"):
        return severity.value
    return str(severity)


# ---------------------------------------------------------------------------
# State Rendering Functions
# ---------------------------------------------------------------------------

def _render_warnings_text(warnings, format, output):
    """Render a list of warnings in Markdown or Rich console format."""
    if not warnings:
        return
    if format == "md":
        lines = "\n## Warnings\n"
        for w in warnings:
            lines += f"- **{_md_inline(w.get('code', 'UNKNOWN'))}**: {_md_inline(w.get('message', ''))}\n"
        _write_output(lines, output)
    else:
        for w in warnings:
            get_console().print(
                f"[yellow][{w.get('code', 'UNKNOWN')}] {w.get('message', '')}[/yellow]"
            )


def _render_state_set_json(result, output):
    """Format a state set result into a JSON envelope and write it."""
    from meminit.core.services.output_formatter import format_envelope

    _write_output(
        format_envelope(
            command="state set",
            data={
                "document_id": result.document_id,
                "action": result.action,
                "entry": result.entry,
                "warnings": result.warnings or [],
            },
        ),
        output,
    )


def _render_state_list_json(result, output):
    """Format a state list result into a JSON envelope and write it."""
    from meminit.core.services.output_formatter import format_envelope

    _write_output(
        format_envelope(
            command="state list",
            data={
                "document_id": result.document_id,
                "entry": result.entry,
                "warnings": result.warnings or [],
            },
        ),
        output,
    )


def _render_state_next_json(result, output):
    """Format a state next result into a JSON envelope and write it."""
    from meminit.core.services.output_formatter import format_envelope

    _write_output(
        format_envelope(
            command="state next",
            data={
                "document_id": result.document_id,
                "next_action": result.next_action,
                "assignee": result.assignee,
                "priority": result.priority,
            },
        ),
        output,
    )


def _render_state_blockers_json(result, output):
    """Format a state blockers result into a JSON envelope and write it."""
    from meminit.core.services.output_formatter import format_envelope

    _write_output(
        format_envelope(
            command="state blockers",
            data={
                "document_id": result.document_id,
                "blockers": result.blockers or [],
                "blocked_by": result.blocked_by or [],
            },
        ),
        output,
    )


def _render_state_set_text(result, format, output):
    """Render the state set result as Markdown or Rich console text."""
    if format == "md":
        if result.action == "clear":
            lines = (
                f"# Meminit State Set\n\n"
                f"- Document ID: `{result.document_id}`\n"
                f"- Action: Cleared\n"
            )
        else:
            lines = (
                f"# Meminit State Set\n\n"
                f"- Document ID: `{result.document_id}`\n"
                f"- Impl State: {_md_inline(result.entry.get('impl_state', ''))}\n"
                f"- Updated By: {_md_inline(result.entry.get('updated_by', ''))}\n"
            )
            if result.entry.get("priority"):
                lines += f"- Priority: {_md_inline(result.entry.get('priority'))}\n"
            if result.entry.get("assignee"):
                lines += f"- Assignee: {_md_inline(result.entry.get('assignee'))}\n"
            if result.entry.get("next_action"):
                lines += f"- Next Action: {_md_inline(result.entry.get('next_action'))}\n"
            if result.entry.get("notes"):
                lines += f"- Notes: {_md_inline(result.entry.get('notes'))}\n"
        if result.warnings:
            lines += "\n## Warnings\n"
            for w in result.warnings:
                lines += f"- **{_md_inline(w.get('code', 'UNKNOWN'))}**: {_md_inline(w.get('message', ''))}\n"
        _write_output(lines, output)
        return

    with maybe_capture(output, format):
        if result.action == "clear":
            get_console().print(
                f"[bold yellow]Cleared state for {result.document_id}[/bold yellow]"
            )
        else:
            get_console().print(f"[bold green]Updated state for {result.document_id}[/bold green]")
            get_console().print(f"Impl State: {result.entry.get('impl_state', '')}")
            get_console().print(f"Updated By: {result.entry.get('updated_by', '')}")
            if result.entry.get("priority"):
                get_console().print(f"Priority: {result.entry.get('priority')}")
            if result.entry.get("assignee"):
                get_console().print(f"Assignee: {result.entry.get('assignee')}")
            if result.entry.get("next_action"):
                get_console().print(f"Next Action: {result.entry.get('next_action')}")
            if result.entry.get("notes"):
                get_console().print(f"Notes: {result.entry.get('notes')}")
        _render_warnings_text(result.warnings, format, output)


def _render_state_list_text(result, format, output):
    """Render the state list result as Markdown or Rich console text."""
    if format == "md":
        lines = f"# Meminit State for {result.document_id}\n\n"
        lines += f"- Impl State: {_md_inline(result.entry.get('impl_state', 'None'))}\n"
        lines += f"- Updated By: {_md_inline(result.entry.get('updated_by', 'None'))}\n"
        lines += f"- Priority: {_md_inline(result.entry.get('priority', 'None'))}\n"
        lines += f"- Assignee: {_md_inline(result.entry.get('assignee', 'None'))}\n"
        lines += f"- Next Action: {_md_inline(result.entry.get('next_action', 'None'))}\n"
        lines += f"- Depends On: {_md_inline(result.entry.get('depends_on', 'None'))}\n"
        lines += f"- Blocked By: {_md_inline(result.entry.get('blocked_by', 'None'))}\n"
        if result.entry.get("notes"):
            lines += f"- Notes: {_md_inline(result.entry.get('notes'))}\n"
        if result.entry.get("next_action"):
            lines += f"- Notes: {_md_inline(result.entry.get('next_action'))}\n"
        if result.warnings:
            lines += "\n## Warnings\n"
            for w in result.warnings:
                lines += f"- **{_md_inline(w.get('code', 'UNKNOWN'))}**: {_md_inline(w.get('message', ''))}\n"
        _write_output(lines, output)
        return

    with maybe_capture(output, format):
        get_console().print(f"[bold]State for {result.document_id}[/bold]")
        get_console().print(f"  Impl State: {result.entry.get('impl_state', 'None')}")
        get_console().print(f"  Updated By: {result.entry.get('updated_by', 'None')}")
        get_console().print(f"  Priority: {result.entry.get('priority', 'None')}")
        get_console().print(f"  Assignee: {result.entry.get('assignee', 'None')}")
        get_console().print(f"  Next Action: {result.entry.get('next_action', 'None')}")
        get_console().print(f"  Depends On: {result.entry.get('depends_on', 'None')}")
        get_console().print(f"  Blocked By: {result.entry.get('blocked_by', 'None')}")
        if result.entry.get("notes"):
            get_console().print(f"  Notes: {result.entry.get('notes')}")
        if result.entry.get("next_action"):
            get_console().print(f"  Next Action: {result.entry.get('next_action')}")
        _render_warnings_text(result.warnings, format, output)


def _render_state_next_text(result, format, output):
    """Render the state next result as Markdown or Rich console text."""
    if format == "md":
        lines = f"# Next Action for {result.document_id}\n\n"
        lines += f"- Next Action: {_md_inline(result.next_action)}\n"
        lines += f"- Assignee: {_md_inline(result.assignee)}\n"
        lines += f"- Priority: {_md_inline(result.priority)}\n"
        _write_output(lines, output)
        return

    with maybe_capture(output, format):
        get_console().print(f"[bold]Next Action for {result.document_id}[/bold]")
        get_console().print(f"  Next Action: {result.next_action}")
        get_console().print(f"  Assignee: {result.assignee}")
        get_console().print(f"  Priority: {result.priority}")


def _render_state_blockers_text(result, format, output):
    """Render the state blockers result as Markdown or Rich console text."""
    if format == "md":
        lines = f"# Blockers for {result.document_id}\n\n"
        if result.blockers:
            lines += "## This Document Blocks\n\n"
            for blocker in result.blockers:
                lines += f"- {_md_inline(blocker)}\n"
        else:
            lines += "## This Document Blocks\n\nNone\n"
        if result.blocked_by:
            lines += "\n## This Document Is Blocked By\n\n"
            for blocked in result.blocked_by:
                lines += f"- {_md_inline(blocked)}\n"
        else:
            lines += "\n## This Document Is Blocked By\n\nNone\n"
        _write_output(lines, output)
        return

    with maybe_capture(output, format):
        get_console().print(f"[bold]Blockers for {result.document_id}[/bold]")
        get_console().print("\n[bold]This Document Blocks:[/bold]")
        if result.blockers:
            for blocker in result.blockers:
                get_console().print(f"  - {blocker}")
        else:
            get_console().print("  None")
        get_console().print("\n[bold]This Document Is Blocked By:[/bold]")
        if result.blocked_by:
            for blocked in result.blocked_by:
                get_console().print(f"  - {blocked}")
        else:
            get_console().print("  None")