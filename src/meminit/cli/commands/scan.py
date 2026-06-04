"""Scan command implementation."""

from pathlib import Path

import click
from rich.table import Table

from meminit.cli._helpers import (
    _write_scan_plan_artifact,
    command_output_handler,
    get_console,
    validate_root_path,
)
from meminit.cli.shared.output_helpers import _md_escape, _md_table, _write_output, maybe_capture
from meminit.cli.shared_flags import agent_repo_options
from meminit.cli.streaming import unsupported_ndjson
from meminit.core.services.observability import get_current_run_id
from meminit.core.services.output_formatter import format_envelope
from meminit.core.services.scan_plan import MigrationPlan
from meminit.core.use_cases.scan_repository import ScanRepositoryUseCase


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
                raise unsupported_ndjson(
                    "scan",
                    "meminit scan --format ndjson does not support --plan; "
                    "run scan --format json --plan for plan artifacts.",
                )

            use_case = ScanRepositoryUseCase(root_dir=str(root_path))

            if format == "ndjson":
                from meminit.cli.streaming import CoreStreamingProducer, streaming_output_handler

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
                                ["Namespace", "Docs Root", "Repo Prefix", "Exists", "Governed .md"],
                                rows,
                            ),
                            "",
                        ]
                    )
                overlaps = getattr(report, "overlapping_namespaces", None)
                if overlaps:
                    rows = [
                        [
                            o.get("parent_namespace"),
                            o.get("parent_docs_root"),
                            o.get("child_namespace"),
                            o.get("child_docs_root"),
                        ]
                        for o in overlaps
                        if isinstance(o, dict)
                    ]
                    lines.extend(
                        [
                            "## Overlapping Namespace Roots (review)",
                            "",
                            _md_table(["Parent", "Parent Root", "Child", "Child Root"], rows),
                            "",
                        ]
                    )
                if report.suggested_type_directories:
                    rows = [[k, v] for k, v in sorted(report.suggested_type_directories.items())]
                    lines.extend(
                        [
                            "## Suggested `type_directories` overrides",
                            "",
                            _md_table(["Type", "Directory"], rows),
                            "",
                        ]
                    )
                if report.ambiguous_types:
                    rows = [
                        [k, ", ".join(sorted(v))] for k, v in sorted(report.ambiguous_types.items())
                    ]
                    lines.extend(
                        [
                            "## Ambiguous Types (manual decision required)",
                            "",
                            _md_table(["Type", "Candidates"], rows),
                            "",
                        ]
                    )
                if getattr(report, "suggested_namespaces", None):
                    rows = [
                        [
                            ns.get("name"),
                            ns.get("docs_root"),
                            ns.get("repo_prefix_suggestion"),
                        ]
                        for ns in report.suggested_namespaces
                        if isinstance(ns, dict)
                    ]
                    lines.extend(
                        [
                            "## Suggested Namespaces (monorepo)",
                            "",
                            _md_table(["Name", "Docs Root", "Repo Prefix"], rows),
                            "",
                        ]
                    )
                if report.notes:
                    lines.append("## Notes\n")
                    lines.extend([f"- {_md_escape(n)}" for n in report.notes])
                    lines.append("")
                _write_output("\n".join(lines), output)
                return

            with maybe_capture(output, format):
                get_console().print("[bold blue]Meminit Scan[/bold blue]")
                get_console().print(f"Root: {root_path}")
                get_console().print(f"Docs root: {report.docs_root or 'Not found'}")
                get_console().print(f"Markdown files: {report.markdown_count}")
                if getattr(report, "governed_markdown_count", None) is not None:
                    get_console().print(
                        f"Governed markdown (all namespaces): "
                        f"{getattr(report, 'governed_markdown_count', 0)}"
                    )

                configured = getattr(report, "configured_namespaces", None)
                if configured:
                    table = Table(title="Configured namespaces")
                    table.add_column("Namespace")
                    table.add_column("Docs Root")
                    table.add_column("Repo Prefix")
                    table.add_column("Exists")
                    table.add_column("Governed .md")
                    for ns in configured:
                        if not isinstance(ns, dict):
                            continue
                        table.add_row(
                            str(ns.get("namespace")),
                            str(ns.get("docs_root")),
                            str(ns.get("repo_prefix")),
                            str(ns.get("docs_root_exists")),
                            str(ns.get("governed_markdown_count")),
                        )
                    get_console().print(table)

                overlaps = getattr(report, "overlapping_namespaces", None)
                if overlaps:
                    table = Table(title="Overlapping namespace roots (review)")
                    table.add_column("Parent")
                    table.add_column("Parent Root")
                    table.add_column("Child")
                    table.add_column("Child Root")
                    for o in overlaps:
                        if not isinstance(o, dict):
                            continue
                        table.add_row(
                            str(o.get("parent_namespace")),
                            str(o.get("parent_docs_root")),
                            str(o.get("child_namespace")),
                            str(o.get("child_docs_root")),
                        )
                    get_console().print(table)
                if report.suggested_type_directories:
                    table = Table(title="Suggested type_directories overrides")
                    table.add_column("Type")
                    table.add_column("Directory")
                    for k, v in sorted(report.suggested_type_directories.items()):
                        table.add_row(k, v)
                    get_console().print(table)
                if report.ambiguous_types:
                    table = Table(title="Ambiguous type_directories (manual decision required)")
                    table.add_column("Type")
                    table.add_column("Candidates")
                    for k, candidates in sorted(report.ambiguous_types.items()):
                        table.add_row(k, ", ".join(sorted(candidates)))
                    get_console().print(table)
                if getattr(report, "suggested_namespaces", None):
                    table = Table(title="Suggested namespaces (monorepo)")
                    table.add_column("Name")
                    table.add_column("Docs Root")
                    table.add_column("Repo Prefix")
                    for ns in report.suggested_namespaces:
                        if not isinstance(ns, dict):
                            continue
                        table.add_row(
                            str(ns.get("name")),
                            str(ns.get("docs_root")),
                            str(ns.get("repo_prefix_suggestion")),
                        )
                    get_console().print(table)
                for note in report.notes:
                    get_console().print(f"- {note}")
