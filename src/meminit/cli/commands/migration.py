"""Migration commands: migrate-ids, migrate-templates."""

from pathlib import Path

import click

from meminit.core.use_cases.migrate_ids import MigrateIdsUseCase
from meminit.core.use_cases.migrate_templates import MigrateTemplatesUseCase

from meminit.cli._helpers import command_output_handler, get_console, validate_initialized, validate_root_path
from meminit.cli.shared.output_helpers import _write_output
from meminit.cli.shared_flags import agent_repo_options
from meminit.core.services.observability import get_current_run_id, log_operation
from meminit.core.services.output_formatter import format_envelope


def register(cli: click.Group) -> None:
    """Register migration commands with the CLI."""

    @cli.command("migrate-ids")
    @click.option(
        "--dry-run/--no-dry-run",
        default=False,
        help="Show what would be changed without making changes",
    )
    @click.option(
        "--rewrite-references/--no-rewrite-references",
        default=False,
        help="Rewrite related_ids in other documents",
    )
    @agent_repo_options()
    def migrate_ids(root, format, output, include_timestamp, correlation_id, dry_run, rewrite_references):
        """Migrate legacy document IDs to canonical format."""
        run_id = get_current_run_id()
        root_path = Path(root).resolve()

        with command_output_handler(
            "migrate-ids",
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
                command="migrate-ids",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )
            validate_initialized(
                root_path,
                format=format,
                command="migrate-ids",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )

            with log_operation(
                operation="migrate_ids",
                details={"dry_run": dry_run, "rewrite_references": rewrite_references},
                run_id=run_id,
            ) as _migrate_ctx:
                use_case = MigrateIdsUseCase(root_dir=str(root_path))
                report = use_case.execute(dry_run=dry_run, rewrite_references=rewrite_references)

                _migrate_ctx["details"][
                    "documents_processed"
                ] = report.documents_processed  # type: ignore
                _migrate_ctx["details"][
                    "documents_changed"
                ] = report.documents_changed  # type: ignore
                _migrate_ctx["details"][
                    "references_updated"
                ] = report.references_updated  # type: ignore

            if format == "json":
                _write_output(
                    format_envelope(
                        command="migrate-ids",
                        root=str(root_path),
                        success=True,
                        extra_top_level={
                            "documents_processed": report.documents_processed,  # type: ignore
                            "documents_changed": report.documents_changed,  # type: ignore
                            "references_updated": report.references_updated,  # type: ignore
                            "actions": report.actions,  # type: ignore
                        },
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
            else:
                if report.actions:  # type: ignore
                    get_console().print(f"[bold cyan]Processed {report.documents_processed} documents, {report.documents_changed} changed:[/bold cyan]")  # type: ignore
                    for action in report.actions:  # type: ignore
                        if action.is_removal:  # type: ignore
                            get_console().print(f"  [red]✗[/red] {action.old_id} -> {action.new_id} (removed)")
                        else:
                            get_console().print(f"  [green]✔[/green] {action.old_id} -> {action.new_id}")
                else:
                    get_console().print("[green]No documents need ID migration.[/green]")

    @cli.command("migrate-templates")
    @click.option(
        "--dry-run/--no-dry-run",
        default=False,
        help="Show what would be changed without making changes",
    )
    @click.option(
        "--backup/--no-backup",
        default=True,
        help="Create .bak files before modifying",
    )
    @click.option(
        "--legacy-type-dirs/--no-legacy-type-dirs",
        default=False,
        help="Migrate type directories (adr/, prd/, fdd/ → 45-adr/)",
    )
    @click.option(
        "--legacy-templates/--no-legacy-templates",
        default=False,
        help="Migrate legacy template substitution syntax",
    )
    @click.option(
        "--placeholder-syntax/--no-placeholder-syntax",
        default=False,
        help="Update legacy placeholder format",
    )
    @click.option(
        "--rename-files/--no-rename-files",
        default=False,
        help="Rename files to kebab-case if not already",
    )
    @agent_repo_options()
    def migrate_templates(
        root,
        format,
        output,
        include_timestamp,
        correlation_id,
        dry_run,
        backup,
        legacy_type_dirs,
        legacy_templates,
        placeholder_syntax,
        rename_files,
    ):
        """Migrate templates and document structure to v2."""
        run_id = get_current_run_id()
        root_path = Path(root).resolve()

        with command_output_handler(
            "migrate-templates",
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
                command="migrate-templates",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )
            validate_initialized(
                root_path,
                format=format,
                command="migrate-templates",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )

            with log_operation(
                operation="migrate_templates",
                details={
                    "dry_run": dry_run,
                    "backup": backup,
                    "legacy_type_dirs": legacy_type_dirs,
                    "legacy_templates": legacy_templates,
                    "placeholder_syntax": placeholder_syntax,
                    "rename_files": rename_files,
                },
                run_id=run_id,
            ) as _migrate_ctx:
                use_case = MigrateTemplatesUseCase(root_dir=str(root_path))
                report = use_case.execute(
                    dry_run=dry_run,
                    backup=backup,
                    legacy_type_dirs=legacy_type_dirs,
                    legacy_templates=legacy_templates,
                    placeholder_syntax=placeholder_syntax,
                    rename_files=rename_files,
                )

                _migrate_ctx["details"][
                    "documents_processed"
                ] = report.documents_processed  # type: ignore
                _migrate_ctx["details"][
                    "files_moved"
                ] = report.files_moved  # type: ignore
                _migrate_ctx["details"][
                    "files_updated"
                ] = report.files_updated  # type: ignore
                _migrate_ctx["details"][
                    "backup_files"
                ] = report.backup_files  # type: ignore

            if format == "json":
                _write_output(
                    format_envelope(
                        command="migrate-templates",
                        root=str(root_path),
                        success=True,
                        extra_top_level={
                            "documents_processed": report.documents_processed,  # type: ignore
                            "files_moved": report.files_moved,  # type: ignore
                            "files_updated": report.files_updated,  # type: ignore
                            "backup_files": report.backup_files,  # type: ignore
                        },
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
            else:
                if report.files_moved:  # type: ignore
                    get_console().print(f"[bold cyan]Moved {report.files_moved} files:[/bold cyan]")  # type: ignore
                    for move in report.files_moved:  # type: ignore
                        get_console().print(f"  [green]✔[/green] {move.old} -> {move.new}")
                if report.files_updated:  # type: ignore
                    get_console().print(f"[bold cyan]Updated {report.files_updated} files:[/bold cyan]")  # type: ignore
                    for update in report.files_updated:  # type: ignore
                        get_console().print(f"  [green]✔[/green] {update.path}")
                if report.backup_files:  # type: ignore
                    get_console().print(f"[bold yellow]Created {len(report.backup_files)} backup files[/bold yellow]")  # type: ignore
                if not report.files_moved and not report.files_updated:  # type: ignore
                    get_console().print("[green]No template migration needed.[/green]")
