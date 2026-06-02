"""Index command implementation."""

from pathlib import Path
from typing import Optional

import click

from meminit.core.domain.entities import Severity
from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.index_cache import IndexCache
from meminit.core.services.observability import get_current_run_id, log_operation
from meminit.core.services.output_formatter import format_envelope
from meminit.core.use_cases.index_repository import IndexRepositoryUseCase

from meminit.cli._helpers import (
    _index_output_data,
    command_output_handler,
    get_console,
    validate_root_path,
)
from meminit.cli.shared.output_helpers import _write_output
from meminit.cli.shared_flags import agent_repo_options


def register(cli: click.Group) -> None:
    """Register the index command with the CLI."""

    @cli.command()
    @agent_repo_options()
    @click.option("--status", help="Filter by governance status")
    @click.option("--impl-state", help="Filter by implementation state")
    @click.option(
        "--output-catalog",
        is_flag=True,
        default=False,
        help="Generate catalog markdown file",
    )
    @click.option(
        "--output-kanban",
        is_flag=True,
        default=False,
        help="Generate kanban markdown and CSS files",
    )
    @click.option("--catalog-name", help="Custom catalog filename")
    @click.option("--no-cache", is_flag=True, default=False, help="Skip cache and rebuild")
    @click.option(
        "--rebuild-cache",
        is_flag=True,
        default=False,
        help="Force cache invalidation",
    )
    @click.option("--explain-cache", is_flag=True, default=False, help="Explain cache strategy")
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
            validate_root_path(
                root_path,
                format=format,
                command="index",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )
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
                            "--no-cache",
                            "--rebuild-cache",
                        ]
                    },
                )

            use_case = IndexRepositoryUseCase(
                root_dir=str(root_path),
                status_filter=status_filter,
                impl_state_filter=impl_state_filter,
                catalog_name=catalog_name,
            )

            if format == "json":
                report = use_case.execute(use_cache=not no_cache, clear_cache=rebuild_cache)

                _write_output(
                    _index_output_data(
                        report,
                        root_path,
                        status_filter=status_filter,
                        impl_state_filter=impl_state_filter,
                    ),
                    output,
                )
            elif format == "ndjson":
                with log_operation(
                    operation="index",
                    details={
                        "status_filter": status_filter,
                        "impl_state_filter": impl_state_filter,
                        "use_cache": not no_cache,
                        "rebuild_cache": rebuild_cache,
                    },
                    run_id=run_id,
                ):
                    for item in use_case.iter_stream(use_cache=not no_cache, clear_cache=rebuild_cache):
                        if item.type == "summary":
                            continue
                        # streaming is handled by the producer
                        pass
            else:
                report = use_case.execute(use_cache=not no_cache, clear_cache=rebuild_cache)

                if report.catalog_path:
                    if format == "text":
                        with open(report.catalog_path, "r", encoding="utf-8") as f:
                            catalog_content = f.read()
                            get_console().print(catalog_content)
                if report.kanban_path:
                    get_console().print(f"[dim]Kanban board written to:[/dim] {report.kanban_path}")
                get_console().print(f"[dim]Index written to:[/dim] {report.index_path}")
                if format == "text":
                    get_console().print(f"[dim]Nodes: {report.document_count}, Edges: {len(report.edges)}[/dim]")
