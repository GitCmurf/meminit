"""Index command implementation."""

from pathlib import Path

import click

from meminit.cli._helpers import command_output_handler, get_console, validate_root_path
from meminit.cli.shared.output_helpers import _md_table, _write_output
from meminit.cli.shared_flags import agent_repo_options
from meminit.core.domain.entities import Severity
from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.index_cache import IndexCache
from meminit.core.services.observability import get_current_run_id
from meminit.core.services.output_formatter import format_envelope
from meminit.core.use_cases.index_repository import IndexRepositoryUseCase


def register(cli: click.Group) -> None:
    """Register the index command with the CLI."""

    @cli.command()
    @agent_repo_options()
    @click.option(
        "--status",
        "status_filter",
        default=None,
        help="Filter by governance status (comma-separated, case-insensitive). E.g. 'Draft,Approved'.",
    )
    @click.option(
        "--impl-state",
        "impl_state_filter",
        default=None,
        help="Filter by implementation state (comma-separated, case-insensitive). E.g. 'In Progress,Blocked'.",
    )
    @click.option(
        "--output-catalog",
        is_flag=True,
        default=False,
        help="Generate catalogue.md (table view, configurable with --catalog-name or catalog_name).",
    )
    @click.option(
        "--output-kanban",
        is_flag=True,
        default=False,
        help="Generate kanban.md + kanban.css (board view).",
    )
    @click.option(
        "--catalog-name",
        default=None,
        help=(
            "Filename for the generated catalog view "
            "(if omitted, uses config or defaults to catalogue.md)."
        ),
    )
    @click.option(
        "--no-cache",
        is_flag=True,
        default=False,
        help="Clear the repo-local index cache before rebuilding.",
    )
    @click.option(
        "--rebuild-cache",
        is_flag=True,
        default=False,
        help="Force a clean rebuild by clearing the repo-local index cache first.",
    )
    @click.option(
        "--explain-cache",
        is_flag=True,
        default=False,
        help="Describe the current index cache manifest without rebuilding.",
    )
    def index(
        root,
        format,
        output,
        include_timestamp,
        correlation_id,
        status_filter,
        impl_state_filter,
        output_catalog,
        output_kanban,
        catalog_name,
        no_cache,
        rebuild_cache,
        explain_cache,
    ):
        """Build or update the repository index artifact."""
        run_id = get_current_run_id()
        root_path = Path(root).resolve()

        with command_output_handler(
            "index",
            format,
            output,
            include_timestamp,
            run_id,
            root_path,
            correlation_id=correlation_id,
        ):
            from meminit.cli._helpers import _index_output_data
            from meminit.cli.streaming import (
                CoreStreamingProducer,
                streaming_output_handler,
                write_ndjson_error,
            )
            from meminit.core.services.exit_codes import exit_code_for_error

            validate_root_path(
                root_path,
                format=format,
                command="index",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )

            # Validate flag combinations
            if no_cache and rebuild_cache:
                raise MeminitError(
                    ErrorCode.INVALID_FLAG_COMBINATION,
                    "--no-cache and --rebuild-cache are mutually exclusive.",
                    details={"flags": ["--no-cache", "--rebuild-cache"]},
                )
            if explain_cache and (no_cache or rebuild_cache):
                raise MeminitError(
                    ErrorCode.INVALID_FLAG_COMBINATION,
                    "--explain-cache cannot be combined with --no-cache or --rebuild-cache.",
                    details={
                        "flags": [
                            "--explain-cache",
                            *(["--no-cache"] if no_cache else ["--rebuild-cache"]),
                        ]
                    },
                )

            # Handle --explain-cache flag (cache inspection mode)
            if explain_cache:
                if format == "ndjson":
                    from meminit.cli.streaming import unsupported_ndjson

                    raise unsupported_ndjson(
                        "index",
                        "meminit index --explain-cache does not support --format ndjson.",
                    )
                if format != "json":
                    raise MeminitError(
                        ErrorCode.INVALID_FLAG_COMBINATION,
                        "meminit index --explain-cache requires --format json.",
                        details={"format": format},
                    )
                _write_output(
                    format_envelope(
                        command="index",
                        root=str(root_path),
                        success=True,
                        data={"cache": IndexCache(root_path).explain()},
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
                return

            # Create use case
            use_case = IndexRepositoryUseCase(
                root_dir=str(root_path),
                output_catalog=output_catalog,
                catalog_name=catalog_name,
                output_kanban=output_kanban,
                status_filter=status_filter,
                impl_state_filter=impl_state_filter,
            )

            # Handle ndjson streaming output
            if format == "ndjson":
                try:
                    stream_result = use_case.iter_stream(
                        use_cache=not no_cache,
                        clear_cache=no_cache or rebuild_cache,
                    )
                    streaming_output_handler(
                        command="index",
                        producer=CoreStreamingProducer(stream_result),
                        output=output,
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        root_path=root_path,
                        correlation_id=correlation_id,
                    )
                except MeminitError as e:
                    details = e.details if isinstance(e.details, dict) else {}
                    if "errors" in details:
                        write_ndjson_error(
                            command_name="index",
                            error=e,
                            output=output,
                            include_timestamp=include_timestamp,
                            run_id=run_id,
                            root_path=root_path,
                            correlation_id=correlation_id,
                        )
                        raise SystemExit(exit_code_for_error(e.code)) from e
                    raise

                # Check for errors in streaming result
                has_error = any(
                    w.get("severity") == Severity.ERROR.value
                    for w in stream_result.summary.warnings
                )
                if has_error:
                    raise SystemExit(1)
                return

            # Execute index use case (synchronous)
            try:
                report = use_case.execute(
                    use_cache=not no_cache,
                    clear_cache=no_cache or rebuild_cache,
                )
            except MeminitError as e:
                # Only intercept graph fatal diagnostics (details.errors present).
                # Re-raise all other MeminitErrors so command_output_handler
                # formats them consistently for text/md/json modes.
                details = e.details if isinstance(e.details, dict) else {}
                is_graph_fatal = "errors" in details

                if is_graph_fatal:
                    violations = details["errors"]

                    if format == "json":
                        _write_output(
                            format_envelope(
                                command="index",
                                root=str(root_path),
                                success=False,
                                violations=violations,
                                error={
                                    "code": e.code.value,
                                    "message": e.message,
                                    "details": e.details,
                                },
                                include_timestamp=include_timestamp,
                                run_id=run_id,
                                correlation_id=correlation_id,
                            ),
                            output,
                        )
                        raise SystemExit(exit_code_for_error(e.code)) from e

                    if format == "md":
                        lines = ["# Meminit Index\n", "- Status: error", ""]
                        lines.extend(["## Graph Violations", ""])
                        rows = [
                            [
                                "ERROR",
                                str(v.get("code")),
                                str(v.get("path")),
                                str(v.get("message")),
                            ]
                            for v in violations
                        ]
                        lines.append(_md_table(["Severity", "Code", "Path", "Message"], rows))
                        _write_output("\n".join(lines), output)

                    else:
                        from meminit.cli.shared.output_helpers import maybe_capture

                        with maybe_capture(output, format):
                            for v in violations:
                                get_console().print(
                                    f"[bold red][ERROR {v.get('code')}] {v.get('message')}[/bold red]"
                                )

                    raise SystemExit(exit_code_for_error(e.code)) from e

                raise

            # Extract warnings and determine status
            warnings_list = getattr(report, "warnings", [])
            has_error = any(w.get("severity") == Severity.ERROR.value for w in warnings_list)
            status = "error" if has_error else ("warn" if warnings_list else "ok")

            # Build output data
            data = _index_output_data(
                report,
                root_path,
                status_filter=status_filter,
                impl_state_filter=impl_state_filter,
            )
            display_edges = data["edges"]

            # Handle JSON output
            if format == "json":
                _write_output(
                    format_envelope(
                        command="index",
                        root=str(root_path),
                        success=not has_error,
                        data=data,
                        warnings=warnings_list,
                        advice=getattr(report, "advice", []),
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
                if has_error:
                    raise SystemExit(1)
                return

            # Handle Markdown output
            if format == "md":
                lines = [
                    "# Meminit Index\n",
                    f"- Status: {status}",
                    f"- Index path: `{data.get('index_path')}`",
                    f"- Nodes: {report.document_count}",
                    f"- Edges: {len(display_edges)}",
                ]
                if report.catalog_path:
                    lines.append(f"- Catalog: `{data.get('catalog_path')}`")
                if report.kanban_path:
                    lines.append(f"- Kanban: `{data.get('kanban_path')}`")

                # Add validation issues section
                if warnings_list:
                    lines.extend(["", "## Validation Issues", ""])
                    rows = [
                        [
                            str(w.get("severity")),
                            str(w.get("code")),
                            str(w.get("path")),
                            str(w.get("line")),
                            str(w.get("message")),
                        ]
                        for w in warnings_list
                    ]
                    lines.append(_md_table(["Severity", "Code", "Path", "Line", "Message"], rows))

                # Add advice section
                advice_list = getattr(report, "advice", [])
                if advice_list:
                    lines.extend(["", "## Advice", ""])
                    advice_rows = [
                        ["INFO", str(a.get("code")), str(a.get("message"))] for a in advice_list
                    ]
                    lines.append(_md_table(["Severity", "Code", "Message"], advice_rows))

                lines.append("")
                _write_output("\n".join(lines), output)
                if has_error:
                    raise SystemExit(1)
                return

            # Handle text output (default)
            from meminit.cli.shared.output_helpers import maybe_capture

            with maybe_capture(output, format):
                style = "red" if has_error else ("yellow" if warnings_list else "green")
                get_console().print(
                    f"[bold {style}]Index written:[/bold {style}] {report.index_path} "
                    f"({report.document_count} nodes, {len(display_edges)} edges)"
                )

                # Print warnings
                for warning in warnings_list:
                    get_console().print(
                        f"  - [{warning.get('severity')}] {warning.get('code')}: {warning.get('message')}"
                    )

                # Print advice
                for advice_item in getattr(report, "advice", []):
                    get_console().print(
                        f"  - [dim]advice[/dim] {advice_item.get('code')}: {advice_item.get('message')}"
                    )

                # Print generated artifacts
                if report.catalog_path:
                    get_console().print(f"[green]Catalog:[/green] {report.catalog_path}")
                if report.kanban_path:
                    get_console().print(f"[green]Kanban:[/green] {report.kanban_path}")

            # Exit with error if any validation issues occurred (applies to all formats)
            if has_error:
                raise SystemExit(1)
