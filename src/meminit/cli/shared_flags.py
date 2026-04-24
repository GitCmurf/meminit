"""Shared Click option decorators for the Meminit agent interface.

Centralizes CLI flags that apply across multiple commands to avoid
duplication and ensure consistency (PRD-003 FR-4, FR-7).
"""

import functools
import os
from typing import Any, Dict

import click


def format_option():
    """Add --format option (text|json|md)."""

    def decorator(f):
        return click.option(
            "--format",
            "format",
            type=click.Choice(["text", "json", "md"], case_sensitive=False),
            default="text",
            help="Output format (text|json|md).",
        )(f)

    return decorator


def root_option():
    """Add --root option for repository root directory."""

    def decorator(f):
        return click.option(
            "--root",
            default=".",
            help="Root directory of the repository",
        )(f)

    return decorator


def output_option():
    """Add --output option to write JSON/md output to a file."""

    def decorator(f):
        return click.option(
            "--output",
            type=click.Path(),
            default=None,
            help="Write output to this file path instead of stdout.",
        )(f)

    return decorator


def include_timestamp_option():
    """Add --include-timestamp flag (Decision 20.3)."""

    def decorator(f):
        return click.option(
            "--include-timestamp",
            is_flag=True,
            default=False,
            help="Include ISO 8601 UTC timestamp in JSON output.",
        )(f)

    return decorator


def correlation_id_option():
    """Add --correlation-id option with MEMINIT_CORRELATION_ID env var fallback.

    CLI flag takes precedence. The env var is only used when the flag is absent.
    Validation is deferred to command_output_handler so that JSON mode can
    emit a structured error envelope instead of a raw Click usage error.
    """

    def decorator(f):
        def _resolve_correlation_id(ctx, param, value):
            if value is None:
                env_val = os.environ.get("MEMINIT_CORRELATION_ID", "").strip()
                if env_val:
                    value = env_val
            return value

        return click.option(
            "--correlation-id",
            "correlation_id",
            default=None,
            callback=_resolve_correlation_id,
            help="Cross-system correlation identifier (max 128 chars, no whitespace).",
        )(f)

    return decorator


def with_log_silence():
    """Silence log events for machine-consumed outputs unless verbose is enabled."""

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            previous = os.environ.get("MEMINIT_LOG_SILENT")
            format_value = kwargs.get("format")

            verbose_value = False
            ctx = click.get_current_context(silent=True)
            if ctx and ctx.parent:
                verbose_value = ctx.parent.params.get("verbose", False)

            output_value = kwargs.get("output")
            silence_logs = (
                not verbose_value and (format_value == "json" or bool(output_value))
            )
            changed = False
            if silence_logs and previous != "1":
                os.environ["MEMINIT_LOG_SILENT"] = "1"
                changed = True
            try:
                return f(*args, **kwargs)
            finally:
                if changed:
                    if previous is None:
                        os.environ.pop("MEMINIT_LOG_SILENT", None)
                    else:
                        os.environ["MEMINIT_LOG_SILENT"] = previous

        return wrapper

    return decorator


def agent_output_options():
    """Composite decorator applying all agent interface output flags.

    Applies: --format, --output, --include-timestamp, --correlation-id.

    Usage::

        @cli.command()
        @agent_output_options()
        def my_command(format, output, include_timestamp, correlation_id, ...):
            ...
    """

    def decorator(f):
        f = format_option()(f)
        f = output_option()(f)
        f = include_timestamp_option()(f)
        f = correlation_id_option()(f)
        f = with_log_silence()(f)
        return f

    return decorator


def agent_repo_options():
    """Composite decorator applying repo-root + agent interface output flags.

    Applies: --root, --format, --output, --include-timestamp, --correlation-id.
    """

    def decorator(f):
        f = agent_output_options()(f)
        f = root_option()(f)
        return f

    return decorator


# ---------------------------------------------------------------------------
# Capabilities registry for the 'meminit capabilities' command.
# ---------------------------------------------------------------------------

_CAPABILITIES_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_capability(
    name: str,
    description: str,
    *,
    supports_json: bool = True,
    supports_correlation_id: bool = True,
    needs_root: bool = False,
    agent_facing: bool,
) -> None:
    """Register a command's capability descriptor."""
    _CAPABILITIES_REGISTRY[name] = {
        "name": name,
        "description": description,
        "supports_json": supports_json,
        "supports_correlation_id": supports_correlation_id,
        "needs_root": needs_root,
        "agent_facing": agent_facing,
    }


# Register all known commands. Each entry must correspond to a Click command
# in main.py. The contract test enforces this invariant.
register_capability("check", "Run compliance checks on the repository", needs_root=True, agent_facing=True)
register_capability("doctor", "Diagnose common configuration issues", needs_root=True, agent_facing=True)
register_capability("fix", "Auto-fix detected violations", needs_root=True, agent_facing=True)
register_capability("scan", "Suggest a DocOps migration plan", needs_root=True, agent_facing=True)
register_capability("install-precommit", "Install a pre-commit hook", needs_root=True, agent_facing=False)
register_capability("index", "Build the document index", needs_root=True, agent_facing=True)
register_capability("resolve", "Resolve a document_id to a file path", needs_root=True, agent_facing=True)
register_capability("identify", "Identify a document's metadata", needs_root=True, agent_facing=True)
register_capability("link", "Print a Markdown link for a document_id", needs_root=True, agent_facing=True)
register_capability("migrate-ids", "Migrate legacy document_id values", needs_root=True, agent_facing=True)
register_capability("migrate-templates", "Migrate legacy template configs", needs_root=True, agent_facing=True)
register_capability("init", "Initialize a new DocOps repository", needs_root=True, agent_facing=True)
register_capability("new", "Create a new document", needs_root=True, agent_facing=True)
register_capability("adr new", "Create a new ADR", needs_root=True, agent_facing=True)
register_capability("context", "Show repository DocOps context", needs_root=True, agent_facing=True)
register_capability("org install", "Install org profile to XDG paths", agent_facing=False)
register_capability("org vendor", "Vendor org profile into repo", needs_root=True, agent_facing=False)
register_capability("org status", "Show org profile status", needs_root=True, agent_facing=False)
register_capability("state set", "Set document implementation state", needs_root=True, agent_facing=True)
register_capability("state get", "Get document implementation state", needs_root=True, agent_facing=True)
register_capability("state list", "List all document states", needs_root=True, agent_facing=True)
register_capability("state next", "Select the next ready work item", needs_root=True, agent_facing=True)
register_capability("state blockers", "List blocked work items and open blockers", needs_root=True, agent_facing=True)
register_capability("capabilities", "Show CLI capabilities descriptor", agent_facing=True)
register_capability("explain", "Explain a Meminit error code", agent_facing=True)
register_capability("protocol check", "Check protocol assets for drift", needs_root=True, agent_facing=True)
register_capability("protocol sync", "Synchronize protocol assets with canonical contract", needs_root=True, agent_facing=True)
