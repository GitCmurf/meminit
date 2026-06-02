"""Check command implementation."""

from pathlib import Path

import click
from rich.table import Table

from meminit.core.services.exit_codes import EX_COMPLIANCE_FAIL
from meminit.core.services.observability import get_current_run_id, log_operation
from meminit.core.use_cases.check_repository import CheckRepositoryUseCase

from meminit.cli._helpers import (
    command_output_handler,
    get_console,
    maybe_capture,
    validate_initialized,
    validate_root_path,
)
from meminit.cli.shared.output_helpers import (
    _flatten_warning_groups,
    _md_table,
    _write_output,
)
from meminit.cli.shared_flags import agent_repo_options
from meminit.core.services.output_formatter import format_envelope


def register(cli: click.Group) -> None:
    """Register the check command with the CLI."""

    @cli.command()
    @click.argument("paths", nargs=-1, required=False)
    @agent_repo_options()
    @click.option("--quiet", is_flag=True, default=False, help="Only show failures (text output)")
    @click.option(
        "--strict",
        is_flag=True,
        default=False,
        help="Treat warnings as errors (e.g., outside docs_root)",
    )
    def check(paths, root, format, output, include_timestamp, correlation_id, quiet, strict):
        """Run compliance checks on the repository or specified PATHS.

        PATHS may be relative, absolute, or glob patterns. If omitted, all governed
        docs under the configured docs_root are checked.
        """
        run_id = get_current_run_id()
        root_path = Path(root).resolve()

        with command_output_handler(
            "check",
            format,
            output,
            include_timestamp,
            run_id,
            root_path,
            correlation_id=correlation_id,
        ):
            if format == "text" and not quiet and not paths:
                with maybe_capture(output, format):
                    get_console().print("[bold blue]Meminit Compliance Check[/bold blue]")

            validate_root_path(
                root_path,
                format=format,
                command="check",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )
            validate_initialized(
                root_path,
                format=format,
                command="check",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )

            use_case = CheckRepositoryUseCase(root_dir=str(root_path))

            if paths:
                with log_operation(
                    operation="check_targeted",
                    details={"paths": list(paths), "strict": strict},
                    run_id=run_id,
                ) as _check_ctx:
                    result = use_case.execute_targeted(list(paths), strict=strict)
                    _check_ctx["details"]["files_checked"] = result.files_checked
                    _check_ctx["details"]["files_failed"] = result.files_failed
                    _check_ctx["details"]["violations_count"] = result.violations_count
                    _check_ctx["details"]["warnings_count"] = result.warnings_count
            else:
                if format == "text" and not quiet:
                    with maybe_capture(output, format):
                        get_console().print(f"Scanning root: {root_path}")

                with log_operation(
                    operation="check_full",
                    details={"root": str(root_path)},
                    run_id=run_id,
                ) as _check_ctx:
                    result = use_case.execute_full_summary(strict=strict)
                    _check_ctx["details"]["files_checked"] = result.files_checked
                    _check_ctx["details"]["files_failed"] = result.files_failed
                    _check_ctx["details"]["violations_count"] = result.violations_count
                    _check_ctx["details"]["warnings_count"] = result.warnings_count

            if format == "json":
                checked_paths_sorted = sorted(result.checked_paths)
                check_counters = {
                    "checked_paths_count": len(checked_paths_sorted),
                    "checked_paths": checked_paths_sorted,
                    "files_checked": result.files_checked,
                    "files_failed": result.files_failed,
                    "files_outside_docs_root_count": result.files_outside_docs_root_count,
                    "files_passed": result.files_passed,
                    "files_with_warnings": result.files_with_warnings,
                    "missing_paths_count": result.missing_paths_count,
                    "schema_failures_count": result.schema_failures_count,
                    "violations_count": result.violations_count,
                    "warnings_count": result.warnings_count,
                }
                _write_output(
                    format_envelope(
                        command="check",
                        root=str(root_path),
                        success=result.success,
                        violations=result.violations,
                        warnings=_flatten_warning_groups(result.warnings),
                        extra_top_level=check_counters,
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
                raise SystemExit(0 if result.success else EX_COMPLIANCE_FAIL)

            if format == "md":
                status = "failed" if not result.success else "success"
                rows: list[list[object]] = []
                for item in result.violations:
                    path = item.get("path")
                    for v in item.get("violations", []):
                        rows.append(["error", v.get("code"), path, v.get("line"), v.get("message")])
                for item in result.warnings:
                    path = item.get("path")
                    for w in item.get("warnings", []):
                        rows.append(
                            [
                                "warning",
                                w.get("code"),
                                path,
                                w.get("line"),
                                w.get("message"),
                            ]
                        )

                title = "# Meminit Compliance Check"
                summary = (
                    f"- Status: {status}\n- Files checked: {result.files_checked}\n"
                    f"- Violations: {result.violations_count}\n- Warnings: {result.warnings_count}\n\n"
                )
                table = (
                    "## Findings\n\n"
                    + _md_table(["Severity", "Rule", "File", "Line", "Message"], rows)
                    + "\n"
                )
                _write_output(f"{title}\n\n{summary}{table}", output)
                raise SystemExit(0 if result.success else EX_COMPLIANCE_FAIL)

            with maybe_capture(output, format):
                violations_by_path = {item["path"]: item["violations"] for item in result.violations}
                warnings_by_path = {item["path"]: item["warnings"] for item in result.warnings}

                if quiet:
                    for path in sorted(violations_by_path.keys()):
                        for v in violations_by_path[path]:
                            line_info = f" (line {v['line']})" if v.get("line") is not None else ""
                            get_console().print(f"FAIL {path}: [{v['code']}] {v['message']}{line_info}")
                    raise SystemExit(0 if result.success else EX_COMPLIANCE_FAIL)

                if paths:
                    label = "file" if result.files_checked == 1 else "files"
                    get_console().print(f"Checking {result.files_checked} existing {label}...")
                    for path in result.checked_paths:
                        if path in violations_by_path:
                            get_console().print(f"FAIL {path}")
                            for v in violations_by_path[path]:
                                line_info = f" (line {v['line']})" if v.get("line") is not None else ""
                                get_console().print(f"  - [{v['code']}] {v['message']}{line_info}")
                            continue
                        if path in warnings_by_path:
                            get_console().print(f"WARN {path}")
                            for w in warnings_by_path[path]:
                                line_info = f" (line {w['line']})" if w.get("line") is not None else ""
                                get_console().print(f"  - [{w['code']}] {w['message']}{line_info}")
                            continue
                        get_console().print(f"OK {path}")
                else:
                    table_title = (
                        "Compliance Violations" if result.violations_count else "Compliance Warnings"
                    )
                    result_table = Table(title=table_title)
                    result_table.add_column("Severity")
                    result_table.add_column("Rule", style="cyan")
                    result_table.add_column("File")
                    result_table.add_column("Message", overflow="fold")

                    for item in result.violations:
                        for v in item.get("violations", []):
                            result_table.add_row(
                                "[red]error[/red]",
                                str(v.get("code")),
                                f"{item.get('path')}:{v.get('line', 0)}",
                                str(v.get("message")),
                            )
                    for item in result.warnings:
                        for w in item.get("warnings", []):
                            result_table.add_row(
                                "[yellow]warning[/yellow]",
                                str(w.get("code")),
                                f"{item.get('path')}:{w.get('line', 0)}",
                                str(w.get("message")),
                            )
                    get_console().print(result_table)

                if not result.success:
                    get_console().print(
                        f"\n[bold red]Found {result.violations_count} violations across {result.files_checked} checked files.[/bold red]"
                    )
                    raise SystemExit(EX_COMPLIANCE_FAIL)
                if result.warnings_count:
                    get_console().print(
                        f"\n[bold yellow]Found {result.warnings_count} warning(s).[/bold yellow]"
                    )
                else:
                    get_console().print("[bold green]Success! No violations found.[/bold green]")
                raise SystemExit(0)