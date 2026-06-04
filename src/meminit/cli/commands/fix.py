"""Fix command implementation."""

import json
from pathlib import Path

import click
from rich.table import Table

from meminit.cli._helpers import command_output_handler, get_console, validate_root_path
from meminit.cli.shared.output_helpers import _write_output, maybe_capture
from meminit.cli.shared_flags import agent_repo_options
from meminit.core.services.error_codes import ErrorCode
from meminit.core.services.exit_codes import EX_COMPLIANCE_FAIL
from meminit.core.services.observability import get_current_run_id
from meminit.core.services.output_formatter import format_envelope, format_error_envelope
from meminit.core.services.scan_plan import MigrationPlan
from meminit.core.use_cases.fix_repository import FixRepositoryUseCase


def register(cli: click.Group) -> None:
    """Register the fix command with the CLI."""

    @cli.command()
    @agent_repo_options()
    @click.option(
        "--plan",
        type=click.Path(exists=True, dir_okay=False),
        default=None,
        help="Apply a deterministic migration plan (JSON)",
    )
    @click.option(
        "--dry-run/--no-dry-run",
        default=True,
        help="Simulate fixes without changing files",
    )
    @click.option(
        "--namespace",
        default=None,
        help="Limit fixes to a single namespace (monorepo safety)",
    )
    def fix(root, plan, dry_run, namespace, format, output, include_timestamp, correlation_id):
        """Automatically fix common compliance violations."""
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
            if format == "text":
                with maybe_capture(output, format):
                    msg = "[bold blue]Meminit Compliance Fixer[/bold blue]"
                    if dry_run:
                        msg += " [yellow](DRY RUN)[/yellow]"
                    if plan:
                        msg += f" [cyan](Using Plan: {plan})[/cyan]"
                    get_console().print(msg)

            validate_root_path(
                root_path,
                format=format,
                command="fix",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )

            plan_obj = None
            if plan:
                try:
                    with open(plan, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    # Handle both an envelope ({"data": {"plan": ...}}) and a direct plan.
                    plan_data = data.get("data", {}).get("plan") or data
                    plan_obj = MigrationPlan.from_dict(plan_data)
                except Exception as e:
                    if format == "json":
                        _write_output(
                            format_error_envelope(
                                command="fix",
                                root=str(root_path),
                                error_code=ErrorCode.VALIDATION_ERROR,
                                message=f"Failed to load plan: {e}",
                                run_id=run_id,
                                include_timestamp=include_timestamp,
                                correlation_id=correlation_id,
                            ),
                            output,
                        )
                    else:
                        get_console().print(f"[bold red]Failed to load plan: {e}[/bold red]")
                    raise SystemExit(1) from e

            use_case = FixRepositoryUseCase(root_dir=str(root_path))
            report = use_case.execute(dry_run=dry_run, namespace=namespace, plan=plan_obj)
            has_remaining = bool(report.remaining_violations)
            exit_code = EX_COMPLIANCE_FAIL if has_remaining else 0

            if format == "json":
                _write_output(
                    format_envelope(
                        command="fix",
                        root=str(root_path),
                        success=not has_remaining,
                        data={
                            "fixed": len(report.fixed_violations),
                            "remaining": len(report.remaining_violations),
                            "dry_run": dry_run,
                        },
                        violations=[
                            {
                                "code": violation.rule,
                                "message": violation.message,
                                "path": violation.file,
                                "line": violation.line,
                                "severity": (
                                    violation.severity.value
                                    if hasattr(violation.severity, "value")
                                    else str(violation.severity)
                                ),
                            }
                            for violation in report.remaining_violations
                        ],
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
                raise SystemExit(exit_code)

            if format == "md":
                _write_output(
                    "# Meminit Fix\n\n"
                    f"- Mode: {'DRY RUN' if dry_run else 'APPLY'}\n"
                    f"- Fixed: {len(report.fixed_violations)}\n"
                    f"- Remaining: {len(report.remaining_violations)}\n",
                    output,
                )
                raise SystemExit(exit_code)

            with maybe_capture(output, format):
                if report.fixed_violations:
                    table = Table(title="Actions Taken" if not dry_run else "Proposed Actions")
                    table.add_column("File")
                    table.add_column("Action", style="green")
                    table.add_column("Description")

                    for action in report.fixed_violations:
                        table.add_row(action.file, action.action, action.description)

                    get_console().print(table)
                    get_console().print(
                        f"\n[bold green]Applied {len(report.fixed_violations)} fixes.[/bold green]"
                    )
                else:
                    get_console().print(
                        "[yellow]No auto-fixes available for current violations.[/yellow]"
                    )

                if report.remaining_violations:
                    get_console().print(
                        f"\n[bold red]Remaining Violations "
                        f"({len(report.remaining_violations)}):[/bold red]"
                    )
                    for v in report.remaining_violations[:5]:
                        get_console().print(f"- {v.file}: {v.message}")
                    if len(report.remaining_violations) > 5:
                        get_console().print(f"... and {len(report.remaining_violations) - 5} more.")
                    get_console().print("\nRun [bold]meminit check[/bold] for full details.")
                else:
                    get_console().print("\n[bold green]All clear![/bold green]")

            raise SystemExit(exit_code)
