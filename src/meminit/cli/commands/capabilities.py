"""Capabilities and explain commands implementation."""

from typing import Any

import click

from meminit.core.use_cases.capabilities import CapabilitiesUseCase
from meminit.core.use_cases.explain_error import ExplainErrorUseCase
from meminit.core.services.error_codes import ErrorCode, MeminitError

from meminit.cli._helpers import command_output_handler, get_console
from meminit.cli.shared.output_helpers import _md_table, _write_output
from meminit.cli.shared_flags import agent_output_options
from meminit.core.services.observability import get_current_run_id
from meminit.core.services.output_formatter import format_envelope
from meminit.cli.shared.output_helpers import exit_code_for_error


def register(cli: click.Group) -> None:
    """Register capabilities and explain commands with the CLI."""

    @cli.command()
    @agent_output_options()
    def capabilities(format, output, include_timestamp, correlation_id):
        """List available capabilities and error codes."""
        run_id = get_current_run_id()

        with command_output_handler(
            "capabilities",
            format,
            output,
            include_timestamp,
            run_id,
            correlation_id=correlation_id,
        ):
            use_case = CapabilitiesUseCase()
            result = use_case.execute()

            if format == "json":
                _write_output(
                    format_envelope(
                        command="capabilities",
                        success=True,
                        extra_top_level={"capabilities": result.capabilities, "error_codes": result.error_codes},
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
            else:
                get_console().print("[bold blue]Capabilities:[/bold blue]")
                rows = []
                for cap in result.capabilities:
                    rows.append([cap.name, cap.description])
                get_console().print(_md_table(["Capability", "Description"], rows))

                get_console().print("\n[bold blue]Error Codes:[/bold blue]")
                rows = []
                for code in result.error_codes:
                    rows.append([code.value, code.name])
                get_console().print(_md_table(["Code", "Name"], rows))
            raise SystemExit(0)

    @cli.command()
    @agent_output_options()
    @click.option("--list", is_flag=True, help="List all error codes")
    @click.argument("error_code", required=False)
    def explain(error_code, list, format, output, include_timestamp, correlation_id):
        """Explain an error code or code category."""
        run_id = get_current_run_id()

        with command_output_handler(
            "explain",
            format,
            output,
            include_timestamp,
            run_id,
            correlation_id=correlation_id,
        ):
            use_case = ExplainErrorUseCase()

            if list:
                result = CapabilitiesUseCase().list_all()
                if format == "json":
                    _write_output(
                        format_envelope(
                            command="explain",
                            success=True,
                            extra_top_level={"error_codes": result},
                            include_timestamp=include_timestamp,
                            run_id=run_id,
                            correlation_id=correlation_id,
                        ),
                        output,
                    )
                else:
                    rows = []
                    for code in result:
                        rows.append([code.value, code.name])
                    get_console().print(_md_table(["Code", "Name"], rows))
            elif error_code:
                result = use_case.explain_code(error_code)
                if format == "json":
                    _write_output(
                        format_envelope(
                            command="explain",
                            success=True,
                            extra_top_level={"code": error_code, "explanation": result},
                            include_timestamp=include_timestamp,
                            run_id=run_id,
                            correlation_id=correlation_id,
                        ),
                        output,
                    )
                else:
                    get_console().print(f"{error_code}: {result}")
            else:
                get_console().print("Error: Provide an error code or use --list")
                raise SystemExit(1)
