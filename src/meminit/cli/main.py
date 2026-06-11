import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import click
from rich.console import Console
from rich.table import Table

from meminit.cli._helpers import (
    _DRIFT_ERROR_CODE,
    _DRIFT_ERROR_STATES,
    _drift_violations,
    _index_output_data,
    _meminit_error_for_new_document_params_validation,
    _normalize_mutation_arg,
    _state_blockers_execute,
    _state_list_execute,
    _state_list_validate_filters,
    _state_next_execute,
    _state_set_execute,
    _state_set_validate_args,
    _validate_mutation_exclusivity,
    _write_scan_plan_artifact,
    command_output_handler,
    complete_document_types,
    validate_initialized,
    validate_root_path,
)
from meminit.cli.commands.check import register as register_check
from meminit.cli.commands.context_cmd import register as register_context_cmd
from meminit.cli.commands.doctor import register as register_doctor
from meminit.cli.commands.fix import register as register_fix
from meminit.cli.commands.init_cmd import register as register_init_cmd
from meminit.cli.commands.install_precommit import register as register_install_precommit
from meminit.cli.commands.migration import register as register_migration
from meminit.cli.shared.output_helpers import (
    _flatten_warning_groups,
    _md_escape,
    _md_table,
    _render_state_blockers_json,
    _render_state_blockers_text,
    _render_state_list_json,
    _render_state_list_text,
    _render_state_next_json,
    _render_state_next_text,
    _render_state_set_json,
    _render_state_set_text,
    _write_output,
    get_console,
    maybe_capture,
)
from meminit.cli.shared_flags import agent_output_options, agent_repo_options
from meminit.cli.streaming import (
    CoreStreamingProducer,
    streaming_output_handler,
    unsupported_ndjson,
    write_ndjson_error,
)
from meminit.core.domain.entities import NewDocumentParams, Severity
from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.exit_codes import EX_COMPLIANCE_FAIL, exit_code_for_error
from meminit.core.services.index_cache import IndexCache
from meminit.core.services.observability import get_current_run_id, log_operation
from meminit.core.services.output_formatter import format_envelope, format_error_envelope
from meminit.core.services.scan_plan import MigrationPlan
from meminit.core.services.versioning import get_cli_version
from meminit.core.use_cases.check_repository import CheckRepositoryUseCase
from meminit.core.use_cases.context_repository import ContextRepositoryUseCase
from meminit.core.use_cases.doctor_repository import DoctorRepositoryUseCase
from meminit.core.use_cases.fix_repository import FixRepositoryUseCase
from meminit.core.use_cases.identify_document import IdentifyDocumentUseCase
from meminit.core.use_cases.index_repository import IndexRepositoryUseCase
from meminit.core.use_cases.init_repository import InitRepositoryUseCase
from meminit.core.use_cases.install_org_profile import InstallOrgProfileUseCase
from meminit.core.use_cases.install_precommit import InstallPrecommitUseCase
from meminit.core.use_cases.migrate_ids import MigrateIdsUseCase
from meminit.core.use_cases.migrate_templates import MigrateTemplatesUseCase
from meminit.core.use_cases.new_document import NewDocumentUseCase
from meminit.core.use_cases.org_status import OrgStatusUseCase
from meminit.core.use_cases.resolve_document import ResolveDocumentUseCase
from meminit.core.use_cases.scan_repository import ScanRepositoryUseCase
from meminit.core.use_cases.vendor_org_profile import VendorOrgProfileUseCase


