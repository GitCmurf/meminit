"""Fix command implementation."""

import json
from pathlib import Path
from typing import Any

import click

from meminit.core.use_cases.fix_repository import FixRepositoryUseCase

from meminit.cli._helpers import command_output_handler, get_console, validate_initialized, validate_root_path
from meminit.cli.shared.output_helpers import _write_output
from meminit.cli.shared_flags import agent_repo_options
from meminit.core.services.observability import get_current_run_id, log_operation
from meminit.core.services.output_formatter import format_envelope
from meminit.core.services.scan_plan import MigrationPlan


def register(cli: click.Group) -> None:
    """Register the fix command with the CLI."""

    @cli.command()
    @click.option(
        "--plan",
        type=click.Path(exists=True),
        help="Path to migration plan file (JSON or YAML)",
    )
    @click.option(
        "--dry-run/--no-dry-run",
        default=False,
        help="Show what would be fixed without making changes",
    )
    @click.option(
        "--namespace",
        help="Namespace to fix (default: default namespace)",
    )
    @agent_repo_options()
    def fix(root, format, output, include_timestamp, correlation_id, plan, dry_run, namespace):
        """Apply fixes from a migration plan."""
        run_id = get_current_run_id()
        root_path = Path(root).resolve()

        with command_output_handler(
            "fix",
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
                command="fix",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )
            validate_initialized(
                root_path,
                format=format,
                command="fix",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )

            with log_operation(
                operation="fix_plan",
                details={
                    "plan": plan if plan else "interactive",
                    "dry_run": dry_run,
                    "namespace": namespace,
                },
                run_id=run_id,
            ) as _fix_ctx:
                use_case = FixRepositoryUseCase(root_dir=str(root_path))

                if plan:
                    with open(plan, "r", encoding="utf-8") as f:
                        plan_obj = None
                        try:
                            data = json.load(f)
                            plan_data = data.get("data", {}).get("plan") or data
                            plan_obj = MigrationPlan.from_dict(plan_data)
                        except Exception as e:
                            _fix_ctx["details"]["plan_parse_error"] = str(e)
                            _fix_ctx["details"]["plan_parse_success"] = False
                            raise
                        _fix_ctx["details"]["plan_parse_success"] = True

                    if not isinstance(plan_obj, MigrationPlan):
                        _fix_ctx["details"]["plan_invalid_type"] = type(plan_obj).__name__
                        raise ValueError(f"Invalid plan format: {type(plan_obj)}")

                    report = use_case.execute_from_plan(
                        plan_obj, dry_run=dry_run, namespace=namespace
                    )
                else:
                    report = use_case.execute_full(
                        dry_run=dry_run, namespace=namespace
                    )

                _fix_ctx["details"][
                    "files_checked"
                ] = report.files_checked  # type: ignore
                _fix_ctx["details"][
                    "files_fixed"
                ] = len(report.fixed_violations)  # type: ignore
                _fix_ctx["details"][
                    "files_skipped"
                ] = len(report.skipped_violations)  # type: ignore
                _fix_ctx["details"][
                    "failures"
                ] = len(report.failures)  # type: ignore

            if format == "json":
                fixed_data = []
                for fv in report.fixed_violations:  # type: ignore
                    fixed_data.append(
                        {
                            "path": fv.file,
                            "action": fv.action,
                            "code": fv.code,
                            "message": fv.message,
                        }
                    )
                skipped_data = []
                for sv in report.skipped_violations:  # type: ignore
                    skipped_data.append(
                        {
                            "path": sv.file,
                            "code": sv.code,
                            "message": sv.message,
                        }
                    )
                failure_data = []
                for f in report.failures:  # type: ignore
                    failure_data.append(
                        {
                            "path": f.file,
                            "code": f.code,
                            "message": f.message,
                        }
                    )
                _write_output(
                    format_envelope(
                        command="fix",
                        root=str(root_path),
                        success=not report.failures,
                        violations=failure_data,
                        extra_top_level={
                            "files_fixed": len(report.fixed_violations),  # type: ignore
                            "files_skipped": len(report.skipped_violations),  # type: ignore
                            "files_failed": len(report.failures),  # type: ignore
                            "fixed_violations": fixed_data,
                            "skipped_violations": skipped_data,
                            "failures": failure_data,
                        },
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )

            else:
                if report.fixed_violations:  # type: ignore
                    get_console().print(
                        f"[bold green]Fixed {len(report.fixed_violations)} violations:[/bold green]"
                    )  # type: ignore
                    for fv in report.fixed_violations:  # type: ignore
                        line_info = f" (line {fv.line})" if fv.line else ""  # type: ignore
                        get_console().print(
                            f"  [green]✔[/green] [{fv.code}] {fv.file}{line_info}: {fv.action}"
                        )  # type: ignore

                if report.skipped_violations:  # type: ignore
                    get_console().print(
                        f"[bold yellow]Skipped {len(report.skipped_violations)} violations:[/bold yellow]"
                    )  # type: ignore
                    for sv in report.skipped_violations:  # type: ignore
                        line_info = f" (line {sv.line})" if sv.line else ""  # type: ignore
                        get_console().print(
                            f"  [yellow]⊘[/yellow] [{sv.code}] {sv.file}{line_info}: {sv.message}"
                        )  # type: ignore

                if report.failures:  # type: ignore
                    get_console().print(
                        f"[bold red]Failed {len(report.failures)} violations:[/bold red]"
                    )  # type: ignore
                    for f in report.failures:  # type: ignore
                        line_info = f" (line {f.line})" if f.line else ""  # type: ignore
                        get_console().print(
                            f"  [red]✗[/red] [{f.code}] {f.file}{line_info}: {f.message}"
                        )  # type: ignore

                if not report.fixed_violations and not report.failures:  # type: ignore
                    get_console().print("[green]No violations found or needed fixing.[/green]")

            raise SystemExit(1 if report.failures else 0)  # type: ignore