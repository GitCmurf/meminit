"""Capabilities and explain commands implementation."""

import click

from meminit.cli._helpers import command_output_handler, get_console
from meminit.cli.shared.output_helpers import (
    _md_table,
    _write_output,
    exit_code_for_error,
    maybe_capture,
)
from meminit.cli.shared_flags import agent_output_options
from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.observability import get_current_run_id
from meminit.core.services.output_formatter import format_envelope
from meminit.core.use_cases.capabilities import CapabilitiesUseCase
from meminit.core.use_cases.explain_error import ExplainErrorUseCase


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
                        data=result,
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
            elif format == "md":
                markdown = "\n".join(
                    [
                        "# Meminit Capabilities",
                        "",
                        "## Commands",
                        "",
                        _md_table(
                            ["Command", "Description"],
                            [[c["name"], c.get("description", "")] for c in result["commands"]],
                        ),
                        "",
                        "## Error Codes",
                        "",
                        _md_table(["Code"], [[code] for code in result["error_codes"]]),
                        "",
                    ]
                )
                _write_output(markdown, output)
            else:
                with maybe_capture(output, format):
                    get_console().print("[bold blue]Capabilities:[/bold blue]")
                    rows = [[c["name"], c.get("description", "")] for c in result["commands"]]
                    get_console().print(_md_table(["Command", "Description"], rows))
                    get_console().print("\n[bold blue]Error Codes:[/bold blue]")
                    get_console().print(", ".join(result["error_codes"]))
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
                codes = use_case.list_codes()
                if format == "json":
                    _write_output(
                        format_envelope(
                            command="explain",
                            success=True,
                            data={"error_codes": codes},
                            include_timestamp=include_timestamp,
                            run_id=run_id,
                            correlation_id=correlation_id,
                        ),
                        output,
                    )
                elif format == "md":
                    markdown = "\n".join(
                        [
                            "# Meminit Explain",
                            "",
                            "## Error Codes",
                            "",
                            _md_table(
                                ["Code", "Category", "Summary"],
                                [[c["code"], c["category"], c["summary"]] for c in codes],
                            ),
                            "",
                        ]
                    )
                    _write_output(markdown, output)
                else:
                    with maybe_capture(output, format):
                        rows = [[c["code"], c["category"], c["summary"]] for c in codes]
                        get_console().print(_md_table(["Code", "Category", "Summary"], rows))
            elif error_code:
                explanation = use_case.explain(error_code)
                if explanation is None:
                    # Unknown code: emit an error envelope but place the requested
                    # code under `data` (contract: requested_code lives in data,
                    # not error.details).
                    if format == "json":
                        _write_output(
                            format_envelope(
                                command="explain",
                                success=False,
                                data={"requested_code": error_code},
                                error={
                                    "code": ErrorCode.UNKNOWN_ERROR_CODE.value,
                                    "message": f"Unknown error code: {error_code}",
                                },
                                include_timestamp=include_timestamp,
                                run_id=run_id,
                                correlation_id=correlation_id,
                            ),
                            output,
                        )
                    elif format == "md":
                        _write_output(
                            "\n".join(
                                [
                                    "# Meminit Explain",
                                    "",
                                    f"Unknown error code: {error_code}",
                                    "",
                                ]
                            ),
                            output,
                        )
                    else:
                        with maybe_capture(output, format):
                            get_console().print(
                                f"[bold red]Unknown error code: {error_code}[/bold red]"
                            )
                    raise SystemExit(exit_code_for_error(ErrorCode.UNKNOWN_ERROR_CODE))
                if format == "json":
                    _write_output(
                        format_envelope(
                            command="explain",
                            success=True,
                            data=explanation,
                            include_timestamp=include_timestamp,
                            run_id=run_id,
                            correlation_id=correlation_id,
                        ),
                        output,
                    )
                elif format == "md":
                    remediation = explanation.get("remediation", {})
                    relevant_commands = ", ".join(remediation.get("relevant_commands", [])) or "—"
                    markdown = "\n".join(
                        [
                            "# Meminit Explain",
                            "",
                            _md_table(
                                ["Field", "Value"],
                                [
                                    ["Code", explanation.get("code", "")],
                                    ["Category", explanation.get("category", "")],
                                    ["Summary", explanation.get("summary", "")],
                                    ["Cause", explanation.get("cause", "")],
                                    ["Remediation Action", remediation.get("action", "")],
                                    [
                                        "Resolution Type",
                                        remediation.get("resolution_type", ""),
                                    ],
                                    [
                                        "Automatable",
                                        "yes" if remediation.get("automatable") else "no",
                                    ],
                                    ["Relevant Commands", relevant_commands],
                                    ["Spec Reference", explanation.get("spec_reference", "")],
                                ],
                            ),
                            "",
                        ]
                    )
                    _write_output(markdown, output)
                else:
                    with maybe_capture(output, format):
                        get_console().print(f"{error_code}: {explanation.get('summary', '')}")
            else:
                raise MeminitError(
                    ErrorCode.INVALID_FLAG_COMBINATION,
                    "Provide an error code or use --list",
                )
