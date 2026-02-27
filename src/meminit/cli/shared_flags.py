"""Shared Click option decorators for the Meminit agent interface.

Centralizes CLI flags that apply across multiple commands to avoid
duplication and ensure consistency (PRD-003 FR-4, FR-7).
"""

import functools
import os

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


def with_log_silence():
    """Silence log events for JSON output unless verbose/debug is enabled."""

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            previous = os.environ.get("MEMINIT_LOG_SILENT")
            format_value = kwargs.get("format")
            verbose_value = kwargs.get("verbose", False)
            output_value = kwargs.get("output")
            silence_logs = False
            if os.environ.get("MEMINIT_DEBUG") != "1" and not verbose_value:
                if format_value == "json" or output_value:
                    silence_logs = True
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

    Applies: --format, --output, --include-timestamp.

    Usage::

        @cli.command()
        @agent_output_options()
        def my_command(format, output, include_timestamp, ...):
            ...
    """

    def decorator(f):
        f = format_option()(f)
        f = output_option()(f)
        f = include_timestamp_option()(f)
        f = with_log_silence()(f)
        return f

    return decorator


def agent_repo_options():
    """Composite decorator applying repo-root + agent interface output flags.

    Applies: --root, --format, --output, --include-timestamp.
    """

    def decorator(f):
        f = agent_output_options()(f)
        f = root_option()(f)
        return f

    return decorator
