"""Install precommit command implementation."""

from pathlib import Path

import click

from meminit.core.use_cases.install_precommit import InstallPrecommitUseCase

from meminit.cli._helpers import command_output_handler, validate_initialized, validate_root_path
from meminit.cli.shared.output_helpers import _write_output
from meminit.cli.shared_flags import agent_repo_options
from meminit.core.services.observability import get_current_run_id
from meminit.core.services.output_formatter import format_envelope


def register(cli: click.Group) -> None:
    """Register the install-precommit command with the CLI."""

    @cli.command("install-precommit")
    @agent_repo_options()
    def install_precommit(root, format, output, include_timestamp, correlation_id):
        """Install pre-commit hook for Meminit compliance."""
        run_id = get_current_run_id()
        root_path = Path(root).resolve()

        with command_output_handler(
            "install-precommit",
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
                command="install-precommit",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )
            validate_initialized(
                root_path,
                format=format,
                command="install-precommit",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )

            use_case = InstallPrecommitUseCase(root_dir=str(root_path))
            result = use_case.execute()

            if format == "json":
                _write_output(
                    format_envelope(
                        command="install-precommit",
                        root=str(root_path),
                        success=result.installed,
                        extra_top_level={
                            "hook_file": result.hook_file,
                            "hook_installed": result.installed,
                        },
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
            else:
                if result.installed:
                    get_console().print(f"[bold green]Pre-commit hook installed at:[/bold green] {result.hook_file}")
                else:
                    get_console().print(f"[yellow]Pre-commit hook already exists at:[/yellow] {result.hook_file}")
            raise SystemExit(0)