@click.group()
@click.version_option(version=get_cli_version(), prog_name="meminit")
@click.option(
    "--no-color",
    is_flag=True,
    default=False,
    help="Disable ANSI colors in text output.",
)
@click.option("--verbose", is_flag=True, default=False, help="Enable verbose debug logging.")
@click.pass_context
def cli(ctx: click.Context, no_color: bool, verbose: bool):
    """Meminit DocOps CLI"""
    if no_color:
        os.environ["NO_COLOR"] = "1"
        os.environ["RICH_NO_COLOR"] = "1"
    if verbose:
        previous_debug = os.environ.get("MEMINIT_DEBUG")
        os.environ["MEMINIT_DEBUG"] = "1"

        def _restore_debug() -> None:
            if previous_debug is None:
                os.environ.pop("MEMINIT_DEBUG", None)
            else:
                os.environ["MEMINIT_DEBUG"] = previous_debug

        ctx.call_on_close(_restore_debug)

    ctx.ensure_object(dict)
    ctx.obj["console"] = Console(no_color=no_color)


register_check(cli)
register_doctor(cli)
register_fix(cli)
register_install_precommit(cli)
register_context_cmd(cli)
register_init_cmd(cli)
register_migration(cli)
from meminit.cli.commands.scan import register as register_scan

register_scan(cli)
from meminit.cli.commands.index import register as register_index

register_index(cli)
from meminit.cli.commands.doc_resolution import register as register_doc_resolution

register_doc_resolution(cli)
from meminit.cli.commands.capabilities import register as register_capabilities

register_capabilities(cli)


