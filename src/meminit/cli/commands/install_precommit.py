"""Install precommit command implementation."""

from pathlib import Path

import click

from meminit.cli._helpers import command_output_handler, get_console, validate_root_path
from meminit.cli.shared.output_helpers import _write_output, maybe_capture
from meminit.cli.shared_flags import agent_repo_options
from meminit.core.services.observability import get_current_run_id
from meminit.core.services.output_formatter import format_envelope
from meminit.core.use_cases.install_precommit import InstallPrecommitUseCase


def register(cli: click.Group) -> None:
    """Register the install-precommit command with the CLI."""

    @cli.command("install-precommit")
    @agent_repo_options()
    def install_precommit(root, format, output, include_timestamp, correlation_id):
        """Install a pre-commit hook to enforce meminit check."""
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

            use_case = InstallPrecommitUseCase(root_dir=str(root_path))
            result = use_case.execute()

            if format == "json":
                _write_output(
                    format_envelope(
                        command="install-precommit",
                        root=str(root_path),
                        success=True,
                        data={
                            "installed": result.status in ("created", "updated"),
                            "hook_path": str(result.config_path),
                            "already_present": result.status == "already_installed",
                        },
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
                return

            if format == "md":
                _write_output(
                    "# Meminit Install Precommit\n\n"
                    f"- Status: {'ok' if result.status in ('created', 'updated') else 'noop'}\n"
                    f"- Installed: `{result.status in ('created', 'updated')}`\n"
                    f"- Already present: `{result.status == 'already_installed'}`\n"
                    f"- Hook path: `{result.config_path}`\n",
                    output,
                )
                return

            with maybe_capture(output, format):
                if result.status == "already_installed":
                    get_console().print(
                        "[yellow]meminit pre-commit hook already installed.[/yellow]"
                    )
                    return
                if result.status == "created":
                    get_console().print(
                        f"[bold green]Created {result.config_path} with meminit hook.[/bold green]"
                    )
                    return
                get_console().print(
                    f"[bold green]Updated {result.config_path} with meminit hook.[/bold green]"
                )
