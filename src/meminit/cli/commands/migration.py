"""Migration commands: migrate-ids, migrate-templates."""

from pathlib import Path

import click

from meminit.cli._helpers import (
    command_output_handler,
    get_console,
    validate_initialized,
    validate_root_path,
)
from meminit.cli.shared.output_helpers import _md_table, _write_output, maybe_capture
from meminit.cli.shared_flags import agent_repo_options
from meminit.core.services.error_codes import ErrorCode
from meminit.core.services.observability import get_current_run_id
from meminit.core.services.output_formatter import format_envelope
from meminit.core.use_cases.migrate_ids import MigrateIdsUseCase
from meminit.core.use_cases.migrate_templates import MigrateTemplatesUseCase


def register(cli: click.Group) -> None:
    """Register migration commands with the CLI."""

    @cli.command("migrate-ids")
    @click.option(
        "--dry-run/--no-dry-run",
        default=True,
        help="Preview changes without writing files",
    )
    @click.option(
        "--rewrite-references/--no-rewrite-references",
        default=False,
        help="Rewrite related_ids in other documents",
    )
    @click.option(
        "--force-restamp/--no-force-restamp",
        default=False,
        help=(
            "Reassign already-canonical IDs whose prefix/type segment does not match the "
            "namespace. Off by default: document_id is immutable, so mismatches are reported "
            "as advice only unless this flag is set."
        ),
    )
    @agent_repo_options()
    def migrate_ids(
        root,
        format,
        output,
        include_timestamp,
        correlation_id,
        dry_run,
        rewrite_references,
        force_restamp,
    ):
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

            use_case = MigrateIdsUseCase(root_dir=str(root_path))
            report = use_case.execute(
                dry_run=dry_run,
                rewrite_references=rewrite_references,
                force_restamp=force_restamp,
            )

            if format == "json":
                _write_output(
                    format_envelope(
                        command="migrate-ids",
                        root=str(root_path),
                        success=True,
                        data={"report": report.as_dict()},
                        advice=report.advice,
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
                return

            if format == "md":
                rows = [
                    [a.file, a.doc_type, a.old_id, a.new_id, a.rewritten_reference_count]
                    for a in report.actions
                ]
                _write_output(
                    "# Meminit ID Migration\n\n"
                    f"- Root: `{root_path}`\n"
                    f"- Mode: {'DRY RUN' if dry_run else 'APPLY'}\n"
                    f"- Actions: {len(report.actions)}\n"
                    f"- Skipped: {len(report.skipped_files)}\n\n"
                    "## Actions\n\n"
                    + (
                        _md_table(["File", "Type", "Old ID", "New ID", "Refs Rewritten"], rows)
                        if rows
                        else "_None_\n"
                    ),
                    output,
                )
                return

            with maybe_capture(output, format):
                get_console().print("[bold blue]Meminit ID Migration[/bold blue]")
                get_console().print(f"Root: {root_path}")
                get_console().print(f"Mode: {'DRY RUN' if dry_run else 'APPLY'}")
                get_console().print(f"Actions: {len(report.actions)}")
                if report.skipped_files:
                    get_console().print(f"Skipped: {len(report.skipped_files)}")
                if report.advice:
                    get_console().print("\nAdvice:")
                    for item in report.advice:
                        get_console().print(f"  - {item.get('message', item.get('code', ''))}")

    @cli.command("migrate-templates")
    @click.option(
        "--dry-run/--no-dry-run",
        default=True,
        help="Preview changes without writing files",
    )
    @click.option(
        "--backup/--no-backup",
        default=True,
        help="Create backup before modifying files",
    )
    @click.option(
        "--legacy-type-dirs/--no-legacy-type-dirs",
        default=True,
        help="Migrate type_directories config",
    )
    @click.option(
        "--legacy-templates/--no-legacy-templates",
        default=True,
        help="Migrate templates config",
    )
    @click.option(
        "--placeholder-syntax/--no-placeholder-syntax",
        default=True,
        help="Migrate placeholder syntax",
    )
    @click.option(
        "--rename-files/--no-rename-files",
        default=True,
        help="Rename template files to *.template.md",
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

            use_case = MigrateTemplatesUseCase(root_dir=str(root_path))
            report = use_case.execute(
                dry_run=dry_run,
                backup=backup,
                migrate_type_directories=legacy_type_dirs,
                migrate_templates=legacy_templates,
                migrate_placeholders=placeholder_syntax,
                rename_files=rename_files,
            )

            warning_entries = [
                {"code": "WARNING", "message": warning, "path": str(report.config_file)}
                for warning in report.warnings
            ]

            if format == "json":
                payload_data = report.as_dict()
                if report.success:
                    payload = format_envelope(
                        command="migrate-templates",
                        root=str(root_path),
                        success=True,
                        data=payload_data,
                        warnings=warning_entries,
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    )
                else:
                    payload = format_envelope(
                        command="migrate-templates",
                        root=str(root_path),
                        success=False,
                        data=payload_data,
                        warnings=warning_entries,
                        error={
                            "code": ErrorCode.VALIDATION_ERROR.value,
                            "message": (
                                report.warnings[0]
                                if report.warnings
                                else "Template migration failed."
                            ),
                            "details": payload_data,
                        },
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    )
                _write_output(payload, output)
                if not report.success:
                    raise SystemExit(1)
                return

            if format == "md":
                lines = [
                    "# Meminit Template Migration\n",
                    f"- Root: `{root_path}`",
                    f"- Mode: {'DRY RUN' if dry_run else 'APPLY'}",
                    f"- Config entries found: {report.config_entries_found}",
                    f"- Config entries migrated: {report.config_entries_migrated}",
                    f"- Template files found: {report.template_files_found}",
                    f"- Template files renamed: {report.template_files_renamed}",
                    f"- Placeholder replacements: {report.placeholder_replacements}",
                    "",
                ]
                if report.warnings:
                    lines.append("## Warnings\n")
                    for warning in report.warnings:
                        lines.append(f"- {warning}")
                    lines.append("")
                lines.append("## Changes\n")
                for action in report.actions:
                    if action.action_type == "config":
                        if action.value:
                            lines.append(f"- Add {action.path} = {action.value}")
                        else:
                            lines.append(f"- Remove {action.path}")
                    elif action.action_type == "file":
                        lines.append(f"- Rename {action.from_path} → {action.to_path}")
                    elif action.action_type == "replace":
                        lines.append(
                            f"- Replace {action.placeholder_from} with {action.placeholder_to} "
                            f"in {action.file} ({action.count} occurrences)"
                        )
                lines.append("")
                if report.backup_path and not dry_run:
                    lines.append(f"Backup: {report.backup_path}\n")
                _write_output("\n".join(lines), output)
                if not report.success:
                    raise SystemExit(1)
                return

            with maybe_capture(output, format):
                get_console().print("[bold blue]Meminit Template Migration[/bold blue]")
                get_console().print(f"Root: {root_path}")
                get_console().print(f"Mode: {'DRY RUN' if dry_run else 'APPLY'}")
                get_console().print(f"Config entries found: {report.config_entries_found}")
                get_console().print(f"Config entries migrated: {report.config_entries_migrated}")
                get_console().print(f"Template files found: {report.template_files_found}")
                get_console().print(f"Template files renamed: {report.template_files_renamed}")
                get_console().print(f"Placeholder replacements: {report.placeholder_replacements}")
                if report.warnings:
                    get_console().print("\nWarnings:")
                    for warning in report.warnings:
                        get_console().print(f"  - {warning}")
                if report.backup_path and not dry_run:
                    get_console().print(f"\nBackup: {report.backup_path}")

            if not report.success:
                raise SystemExit(1)
