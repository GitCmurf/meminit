"""Shared Click option decorators for the Meminit agent interface.

Centralizes CLI flags that apply across multiple commands to avoid
duplication and ensure consistency (PRD-003 FR-4, FR-7).
"""

import functools

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
        return f

    return decorator
