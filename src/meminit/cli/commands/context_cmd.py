"""Context command implementation."""

from pathlib import Path

import click

from meminit.cli._helpers import command_output_handler, get_console, validate_root_path
from meminit.cli.shared.output_helpers import _md_escape, _write_output, maybe_capture
from meminit.cli.shared_flags import agent_repo_options
from meminit.core.services.observability import get_current_run_id
from meminit.core.services.output_formatter import format_envelope
from meminit.core.use_cases.context_repository import ContextRepositoryUseCase


def register(cli: click.Group) -> None:
    """Register the context command with the CLI."""

    @cli.command()
    @click.option(
        "--deep",
        is_flag=True,
        help="Show detailed configuration and version information",
    )
    @agent_repo_options()
    def context(root, format, output, include_timestamp, correlation_id, deep):
        """Show repository context and configuration."""
        run_id = get_current_run_id()
        root_path = Path(root).resolve()

        with command_output_handler(
            "context",
            format,
            output,
            include_timestamp,
            run_id,
            root_path,
            correlation_id=correlation_id,
        ):
            validate_root_path(
                root_path,
                format=format,
                command="context",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )

            use_case = ContextRepositoryUseCase(root_dir=str(root_path))

            if format == "ndjson":
                from meminit.cli.streaming import (
                    CoreStreamingProducer,
                    streaming_output_handler,
                    unsupported_ndjson,
                )

                if not deep:
                    # Shallow context is a single config blob, not a stream; only
                    # deep mode emits per-document records over ndjson.
                    raise unsupported_ndjson(
                        "context",
                        "meminit context --format ndjson requires --deep.",
                    )
                streaming_output_handler(
                    command="context",
                    producer=CoreStreamingProducer(use_case.iter_stream(deep=True)),
                    output=output,
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    root_path=root_path,
                    correlation_id=correlation_id,
                )
                return

            result = use_case.execute(deep=deep)

            if format == "json":
                _write_output(
                    format_envelope(
                        command="context",
                        root=str(root_path),
                        success=True,
                        data=result.data,
                        warnings=result.warnings,
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
                return

            if format == "md":
                lines = [
                    "# Meminit Context\n",
                    f"- Root: `{root_path}`",
                    f"- Project: `{result.data.get('project_name', 'N/A')}`",
                    f"- Config: `{result.data.get('config_path', 'N/A')}`",
                    "",
                ]
                if result.warnings:
                    lines.append("## Warnings\n")
                    for warning in result.warnings:
                        code = warning.get("code", "WARNING")
                        message = _md_escape(warning.get("message", ""))
                        lines.append(f"- [{code}] {message}")
                    lines.append("")
                _write_output("\n".join(lines), output)
                return

            with maybe_capture(output, format):
                get_console().print("[bold blue]Meminit Context[/bold blue]")
                get_console().print(f"Root: {root_path}")
                get_console().print(f"Project: {result.data.get('project_name', 'N/A')}")
                if result.warnings:
                    get_console().print("Warnings:")
                    for warning in result.warnings:
                        get_console().print(f"  - {warning.get('code')}: {warning.get('message')}")
