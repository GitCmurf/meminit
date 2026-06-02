"""Init command implementation."""

from pathlib import Path

import click

from meminit.core.use_cases.init_repository import InitRepositoryUseCase

from meminit.cli._helpers import command_output_handler, get_console, validate_root_path
from meminit.cli.shared.output_helpers import _write_output
from meminit.cli.shared_flags import agent_repo_options
from meminit.core.services.observability import get_current_run_id
from meminit.core.services.output_formatter import format_envelope


def register(cli: click.Group) -> None:
    """Register the init command with the CLI."""

    @cli.command()
    @click.option("--repo-prefix", help="Repository prefix for document IDs")
    @agent_repo_options()
    def init(root, format, output, include_timestamp, correlation_id, repo_prefix):
        """Initialize a Meminit DocOps repository."""
        run_id = get_current_run_id()
        root_path = Path(root).resolve()

        with command_output_handler(
            "init",
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
                command="init",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )

            use_case = InitRepositoryUseCase(root_dir=str(root_path))
            result = use_case.execute(repo_prefix=repo_prefix)

            if format == "json":
                _write_output(
                    format_envelope(
                        command="init",
                        root=str(root_path),
                        success=True,
                        extra_top_level={
                            "created_paths": result.created_paths,
                            "skipped_paths": result.skipped_paths,
                        },
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
            else:
                if result.created_paths:
                    get_console().print("[bold green]Created:[/bold green]")
                    for path in result.created_paths:
                        get_console().print(f"  [green]✔[/green] {path}")
                if result.skipped_paths:
                    get_console().print("[bold yellow]Skipped:[/bold yellow]")
                    for path in result.skipped_paths:
                        get_console().print(f"  [yellow]⊘[/yellow] {path}")
                get_console().print("[bold green]Meminit initialized successfully![/bold green]")
