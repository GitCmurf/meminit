"""Shared output helpers for Meminit CLI commands.

Extracted from src/meminit/cli/main.py to improve modularity.
Contains ~513 lines of formatting, rendering, and error handling utilities.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

import click
from rich.console import Console

from meminit.core.services.output_contracts import (
    OUTPUT_SCHEMA_VERSION_V2,
    OUTPUT_SCHEMA_VERSION_V3,
)
from meminit.core.services.output_formatter import format_envelope, format_error_envelope
from meminit.core.services.error_codes import ErrorCode
from meminit.core.services.exit_codes import EX_CANTCREAT, exit_code_for_error
from meminit.core.services.path_utils import is_safe_cli_output_path


# ---------------------------------------------------------------------------
# Rich Console Singleton
# ---------------------------------------------------------------------------

console = Console()


def get_console() -> Console:
    """Helper to get the rich console from context if available."""
    try:
        ctx = click.get_current_context(silent=True)
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
    from meminit.core.services.output_contracts import (
        OUTPUT_SCHEMA_VERSION_V2,
        OUTPUT_SCHEMA_VERSION_V3,
    )

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
            payload = _extract_envelope_metadata(output_str)
            if payload is not None:
                click.echo(
                    format_error_envelope(
                        command=payload["command"],
                        root=payload.get("root"),
                        error_code=ErrorCode.PATH_ESCAPE,
                        message=f"Output path is considered unsafe: {output}",
                        details={"output_path": output},
                        include_timestamp="timestamp" in payload,
                        run_id=(
                            payload.get("run_id")
                            if isinstance(payload.get("run_id"), str)
                            else None
                        ),
                        correlation_id=(
                            payload.get("correlation_id")
                            if isinstance(payload.get("correlation_id"), str)
                            else None
                        ),
                    )
                )
            else:
                click.echo(
                    f"ERROR: Output path '{output}' is considered unsafe. Writing blocked.",
                    err=True,
                )
            raise SystemExit(exit_code_for_error(ErrorCode.PATH_ESCAPE))

        try:
            mode = "a" if append else "w"
            with out_path.open(mode, encoding="utf-8") as handle:
                if add_newline:
                    handle.write(output_str + "\n")
                else:
                    handle.write(output_str)
            return
        except OSError as exc:
            # Preserve machine-safe behavior for JSON output when file writes fail.
            payload = _extract_envelope_metadata(output_str)
            if payload is not None:
                click.echo(
                    format_error_envelope(
                        command=payload["command"],
                        root=payload.get("root"),
                        error_code=ErrorCode.UNKNOWN_ERROR,
                        message=f"Failed to write output file: {output}",
                        details={"output_path": output, "reason": str(exc)},
                        include_timestamp="timestamp" in payload,
                        run_id=(
                            payload.get("run_id")
                            if isinstance(payload.get("run_id"), str)
                            else None
                        ),
                        correlation_id=(
                            payload.get("correlation_id")
                            if isinstance(payload.get("correlation_id"), str)
                            else None
                        ),
                    )
                )
            else:
                # Fallback to click.echo
                click.echo(f"Error writing output file '{output}': {exc}", err=True)
            raise SystemExit(EX_CANTCREAT)
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
                # Avoid clobbering a file with empty content in nested capture flows.
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
    text = "" if value is None else str(value)
    return text.translate(_MD_INLINE_SPECIAL)


def _md_table(headers: list[str], rows: list[list[object]]) -> str:
    head = "| " + " | ".join(_md_escape(h) for h in headers) + " |"
    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(_md_escape(c) for c in row) + " |" for row in rows]
    return "\n".join([head, sep, *body])


# ---------------------------------------------------------------------------
# Warning and Severity Utilities
# ---------------------------------------------------------------------------

def _flatten_warning_groups(warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for item in warnings:
        path = item.get("path")
        for warning in item.get("warnings", []):
            entry: Dict[str, Any] = {
                "code": warning.get("code"),
                "path": path,
                "message": warning.get("message"),
            }
            if "line" in warning and warning.get("line") is not None:
                entry["line"] = warning.get("line")
            flat.append(entry)
    return flat


def get_severity_value(violation):
    return (
        violation.severity.value
        if hasattr(violation.severity, "value")
        else str(violation.severity)
    )


# ---------------------------------------------------------------------------
# State Rendering Functions
# ---------------------------------------------------------------------------

def _render_warnings_text(warnings, fmt, output):
    if not warnings:
        return
    if fmt == "md":
        lines = ["\n## Warnings\n"]
        for w in warnings:
            lines.append(
                f"- **{_md_inline(w.get('code', 'UNKNOWN'))}**: {_md_inline(w.get('message', ''))}"
            )
        lines.append("")
        _write_output("\n".join(lines), output)
        return
    for w in warnings:
        get_console().print(
            f"[yellow]Warning ({w.get('code', 'UNKNOWN')}): {w.get('message', '')}[/yellow]"
        )


def _render_state_set_json(
    result,
    root_path,
    include_timestamp,
    run_id,
    correlation_id,
    output,
):
    data: dict = {"action": result.action, "document_id": result.document_id}
    if result.entry:
        data.update(result.entry)
    _write_output(
        format_envelope(
            command="state set",
            root=str(root_path),
            success=True,
            data=data,
            warnings=result.warnings,
            include_timestamp=include_timestamp,
            run_id=run_id,
            correlation_id=correlation_id,
        ),
        output,
    )


def _render_state_set_text(result, format, output):
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


def _render_state_list_json(
    result, valid_impl_states, valid_doc_statuses, root_path, include_timestamp, run_id, correlation_id, output
):
    data = {"document_id": result.document_id, "entry": result.entry}
    if valid_impl_states:
        data["valid_impl_states"] = list(valid_impl_states)
    if valid_doc_statuses:
        data["valid_doc_statuses"] = list(valid_doc_statuses)
    data["summary"] = result.summary
    _write_output(
        format_envelope(
            command="state list",
            root=str(root_path),
            success=True,
            data=data,
            warnings=result.warnings,
            include_timestamp=include_timestamp,
            run_id=run_id,
            correlation_id=correlation_id,
        ),
        output,
    )


def _render_state_list_text(result, valid_impl_states, valid_doc_statuses, format, output):
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


def _render_state_next_json(
    result, root_path, include_timestamp, run_id, correlation_id, output
):
    entry = result.entry or {}
    _write_output(
        format_envelope(
            command=" state next",
            root=str(root_path),
            success=True,
            data={
                "document_id": result.document_id,
                "entry": entry,
                "selection": result.selection,
                "reason": result.reason,
            },
            warnings=result.warnings,
            include_timestamp=include_timestamp,
            run_id=run_id,
            correlation_id=correlation_id,
        ),
        output,
    )


def _render_state_next_text(result, fmt, output):
    if fmt == "md":
        lines = f"# Next Action for {result.document_id}\n\n"
        lines += f"- Next Action: {_md_inline(result.entry.get('next_action'))}\n"
        lines += f"- Assignee: {_md_inline(result.entry.get('assignee'))}\n"
        lines += f"- Priority: {_md_inline(result.entry.get('priority'))}\n"
        _write_output(lines, output)
        return

    with maybe_capture(output, fmt):
        get_console().print(f"[bold]Next Action for {result.document_id}[/bold]")
        get_console().print(f"  Next Action: {result.entry.get('next_action')}")
        get_console().print(f"  Assignee: {result.entry.get('assignee')}")
        get_console().print(f"  Priority: {result.entry.get('priority')}")
        _render_warnings_text(result.warnings, fmt, output)


def _render_state_blockers_json(
    result, root_path, include_timestamp, run_id, correlation_id, output
):
    _write_output(
        format_envelope(
            command="state blockers",
            root=str(root_path),
            success=True,
            data={
                "document_id": result.document_id,
                "blocked": result.blocked,
                "summary": result.summary,
            },
            warnings=result.warnings,
            include_timestamp=include_timestamp,
            run_id=run_id,
            correlation_id=correlation_id,
        ),
        output,
    )


def _render_state_blockers_text(result, fmt, output):
    if fmt == "md":
        lines = f"# Blockers for {result.document_id}\n\n"
        if result.blocked:
            lines += "## This Document Blocks\n\n"
            for blocker in result.blocked:
                lines += f"- {_md_inline(blocker)}\n"
        else:
            lines += "## This Document Blocks\n\nNone\n"
        if result.summary.get("blocked_by"):
            lines += "\n## This Document Is Blocked By\n\n"
            for blocked in result.summary.get("blocked_by", []):
                lines += f"- {_md_inline(blocked.get('doc_id'))}: {_md_inline(blocked.get('reason', ''))}\n"
        else:
            lines += "\n## This Document Is Blocked By\n\nNone\n"
        _write_output(lines, output)
        return

    with maybe_capture(output, fmt):
        get_console().print(f"[bold]Blockers for {result.document_id}[/bold]")
        get_console().print("\n[bold]This Document Blocks:[/bold]")
        if result.blocked:
            for blocker in result.blocked:
                get_console().print(f"  - {blocker}")
        else:
            get_console().print("  None")
        get_console().print("\n[bold]This Document Is Blocked By:[/bold]")
        if result.summary.get("blocked_by"):
            for blocked in result.summary.get("blocked_by", []):
                get_console().print(f"  - {blocked.get('doc_id')}: {blocked.get('reason', '')}")
        else:
            get_console().print("  None")
        _render_warnings_text(result.warnings, fmt, output)