"""Doctor command implementation."""

from pathlib import Path

import click

from meminit.cli._helpers import (
    command_output_handler,
    get_console,
    maybe_capture,
    validate_root_path,
)
from meminit.cli.shared.output_helpers import _md_table, _write_output
from meminit.cli.shared_flags import agent_repo_options
from meminit.core.services.exit_codes import EX_COMPLIANCE_FAIL
from meminit.core.services.observability import get_current_run_id
from meminit.core.services.output_formatter import format_envelope
from meminit.core.use_cases.doctor_repository import DoctorRepositoryUseCase


def register(cli: click.Group) -> None:
    """Register the doctor command with the CLI."""

    @cli.command()
    @agent_repo_options()
    @click.option(
        "--strict/--no-strict",
        default=False,
        help="Treat warnings as errors (exit non-zero)",
    )
    def doctor(root, format, output, include_timestamp, correlation_id, strict):
        """Self-check: verify meminit can operate in this repository."""
        run_id = get_current_run_id()
        root_path = Path(root).resolve()

        with command_output_handler(
            "doctor",
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
                command="doctor",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )

            use_case = DoctorRepositoryUseCase(root_dir=str(root_path))
            issues = use_case.execute()

            errors = [
                i
                for i in issues
                if (i.severity.value if hasattr(i.severity, "value") else str(i.severity))
                == "error"
            ]
            warnings = [
                i
                for i in issues
                if (i.severity.value if hasattr(i.severity, "value") else str(i.severity))
                == "warning"
            ]

            status = "ok"
            if errors:
                status = "error"
            elif warnings:
                status = "warn"
            has_failure = bool(errors) or (strict and bool(warnings))
            exit_code = EX_COMPLIANCE_FAIL if has_failure else 0

            if format == "json":
                # PRD §15.1 Mapping Rule:
                promoted_warnings = warnings if strict else []
                unpromoted_warnings = [] if strict else warnings
                v2_warnings = [
                    {
                        "code": v.rule,
                        "message": v.message,
                        "path": v.file or "",
                        "line": v.line,
                        "severity": "warning",
                    }
                    for v in unpromoted_warnings
                ]
                v2_violations = [
                    {
                        "code": v.rule,
                        "message": v.message,
                        "path": v.file or "",
                        "line": v.line,
                        "severity": "error",
                    }
                    for v in errors
                ] + [
                    {
                        "code": v.rule,
                        "message": v.message,
                        "path": v.file or "",
                        "line": v.line,
                        "severity": "error",
                    }
                    for v in promoted_warnings
                ]
                # Include original issues in data for backward compatibility (PRD §15.1)
                issues_payload = [
                    {
                        "severity": (
                            i.severity.value if hasattr(i.severity, "value") else str(i.severity)
                        ),
                        "rule": i.rule,
                        "file": i.file,
                        "line": i.line,
                        "message": i.message,
                    }
                    for i in issues
                ]
                _write_output(
                    format_envelope(
                        command="doctor",
                        root=str(root_path),
                        success=not has_failure,
                        violations=v2_violations,
                        warnings=v2_warnings,
                        data={
                            "strict": strict,
                            "status": status,
                            "issues": issues_payload,
                            "issues_count": len(issues),
                            "errors_count": len(errors),
                            "warnings_count": len(warnings),
                        },
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
                raise SystemExit(exit_code)

            if format == "md":
                title = f"# Meminit Doctor\n\nStatus: {status}\n\n"
                if errors:
                    title += f"- Errors: {len(errors)}\n"
                if warnings:
                    title += f"- Warnings: {len(warnings)}\n"
                title += "\n"

                rows = []
                for issue in issues:
                    sev = (
                        issue.severity.value
                        if hasattr(issue.severity, "value")
                        else str(issue.severity)
                    )
                    rows.append(
                        [
                            sev,
                            issue.rule or "",
                            issue.file or "",
                            issue.line or "",
                            issue.message or "",
                        ]
                    )
                table = _md_table(["Severity", "Rule", "File", "Line", "Message"], rows)
                _write_output(f"{title}{table}\n", output)
                raise SystemExit(exit_code)

            with maybe_capture(output, format):
                get_console().print(f"Status: {status.upper()}")
                if errors:
                    get_console().print(f"\n[bold red]Errors ({len(errors)}):[/bold red]")
                    for issue in errors:
                        line_info = f" (line {issue.line})" if issue.line is not None else ""
                        get_console().print(
                            f"  [red]ERR[/red] [{issue.rule}] {issue.file or ''}{line_info}: {issue.message}"
                        )
                if warnings:
                    get_console().print(f"\n[bold yellow]Warnings ({len(warnings)}):[/bold yellow]")
                    for issue in warnings:
                        line_info = f" (line {issue.line})" if issue.line is not None else ""
                        get_console().print(
                            f"  [yellow]WARN[/yellow] [{issue.rule}] {issue.file or ''}{line_info}: {issue.message}"
                        )
            raise SystemExit(exit_code)