@cli.command(name="new")
@click.argument("doc_type", required=False, shell_complete=complete_document_types)
@click.argument("title", required=False)
@agent_repo_options()
@click.option("--namespace", default=None, help="Namespace to create the doc in (monorepo mode)")
@click.option("--owner", default=None, help="Set owner frontmatter field")
@click.option("--area", default=None, help="Set area frontmatter field")
@click.option("--description", default=None, help="Set description frontmatter field")
@click.option(
    "--status",
    default="Draft",
    help="Set status (Draft|In Review|Approved|Superseded)",
)
@click.option("--keywords", multiple=True, help="Set keywords (repeatable)")
@click.option(
    "--related-ids",
    multiple=True,
    help="Set related_ids (repeatable, REPO-TYPE-SEQ)",
)
@click.option(
    "--id",
    "document_id",
    default=None,
    help="Specify exact document ID (REPO-TYPE-SEQ; deterministic mode)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview without writing file (JSON includes would_create)",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Output decision reasoning (stderr for JSON)",
)
@click.option("--list-types", is_flag=True, default=False, help="List valid document types")
@click.option(
    "--edit",
    is_flag=True,
    default=False,
    help="Open in editor after creation (no --dry-run/--format json)",
)
@click.option(
    "--interactive",
    is_flag=True,
    default=False,
    help="Interactive prompts for missing fields (no --format json)",
)
def new_doc(
    doc_type,
    title,
    root,
    namespace,
    owner,
    area,
    description,
    status,
    keywords,
    related_ids,
    document_id,
    dry_run,
    verbose,
    list_types,
    edit,
    format,
    output,
    include_timestamp,
    correlation_id,
    interactive,
):
    """Create a new document of TYPE with TITLE."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "new",
        format,
        output,
        include_timestamp,
        run_id,
        root_path,
        correlation_id=correlation_id,
    ):
        if interactive and format == "json":
            raise MeminitError(
                ErrorCode.INVALID_FLAG_COMBINATION,
                "--interactive and --format json are incompatible",
            )

        if edit and (dry_run or format == "json"):
            raise MeminitError(
                ErrorCode.INVALID_FLAG_COMBINATION,
                "--edit is incompatible with --dry-run and --format json",
            )

        if list_types and (doc_type or title):
            raise MeminitError(
                ErrorCode.INVALID_FLAG_COMBINATION,
                "--list-types cannot be combined with TYPE or TITLE arguments",
            )

        if list_types:
            validate_root_path(
                root_path,
                format=format,
                command="new",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )
            validate_initialized(
                root_path,
                format=format,
                command="new",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )
            use_case = NewDocumentUseCase(str(root_path))
            types_list = use_case.get_available_types(namespace)

            if format == "json":
                _write_output(
                    format_envelope(
                        command="new",
                        root=str(root_path),
                        success=True,
                        data={"types": types_list},
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
            elif format == "md":
                lines = ["# Meminit New", "", "## Valid Document Types", ""]
                for item in types_list:
                    lines.append(f"- `{item['type']}` → `{item['directory']}`")
                _write_output("\n".join(lines), output)
            else:
                with maybe_capture(output, format):
                    get_console().print("[bold blue]Valid Document Types:[/bold blue]")
                    for item in types_list:
                        get_console().print(f"  {item['type']:10} → {item['directory']}")
            return

        if interactive:
            validate_root_path(
                root_path,
                format=format,
                command="new",
                output=output,
                include_timestamp=include_timestamp,
                run_id=run_id,
                correlation_id=correlation_id,
            )
            use_case = NewDocumentUseCase(str(root_path))
            valid_types = use_case.get_valid_types(namespace)
            if not doc_type:
                doc_type = click.prompt("Document type", type=click.Choice(valid_types))
            if not title:
                title = click.prompt("Document title")
            if not owner:
                owner = click.prompt("Owner (optional)", default="__TBD__", show_default=True)
            if not area:
                area = click.prompt("Area (optional)", default="", show_default=False)
            if not description:
                description = click.prompt("Description (optional)", default="", show_default=False)

        if not doc_type or not title:
            raise MeminitError(
                ErrorCode.INVALID_FLAG_COMBINATION,
                "TYPE and TITLE are required unless --list-types is specified",
            )

        validate_root_path(
            root_path,
            format=format,
            command="new",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )
        validate_initialized(
            root_path,
            format=format,
            command="new",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )

        if doc_type.lower() == "adr":
            doc_type = "ADR"

        try:
            params = NewDocumentParams(
                doc_type=doc_type,
                title=title,
                namespace=namespace,
                owner=owner,
                area=area,
                description=description,
                status=status,
                keywords=list(keywords) if keywords else None,
                related_ids=list(related_ids) if related_ids else None,
                document_id=document_id,
                dry_run=dry_run,
                verbose=verbose,
            )
        except ValueError as exc:
            raise _meminit_error_for_new_document_params_validation(exc) from exc

        use_case = NewDocumentUseCase(str(root_path))
        result = use_case.execute_with_params(params)

        if not result.success:
            if isinstance(result.error, MeminitError):
                raise result.error
            raise MeminitError(
                ErrorCode.UNKNOWN_ERROR,
                str(result.error) if result.error else "Unknown error",
            )

        if format == "json":
            if result.reasoning and verbose:
                for entry in result.reasoning:
                    sys.stderr.write(f"# {entry['decision']}: {entry['value']}")
                    if "source" in entry:
                        sys.stderr.write(f" (source: {entry['source']})")
                    elif "method" in entry:
                        sys.stderr.write(f" (method: {entry['method']})")
                    sys.stderr.write("\n")
                sys.stderr.flush()
            response_data: Dict[str, Any] = {
                "path": result.path.relative_to(root_path).as_posix() if result.path else None,
                "document_id": result.document_id,
                "type": result.doc_type,
                "title": result.title,
                "status": result.status,
                "version": result.version,
                "owner": result.owner,
                "area": result.area,
                "last_updated": result.last_updated,
                "docops_version": result.docops_version,
                "description": result.description,
                "keywords": result.keywords or [],
                "related_ids": result.related_ids or [],
            }

            # Add Templates v2 fields if available
            if result.rendered_content is not None:
                response_data["rendered_content"] = result.rendered_content
            if result.content_sha256 is not None:
                response_data["content_sha256"] = result.content_sha256
            if result.template_info is not None:
                response_data["template"] = result.template_info
            if dry_run:
                response_data["dry_run"] = True
                response_data["would_create"] = {
                    "path": response_data["path"],
                    "document_id": response_data["document_id"],
                    "type": response_data["type"],
                    "title": response_data["title"],
                }
            _write_output(
                format_envelope(
                    command="new",
                    root=str(root_path),
                    success=True,
                    data=response_data,
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
        elif format == "md":
            rel_path = result.path.relative_to(root_path).as_posix() if result.path else None
            lines = [
                "# Meminit New",
                "",
                f"- Status: {'dry-run' if dry_run else 'ok'}",
                f"- Type: `{_md_escape(result.doc_type)}`",
                f"- Title: `{_md_escape(result.title)}`",
            ]
            if result.document_id:
                lines.append(f"- Document ID: `{_md_escape(result.document_id)}`")
            if rel_path:
                lines.append(f"- Path: `{_md_escape(rel_path)}`")
            if dry_run:
                lines.extend(
                    [
                        "",
                        "## Would Create",
                        "",
                        f"- Path: `{_md_escape(rel_path)}`",
                        f"- Document ID: `{_md_escape(result.document_id)}`",
                    ]
                )
            _write_output("\n".join(lines), output)
        else:
            with maybe_capture(output, format):
                if dry_run:
                    get_console().print(
                        f"[bold yellow]Would create {result.doc_type}: {result.path}[/bold yellow]"
                    )
                else:
                    get_console().print(
                        f"[bold green]Created {result.doc_type}: {result.path}[/bold green]"
                    )

        if edit and not dry_run and result.path:
            editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
            if editor:
                editor_argv = shlex.split(editor, posix=(os.name != "nt"))
                import subprocess

                subprocess.run([*editor_argv, str(result.path)], check=False)


@cli.group()
def adr():
    """ADR tools (compatibility alias)."""
    pass


@adr.command(name="new")
@click.argument("title")
@agent_repo_options()
@click.option("--namespace", default=None, help="Namespace to create the ADR in (monorepo mode)")
def adr_new(title, root, format, output, include_timestamp, correlation_id, namespace):
    """Create a new ADR (alias for 'meminit new ADR')."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "adr new",
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
            command="adr new",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )
        validate_initialized(
            root_path,
            format=format,
            command="adr new",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )

        use_case = NewDocumentUseCase(str(root_path))
        params = NewDocumentParams(
            doc_type="ADR",
            title=title,
            namespace=namespace,
            verbose=os.environ.get("MEMINIT_DEBUG") == "1",
        )
        result = use_case.execute_with_params(params)

        if not result.success:
            if isinstance(result.error, MeminitError):
                raise result.error
            raise MeminitError(
                ErrorCode.UNKNOWN_ERROR,
                str(result.error) if result.error else "Unknown error",
            )

        rel_path = result.path.relative_to(root_path).as_posix() if result.path else None
        if format == "json":
            response_data = {
                "path": rel_path,
                "document_id": result.document_id,
                "type": result.doc_type,
                "title": result.title,
                "status": result.status,
                "version": result.version,
                "owner": result.owner,
                "area": result.area,
                "last_updated": result.last_updated,
                "docops_version": result.docops_version,
                "description": result.description,
                "keywords": result.keywords or [],
                "related_ids": result.related_ids or [],
            }
            _write_output(
                format_envelope(
                    command="adr new",
                    root=str(root_path),
                    success=True,
                    data=response_data,
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
        elif format == "md":
            lines = [
                "# Meminit ADR New",
                "",
                "- Status: ok",
                f"- Title: `{_md_escape(result.title)}`",
            ]
            if rel_path:
                lines.append(f"- Path: `{_md_escape(rel_path)}`")
            _write_output("\n".join(lines), output)
        else:
            with maybe_capture(output, format):
                get_console().print(f"[bold green]Created ADR: {result.path}[/bold green]")


@cli.group()
def org():
    """Org profiles (XDG install + vendoring into repos)."""
    pass


@org.command("install")
@click.option("--profile", default="default", help="Org profile name to install")
@click.option("--dry-run/--no-dry-run", default=True, help="Preview without writing to XDG paths")
@click.option("--force/--no-force", default=False, help="Overwrite an existing installed profile")
@agent_output_options()
def org_install(profile, dry_run, force, format, output, include_timestamp, correlation_id):
    """Install the packaged org profile into XDG user data directories."""
    run_id = get_current_run_id()
    with command_output_handler(
        "org install",
        format,
        output,
        include_timestamp,
        run_id,
        correlation_id=correlation_id,
    ):
        use_case = InstallOrgProfileUseCase()
        report = use_case.execute(profile_name=profile, dry_run=dry_run, force=force)

        if format == "json":
            _write_output(
                format_envelope(
                    command="org install",
                    success=True,
                    data=report.as_dict(),
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
            return

        with maybe_capture(output, format):
            get_console().print("[bold blue]Meminit Org Install[/bold blue]")
            get_console().print(f"Profile: {profile}")
            get_console().print(report.message)


@org.command("vendor")
@agent_repo_options()
@click.option("--profile", default="default", help="Org profile name to vendor")
@click.option("--dry-run/--no-dry-run", default=True, help="Preview without writing files")
@click.option(
    "--force/--no-force",
    default=False,
    help="Overwrite an existing lock and update vendored files",
)
@click.option(
    "--include-org-docs/--no-include-org-docs",
    default=True,
    help="Vendor ORG governance markdown docs too",
)
def org_vendor(
    root,
    profile,
    dry_run,
    force,
    include_org_docs,
    format,
    output,
    include_timestamp,
    correlation_id,
):
    """Vendor (copy + pin) org standards into a repo to prevent unintentional drift."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "org vendor",
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
            command="org vendor",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )

        use_case = VendorOrgProfileUseCase(root_dir=str(root_path))
        report = use_case.execute(
            profile_name=profile,
            dry_run=dry_run,
            force=force,
            include_org_docs=include_org_docs,
        )

        if format == "json":
            _write_output(
                format_envelope(
                    command="org vendor",
                    root=str(root_path),
                    success=True,
                    data=report.as_dict(),
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
            return

        with maybe_capture(output, format):
            get_console().print("[bold blue]Meminit Org Vendor[/bold blue]")
            get_console().print(report.message)


@org.command("status")
@agent_repo_options()
@click.option("--profile", default="default", help="Org profile name")
def org_status(root, profile, format, output, include_timestamp, correlation_id):
    """Show org profile install + repo lock status (drift visibility)."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "org status",
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
            command="org status",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )

        use_case = OrgStatusUseCase(root_dir=str(root_path))
        report = use_case.execute(profile_name=profile)

        if format == "json":
            _write_output(
                format_envelope(
                    command="org status",
                    root=str(root_path),
                    success=True,
                    data=report.as_dict(),
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
            return

        with maybe_capture(output, format):
            get_console().print("[bold blue]Meminit Org Status[/bold blue]")
            get_console().print(f"Profile: {profile}")
            get_console().print(f"Global installed: {report.global_installed}")


@cli.group()
def state():
    """Manage project-state.yaml document entries."""
    pass


@state.command("set")
@click.argument("document_id")
@agent_repo_options()
@click.option("--impl-state", help="Set implementation state (e.g., 'In Progress').")
@click.option("--notes", help="Set notes (max 500 chars).")
@click.option("--actor", help="Override the updated_by actor identity.")
@click.option("--clear", "-c", is_flag=True, help="Clear the tracking state for this document.")
@click.option("--priority", help="Set priority (P0, P1, P2, P3).")
@click.option("--depends-on", multiple=True, help="Replace depends_on list (repeatable).")
@click.option("--add-depends-on", multiple=True, help="Add to depends_on (repeatable).")
@click.option("--remove-depends-on", multiple=True, help="Remove from depends_on.")
@click.option("--clear-depends-on", is_flag=True, help="Clear depends_on list.")
@click.option("--blocked-by", multiple=True, help="Replace blocked_by list (repeatable).")
@click.option("--add-blocked-by", multiple=True, help="Add to blocked_by (repeatable).")
@click.option("--remove-blocked-by", multiple=True, help="Remove from blocked_by.")
@click.option("--clear-blocked-by", is_flag=True, help="Clear blocked_by list.")
@click.option("--assignee", help="Set assignee (empty string to clear).")
@click.option("--next-action", help="Set next action (empty string to clear).")
def state_set(
    document_id,
    root,
    format,
    output,
    include_timestamp,
    correlation_id,
    impl_state,
    notes,
    actor,
    clear,
    priority,
    depends_on,
    add_depends_on,
    remove_depends_on,
    clear_depends_on,
    blocked_by,
    add_blocked_by,
    remove_blocked_by,
    clear_blocked_by,
    assignee,
    next_action,
):
    """Set, update, or clear a document's implementation state."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "state set",
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
            command="state set",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )
        validate_initialized(
            root_path,
            format=format,
            command="state set",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )

        _state_set_validate_args(
            impl_state,
            notes,
            clear,
            priority,
            depends_on,
            add_depends_on,
            remove_depends_on,
            clear_depends_on,
            blocked_by,
            add_blocked_by,
            remove_blocked_by,
            clear_blocked_by,
            assignee,
            next_action,
        )
        result = _state_set_execute(
            root_path,
            document_id,
            impl_state,
            notes,
            actor,
            clear,
            priority,
            depends_on,
            add_depends_on,
            remove_depends_on,
            clear_depends_on,
            blocked_by,
            add_blocked_by,
            remove_blocked_by,
            clear_blocked_by,
            assignee,
            next_action,
        )

        if format == "json":
            _render_state_set_json(
                result,
                root_path,
                include_timestamp,
                run_id,
                correlation_id,
                output,
            )
            return
        _render_state_set_text(result, format, output)


@state.command("get")
@click.argument("document_id")
@agent_repo_options()
def state_get(document_id, root, format, output, include_timestamp, correlation_id):
    """Get a document's implementation state."""
    from meminit.core.use_cases.state_document import StateDocumentUseCase

    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "state get",
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
            command="state get",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )
        validate_initialized(
            root_path,
            format=format,
            command="state get",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )

        use_case = StateDocumentUseCase(str(root_path), strict_config=True)
        result = use_case.get_state(document_id)

        if format == "json":
            _write_output(
                format_envelope(
                    command="state get",
                    root=str(root_path),
                    success=True,
                    data=result.entry,
                    warnings=result.warnings,
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
            return

        if format == "md":
            if result.entry is None:
                raise SystemExit(1)
            _write_output(
                f"# Meminit State Get\n\n"
                f"- Document ID: `{document_id}`\n"
                f"- Impl State: {result.entry.get('impl_state')}\n"
                f"- Updated By: {result.entry.get('updated_by')}\n"
                f"- Updated: {result.entry.get('updated')}\n",
                output,
            )
            return

        with maybe_capture(output, format):
            if result.entry is None:
                raise SystemExit(1)
            get_console().print(f"[bold blue]{document_id}[/bold blue]")
            get_console().print(f"Impl State: {result.entry.get('impl_state')}")
            get_console().print(f"Updated By: {result.entry.get('updated_by')}")
            get_console().print(f"Updated: {result.entry.get('updated')}")
            if result.entry.get("notes"):
                get_console().print(f"Notes: {result.entry.get('notes')}")


@state.command("list")
@agent_repo_options()
@click.option("--ready", is_flag=True, default=False, help="Show only ready entries.")
@click.option("--no-ready", is_flag=True, default=False, help="Show only non-ready entries.")
@click.option("--blocked", is_flag=True, default=False, help="Show only blocked entries.")
@click.option("--no-blocked", is_flag=True, default=False, help="Show only non-blocked entries.")
@click.option("--assignee", multiple=True, help="Filter by assignee (repeatable).")
@click.option("--priority", multiple=True, help="Filter by priority (repeatable, e.g., P0 P1).")
@click.option(
    "--impl-state", "impl_state", multiple=True, help="Filter by impl_state (repeatable)."
)
def state_list(
    root,
    format,
    output,
    include_timestamp,
    correlation_id,
    ready,
    no_ready,
    blocked,
    no_blocked,
    assignee,
    priority,
    impl_state,
):
    """List entries in project-state.yaml with optional filters."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "state list",
        format,
        output,
        include_timestamp,
        run_id,
        root_path,
        correlation_id=correlation_id,
    ):
        (
            ready_filter,
            blocked_filter,
            assignee_list,
            priority_list,
            impl_state_list,
        ) = _state_list_validate_filters(
            ready, no_ready, blocked, no_blocked, assignee, priority, impl_state
        )

        result, valid_impl_states, valid_doc_statuses = _state_list_execute(
            root_path,
            format,
            include_timestamp,
            run_id,
            output,
            correlation_id,
            ready_filter,
            blocked_filter,
            assignee_list,
            priority_list,
            impl_state_list,
        )

        if format == "json":
            _render_state_list_json(
                result,
                valid_impl_states,
                valid_doc_statuses,
                root_path,
                include_timestamp,
                run_id,
                correlation_id,
                output,
            )
            return

        _render_state_list_text(result, valid_impl_states, valid_doc_statuses, format, output)


@state.command("next")
@agent_repo_options()
@click.option("--assignee", help="Restrict candidates to a specific assignee.")
@click.option("--priority-at-least", help="Restrict to priorities at or above threshold (P0-P3).")
def state_next(
    root, format, output, include_timestamp, correlation_id, assignee, priority_at_least
):
    """Return the deterministically-selected next work item."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "state next",
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
            command="state next",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )
        validate_initialized(
            root_path,
            format=format,
            command="state next",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )
        result = _state_next_execute(root_path, assignee, priority_at_least)
        if format == "json":
            _render_state_next_json(
                result, root_path, include_timestamp, run_id, correlation_id, output
            )
            return
        _render_state_next_text(result, format, output)


@state.command("blockers")
@agent_repo_options()
@click.option("--assignee", help="Restrict to a specific assignee.")
def state_blockers(root, format, output, include_timestamp, correlation_id, assignee):
    """List blocked work items and their open blockers."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "state blockers",
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
            command="state blockers",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )
        validate_initialized(
            root_path,
            format=format,
            command="state blockers",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )
        result = _state_blockers_execute(root_path, assignee)
        if format == "json":
            _render_state_blockers_json(
                result, root_path, include_timestamp, run_id, correlation_id, output
            )
            return
        _render_state_blockers_text(result, format, output)


@cli.group()
def protocol():
    """Protocol governance: check and sync governed files."""
    pass


@protocol.command("check")
@agent_repo_options()
@click.option(
    "--asset",
    "asset_ids",
    multiple=True,
    help="Restrict check to specific asset IDs (repeatable).",
)
def protocol_check(asset_ids, root, format, output, include_timestamp, correlation_id):
    """Check protocol assets for drift (read-only)."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "protocol check",
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
            command="protocol check",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )

        from meminit.core.use_cases.protocol_check import ProtocolChecker

        checker = ProtocolChecker(str(root_path))
        ids = list(asset_ids) if asset_ids else None
        report = checker.execute(asset_ids=ids)

        exit_code = 0 if report.success else EX_COMPLIANCE_FAIL

        violations = _drift_violations(report.assets, "status")

        if format == "json":
            _write_output(
                format_envelope(
                    command="protocol check",
                    root=str(root_path),
                    success=report.success,
                    data={
                        "summary": report.summary,
                        "assets": report.assets,
                    },
                    violations=violations,
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
            raise SystemExit(exit_code)

        # text and md formatting
        if format == "md":
            headers = ["Status", "Asset ID", "Path"]
            rows = []
            for a in report.assets:
                rows.append([a["status"].upper(), a["id"], a["target_path"]])
            _write_output(_md_table(headers, rows), output)
            raise SystemExit(exit_code)

        with maybe_capture(output, format):
            get_console().print("[bold blue]Meminit Protocol Check[/bold blue]")
            if report.success:
                get_console().print("[bold green]All protocol assets aligned.[/bold green]")
            else:
                for a in report.assets:
                    if a["status"] == "aligned":
                        get_console().print(f"  OK {a['target_path']}")
                    else:
                        color = "red" if not a["auto_fixable"] else "yellow"
                        get_console().print(
                            f"  [{color}]{a['status'].upper()}[/{color}] {a['target_path']}"
                        )
        raise SystemExit(exit_code)


@protocol.command("sync")
@agent_repo_options()
@click.option(
    "--asset",
    "asset_ids",
    multiple=True,
    help="Restrict sync to specific asset IDs (repeatable).",
)
@click.option(
    "--dry-run/--no-dry-run", default=True, help="Preview without writing (default: dry-run)."
)
@click.option("--force/--no-force", default=False, help="Allow overwriting tampered assets.")
def protocol_sync(
    asset_ids, dry_run, force, root, format, output, include_timestamp, correlation_id
):
    """Synchronize protocol assets with the canonical contract."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "protocol sync",
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
            command="protocol sync",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )

        from meminit.core.use_cases.protocol_sync import ProtocolSyncer

        syncer = ProtocolSyncer(str(root_path))
        ids = list(asset_ids) if asset_ids else None
        report = syncer.execute(dry_run=dry_run, force=force, asset_ids=ids)

        exit_code = 0 if report.success else EX_COMPLIANCE_FAIL

        if report.dry_run:
            sync_violations = (
                _drift_violations(report.assets, "prior_status") if not report.success else []
            )
        else:
            refused = [a for a in report.assets if a["action"] == "refuse"]
            sync_violations = _drift_violations(refused, "prior_status") if refused else []

        if format == "json":
            _write_output(
                format_envelope(
                    command="protocol sync",
                    root=str(root_path),
                    success=report.success,
                    data={
                        "dry_run": report.dry_run,
                        "applied": report.applied,
                        "summary": report.summary,
                        "assets": report.assets,
                    },
                    violations=sync_violations,
                    warnings=report.warnings,
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
            raise SystemExit(exit_code)

        if format == "md":
            headers = ["Action", "Asset ID", "Path"]
            rows = []
            for a in report.assets:
                detail = a["action"]
                if a.get("preserved_user_bytes") is not None:
                    detail += f" ({a['preserved_user_bytes']} user bytes preserved)"
                rows.append([detail, a["id"], a["target_path"]])
            _write_output(_md_table(headers, rows), output)
            raise SystemExit(exit_code)

        with maybe_capture(output, format):
            label = "DRY RUN" if dry_run else "APPLY"
            get_console().print(
                f"[bold blue]Meminit Protocol Sync[/bold blue] [yellow]({label})[/yellow]"
            )
            for a in report.assets:
                if a["action"] == "noop":
                    get_console().print(f"  [dim]noop[/dim] {a['target_path']}")
                elif a["action"] == "rewrite":
                    msg = f"rewrite {a['target_path']}"
                    if a.get("preserved_user_bytes") is not None:
                        msg += f" ({a['preserved_user_bytes']} user bytes preserved)"
                    get_console().print(f"  [green]{msg}[/green]")
                elif a["action"] == "refuse":
                    get_console().print(f"  [red]refuse {a['target_path']}[/red]")
        raise SystemExit(exit_code)


if __name__ == "__main__":
    cli()
