"""Init command implementation."""

from pathlib import Path

import click

from meminit.cli._helpers import command_output_handler, get_console, validate_root_path
from meminit.cli.shared.output_helpers import _write_output, maybe_capture
from meminit.cli.shared_flags import agent_repo_options
from meminit.core.services.observability import get_current_run_id
from meminit.core.services.output_formatter import format_envelope
from meminit.core.use_cases.init_repository import InitRepositoryUseCase


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
            # `meminit init` may target a directory that does not exist yet; create
            # it (the use case writes the full tree underneath). Validate afterwards
            # so an existing non-directory at the path is still rejected cleanly.
            if not root_path.exists():
                root_path.mkdir(parents=True, exist_ok=True)
            validate_root_path(
                root_path,
                format=format,
                command="init",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )

            use_case = InitRepositoryUseCase(root_dir=str(root_path), repo_prefix=repo_prefix)
            result = use_case.execute()

            if format == "json":
                _write_output(
                    format_envelope(
                        command="init",
                        root=str(root_path),
                        success=True,
                        data={
                            "created_paths": result.created_paths,
                            "skipped_paths": result.skipped_paths,
                        },
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
                return

            if format == "md":
                created = result.created_paths
                skipped = result.skipped_paths
                lines = [
                    "# Meminit Init",
                    "",
                    "- Status: ok",
                    f"- Created: {len(created)}",
                    f"- Skipped: {len(skipped)}",
                    "",
                ]
                if created:
                    lines.append("## Created Paths\n")
                    lines.extend([f"- `{p}`" for p in created])
                    lines.append("")
                if skipped:
                    lines.append("## Skipped Paths\n")
                    lines.extend([f"- `{p}`" for p in skipped])
                    lines.append("")
                _write_output("\n".join(lines), output)
                return

            with maybe_capture(output, format):
                get_console().print(
                    f"[bold green]Initialized DocOps repository at {root}[/bold green]"
                )
                get_console().print("- Created directory structure (docs/)")
                get_console().print("- Created docops.config.yaml")
                get_console().print("- Created AGENTS.md")
