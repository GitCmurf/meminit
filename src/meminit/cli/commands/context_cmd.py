"""Context command implementation."""

from pathlib import Path

import click

from meminit.core.use_cases.context_repository import ContextRepositoryUseCase

from meminit.cli._helpers import command_output_handler, validate_root_path
from meminit.cli.shared.output_helpers import _write_output
from meminit.cli.shared_flags import agent_repo_options
from meminit.core.services.observability import get_current_run_id
from meminit.core.services.output_formatter import format_envelope


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
            result = use_case.execute(deep=deep)

            if format == "json":
                _write_output(
                    format_envelope(
                        command="context",
                        root=str(root_path),
                        success=True,
                        extra_top_level=result.to_dict(),
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
            else:
                for key, value in result.to_dict().items():
                    if deep or key in ["docs_root", "repo_prefix", "namespaces"]:
                        get_console().print(f"{key}: {value}")
