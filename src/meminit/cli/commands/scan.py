"""Scan command implementation."""

import json
from pathlib import Path
from typing import Any

import click

from meminit.core.use_cases.scan_repository import ScanRepositoryUseCase
from meminit.core.services.scan_plan import MigrationPlan
from meminit.core.services.observability import get_current_run_id, log_operation

from meminit.cli._helpers import (
    command_output_handler,
    get_console,
    validate_root_path,
)
from meminit.cli.shared.output_helpers import (
    _md_table,
    _write_output,
)
from meminit.cli.shared_flags import agent_repo_options
from meminit.core.services.output_formatter import format_envelope


def _write_scan_plan_artifact(
    *,
    plan: str,
    root_path: Path,
    migration_plan: MigrationPlan,
    format: str,
    output: Any,
    include_timestamp: bool,
    run_id: str,
    correlation_id: str | None,
    empty: bool = False,
) -> None:
    """Write the scan plan artifact."""
    plan_path = Path(plan).resolve()
    plan_data = migration_plan.to_dict()

    # Preserve envelope structure for downstream parsing
    envelope_data = {
        "command": "scan",
        "root": str(root_path),
        "success": True,
        "data": {"plan": plan_data},
        "warnings": [],
        "violations": [],
    }
    if include_timestamp:
        envelope_data["run_id"] = run_id
    if correlation_id:
        envelope_data["correlation_id"] = correlation_id

    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(envelope_data, indent=2), encoding="utf-8")

    if format != "json":
        if empty:
            get_console().print(f"[yellow]Wrote empty plan to {plan_path}[/yellow]")
        else:
            get_console().print(f"[bold green]Wrote plan to {plan_path}[/bold green]")


def register(cli: click.Group) -> None:
    """Register the scan command with the CLI."""

    @cli.command()
    @agent_repo_options()
    @click.option(
        "--plan",
        type=click.Path(dir_okay=False, writable=True),
        default=None,
        help="Output deterministic migration plan to file",
    )
    def scan(root, plan, format, output, include_timestamp, correlation_id):
        """Scan a repository and suggest a DocOps migration plan (read-only)."""
        run_id = get_current_run_id()
        root_path = Path(root).resolve()

        with command_output_handler(
            "scan",
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
                command="scan",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )
            if format == "ndjson" and plan:
                raise click.ClickException(
                    "meminit scan --format ndjson does not support --plan; "
                    "run scan --format json --plan for plan artifacts."
                )

            use_case = ScanRepositoryUseCase(root_dir=str(root_path))

            if format == "ndjson":
                from meminit.core.services.stream_events import (
                    CoreStreamingProducer,
                    streaming_output_handler,
                )

                streaming_output_handler(
                    command="scan",
                    producer=CoreStreamingProducer(use_case.iter_stream()),
                    output=output,
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    root_path=root_path,
                    correlation_id=correlation_id,
                )
                return

            report = use_case.execute(generate_plan=bool(plan))
            scan_data = report.as_dict()

            if plan and report.plan:
                _write_scan_plan_artifact(
                    plan=plan,
                    root_path=root_path,
                    migration_plan=report.plan,
                    format=format,
                    output=output,
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                )
            elif plan:
                if format != "json":
                    get_console().print(
                        "[yellow]No plan actions generated — repository may already be compliant.[/yellow]"
                    )
                _write_scan_plan_artifact(
                    plan=plan,
                    root_path=root_path,
                    migration_plan=MigrationPlan(
                        plan_version="1.0",
                        generated_at="1970-01-01T00:00:00Z",
                        config_fingerprint="",
                        actions=[],
                    ),
                    format=format,
                    output=output,
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                    empty=True,
                )

            if format == "json":
                _write_output(
                    format_envelope(
                        command="scan",
                        root=str(root_path),
                        success=True,
                        data={"report": scan_data},
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
                return

            if format == "md":
                lines = [
                    "# Meminit Scan\n",
                    f"- Root: `{root_path}`",
                    f"- Docs root: `{report.docs_root or 'Not found'}`",
                    f"- Markdown files: {report.markdown_count}",
                    f"- Governed markdown (all namespaces): {getattr(report, 'governed_markdown_count', 0)}",
                    "",
                ]
                configured = getattr(report, "configured_namespaces", None)
                if configured:
                    rows = [
                        [
                            ns.get("namespace"),
                            ns.get("docs_root"),
                            ns.get("repo_prefix"),
                            ns.get("docs_root_exists"),
                            ns.get("governed_markdown_count"),
                        ]
                        for ns in configured
                        if isinstance(ns, dict)
                    ]
                    lines.extend(
                        [
                            "## Configured Namespaces",
                            "",
                            _md_table(
                                [
                                    "Namespace",
                                    "Docs Root",
                                    "Repo Prefix",
                                    "Exists",
                                    "Governed MD",
                                ],
                                rows,
                            ),
                            "",
                        ]
                    )
                _write_output("\n".join(lines), output)
                return

            with output if output else open(os.devnull, "w") as out:
                get_console().print(f"[bold blue]Scanning {root_path}[/bold blue]")
                get_console().print(f"Docs root: {report.docs_root or 'Not found'}")
                get_console().print(f"Markdown files: {report.markdown_count}")

                if report.warnings:
                    get_console().print("\n[yellow]Warnings:[/yellow]")
                    for warning in report.warnings:
                        get_console().print(f"  - {warning}")

                if report.suggestions:
                    get_console().print("\n[bold green]Suggestions:[/bold green]")
                    for suggestion in report.suggestions:
                        get_console().print(f"  - {suggestion}")
                else:
                    get_console().print("\n[green]No issues found. Repository is ready![/green]")

                if plan and report.plan:
                    get_console().print(
                        f"\n[bold green]Migration plan written to {plan}[/bold green]"
                    )