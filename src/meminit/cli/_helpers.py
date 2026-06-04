import contextlib
from pathlib import Path
from typing import Any, Optional

from meminit.cli.shared.output_helpers import (
    _md_escape,
    _unexpected_error_details,
    _write_output,
    get_console,
    maybe_capture,
)
from meminit.cli.shared_flags import command_supports_ndjson
from meminit.cli.streaming import unsupported_ndjson, write_ndjson_error
from meminit.core.domain.entities import NewDocumentParams
from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.exit_codes import exit_code_for_error
from meminit.core.services.index_helpers import build_index_output_data, filter_index_edges
from meminit.core.services.observability import get_current_run_id
from meminit.core.services.output_formatter import (
    format_envelope,
    format_error_envelope,
    normalize_correlation_id,
)
from meminit.core.services.path_utils import is_safe_cli_output_path, relative_path_string


@contextlib.contextmanager
def command_output_handler(
    command_name: str,
    format: str,
    output: Optional[str],
    include_timestamp: bool,
    run_id: str,
    root_path: Optional[Path] = None,
    correlation_id: Optional[str] = None,
):
    """Centralized error handling and output formatting for CLI commands."""
    # Validate correlation_id early so JSON mode can emit a structured error
    # envelope instead of a raw Click usage error.
    if correlation_id is not None:
        try:
            normalize_correlation_id(correlation_id)
        except ValueError as e:
            error_msg = f"Invalid --correlation-id: {e}"
            if format == "json":
                _write_output(
                    format_error_envelope(
                        command=command_name,
                        root=root_path,
                        error_code=ErrorCode.INVALID_FLAG_COMBINATION,
                        message=error_msg,
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                    ),
                    output,
                )
            elif format == "ndjson":
                write_ndjson_error(
                    command_name=command_name,
                    error=MeminitError(ErrorCode.INVALID_FLAG_COMBINATION, error_msg),
                    output=output,
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    root_path=root_path,
                    correlation_id=None,
                )
            else:
                _write_output(f"Error: {error_msg}\n", output)
            raise SystemExit(exit_code_for_error(ErrorCode.INVALID_FLAG_COMBINATION)) from e
    if format == "ndjson" and not command_supports_ndjson(command_name):
        error = unsupported_ndjson(
            command_name,
            f"meminit {command_name} does not support --format ndjson.",
        )
        write_ndjson_error(
            command_name=command_name,
            error=error,
            output=output,
            include_timestamp=include_timestamp,
            run_id=run_id,
            root_path=root_path,
            correlation_id=correlation_id,
        )
        raise SystemExit(exit_code_for_error(error.code))
    try:
        yield
    except MeminitError as e:
        if format == "ndjson":
            write_ndjson_error(
                command_name=command_name,
                error=e,
                output=output,
                include_timestamp=include_timestamp,
                run_id=run_id,
                root_path=root_path,
                correlation_id=correlation_id,
            )
        elif format == "json":
            _write_output(
                format_error_envelope(
                    command=command_name,
                    root=root_path,
                    error_code=e.code,
                    message=e.message,
                    details=e.details,
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
        elif format == "md":
            _write_output(
                f"# Error\n\n- Code: {e.code.value}\n- Message: {_md_escape(e.message)}\n",
                output,
            )
        else:
            with maybe_capture(output, format):
                # soft_wrap avoids rich hard-wrapping long paths (e.g. in the
                # message) across lines when output is captured to a file.
                get_console().print(
                    f"[bold red][ERROR {e.code.value}] {e.message}[/bold red]",
                    soft_wrap=True,
                )
        raise SystemExit(exit_code_for_error(e.code)) from e
    except Exception as e:
        # Secure error handling (Item 2): Mask raw exceptions in user-facing message
        safe_msg = "An unexpected internal error occurred."
        if format == "json":
            _write_output(
                format_error_envelope(
                    command=command_name,
                    root=root_path,
                    error_code=ErrorCode.UNKNOWN_ERROR,
                    message=safe_msg,
                    details=_unexpected_error_details(e),
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
        elif format == "ndjson":
            write_ndjson_error(
                command_name=command_name,
                error=MeminitError(
                    ErrorCode.UNKNOWN_ERROR,
                    safe_msg,
                    details=_unexpected_error_details(e),
                ),
                output=output,
                include_timestamp=include_timestamp,
                run_id=run_id,
                root_path=root_path,
                correlation_id=correlation_id,
            )
        elif format == "md":
            _write_output(
                f"# Error\n\n- Code: UNKNOWN_ERROR\n- Message: {safe_msg}\n",
                output,
            )
        else:
            with maybe_capture(output, format):
                get_console().print(
                    f"[bold red][ERROR UNKNOWN_ERROR] {safe_msg}[/bold red]", soft_wrap=True
                )

        # Always log the real error to stderr for operators
        import click

        click.echo(f"INTERNAL ERROR: {e}", err=True)
        raise SystemExit(exit_code_for_error(ErrorCode.UNKNOWN_ERROR))


def complete_document_types(ctx, param, incomplete: str):
    """Shell completion for document types (F8.2)."""
    from meminit.core.services.repo_config import load_repo_layout

    root = ctx.params.get("root", ".")
    root_path = Path(root).resolve()

    try:
        layout = load_repo_layout(str(root_path))
        ns = layout.default_namespace()
        if ns:
            types = sorted(ns.type_directories.keys())
            return [t for t in types if t.startswith(incomplete.upper())]
    except Exception:
        pass
    return []


def _meminit_error_for_new_document_params_validation(exc: ValueError) -> MeminitError:
    """Translate NewDocumentParams validation failures into structured CLI errors."""
    message = str(exc)
    if "document_id" in message:
        code = ErrorCode.INVALID_ID_FORMAT
    elif "related_ids" in message or "superseded_by" in message:
        code = ErrorCode.INVALID_RELATED_ID
    elif "status" in message:
        code = ErrorCode.INVALID_STATUS
    else:
        code = ErrorCode.INVALID_FIELD
    return MeminitError(
        code,
        message,
        details={"validation_error": message, "source": "NewDocumentParams"},
    )


def _write_scan_plan_artifact(
    *,
    plan: str,
    root_path: Path,
    migration_plan: Any,
    format: str,
    output: Optional[str],
    include_timestamp: bool,
    run_id: str,
    correlation_id: Optional[str],
    empty: bool = False,
) -> None:
    plan_path = Path(plan)
    if not is_safe_cli_output_path(plan_path):
        raise MeminitError(
            ErrorCode.PATH_ESCAPE,
            f"Plan path is considered unsafe: {plan}",
            details={"plan_path": plan},
        )

    plan_json = format_envelope(
        command="scan",
        root=str(root_path),
        success=True,
        data={"plan": migration_plan.as_dict()},
        include_timestamp=include_timestamp,
        run_id=run_id,
        correlation_id=correlation_id,
    )
    try:
        with open(plan_path, "w", encoding="utf-8") as f:
            f.write(plan_json + "\n")
    except OSError as e:
        if format == "json":
            _write_output(
                format_error_envelope(
                    command="scan",
                    root=str(root_path),
                    error_code=ErrorCode.UNKNOWN_ERROR,
                    message=f"Failed to save plan: {plan}",
                    details={"plan_path": plan, "reason": str(e)},
                    run_id=run_id,
                    include_timestamp=include_timestamp,
                    correlation_id=correlation_id,
                ),
                output,
            )
            raise SystemExit(1) from e
        get_console().print(f"[bold red]Failed to save plan: {e}[/bold red]")
        raise SystemExit(1) from e

    if format != "json":
        adjective = "empty " if empty else ""
        style = "dim" if empty else "bold green"
        get_console().print(f"[{style}]Saved {adjective}migration plan to {plan}[/{style}]")


def _index_output_data(
    report: Any,
    root_path: Path,
    *,
    status_filter: str | None = None,
    impl_state_filter: str | None = None,
) -> dict[str, Any]:
    return build_index_output_data(
        report,
        root_path,
        status_filter=status_filter,
        impl_state_filter=impl_state_filter,
    )


def validate_root_path(
    root_path: Path,
    format: str = "text",
    command: str = "unknown",
    include_timestamp: bool = False,
    run_id: Optional[str] = None,
    output: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """Validate root path exists and is a directory.

    Raises SystemExit with proper error envelope for JSON format.
    """
    if root_path.exists() and root_path.is_dir():
        return

    if not root_path.exists():
        msg = f"Path does not exist: {root_path}"
        details = {"path": str(root_path), "reason": "not_found"}
    else:
        msg = f"Path is not a directory: {root_path}"
        details = {"path": str(root_path), "reason": "not_directory"}

    if format == "json":
        _write_output(
            format_error_envelope(
                command=command,
                root=str(root_path),
                error_code=ErrorCode.INVALID_ROOT_PATH,
                message=msg,
                details=details,
                include_timestamp=include_timestamp,
                run_id=run_id or get_current_run_id(),
                correlation_id=correlation_id,
            ),
            output=output,
        )
    elif format == "ndjson":
        write_ndjson_error(
            command_name=command,
            error=MeminitError(
                ErrorCode.INVALID_ROOT_PATH,
                msg,
                details=details,
            ),
            output=output,
            include_timestamp=include_timestamp,
            run_id=run_id or get_current_run_id(),
            root_path=root_path,
            correlation_id=correlation_id,
        )
    elif format == "md":
        _write_output(
            f"# Meminit Error\n\n- Code: INVALID_ROOT_PATH\n- Message: {msg}\n",
            output=output,
        )
    else:
        with maybe_capture(output, format):
            get_console().print(
                f"[bold red][ERROR INVALID_ROOT_PATH] {msg}[/bold red]", soft_wrap=True
            )
    raise SystemExit(exit_code_for_error(ErrorCode.INVALID_ROOT_PATH))


def validate_initialized(
    root_path: Path,
    format: str = "text",
    command: str = "unknown",
    include_timestamp: bool = False,
    run_id: Optional[str] = None,
    output: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """Validate that the repo is initialized with meminit config (F9.1).

    Per PRD F9.1, docops.config.yaml MUST exist for the repo to be considered initialized.
    The docs/ directory is a secondary indicator but not sufficient alone.

    Raises SystemExit with CONFIG_MISSING error if:
    - docops.config.yaml does not exist
    - docops.config.yaml is not a regular file (e.g., directory or symlink)
    """
    config_file = root_path / "docops.config.yaml"

    if config_file.is_file() and not config_file.is_symlink():
        import yaml as _yaml

        try:
            raw = _yaml.safe_load(config_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and raw.get("docops_version") is not None:
                return
            msg = (
                "Repository config is malformed: docops.config.yaml is missing "
                "required fields (e.g., docops_version). Run 'meminit init' to repair."
            )
            details = {
                "reason": "missing_version",
                "hint": "meminit init",
                "root": str(root_path),
                "file": "docops.config.yaml",
                "required": "valid YAML with docops_version",
            }
        except (_yaml.YAMLError, UnicodeDecodeError, OSError) as exc:
            msg = (
                f"Repository config is malformed: docops.config.yaml could not be "
                f"parsed ({exc}). Run 'meminit init' to repair."
            )
            details = {
                "reason": "unparseable",
                "hint": "meminit init",
                "root": str(root_path),
                "file": "docops.config.yaml",
                "error": str(exc),
            }
    elif config_file.exists():
        msg = (
            "Repository not initialized: docops.config.yaml exists but is not a "
            "regular file (e.g., directory or symlink). Run 'meminit init' to repair."
        )
        details = {
            "reason": "not_regular_file",
            "hint": "meminit init",
            "root": str(root_path),
            "file": "docops.config.yaml",
            "required": "regular file (not directory/symlink)",
        }
    else:
        msg = "Repository not initialized: missing docops.config.yaml. Run 'meminit init' first."
        details = {
            "reason": "missing",
            "hint": "meminit init",
            "root": str(root_path),
            "missing_file": "docops.config.yaml",
        }

    if format == "json":
        _write_output(
            format_error_envelope(
                command=command,
                root=str(root_path),
                error_code=ErrorCode.CONFIG_MISSING,
                message=msg,
                details=details,
                include_timestamp=include_timestamp,
                run_id=run_id or get_current_run_id(),
                correlation_id=correlation_id,
            ),
            output=output,
        )
    elif format == "ndjson":
        write_ndjson_error(
            command_name=command,
            error=MeminitError(
                ErrorCode.CONFIG_MISSING,
                msg,
                details=details,
            ),
            output=output,
            include_timestamp=include_timestamp,
            run_id=run_id or get_current_run_id(),
            root_path=root_path,
            correlation_id=correlation_id,
        )
    elif format == "md":
        _write_output(
            f"# Meminit Error\n\n- Code: CONFIG_MISSING\n- Message: {msg}\n",
            output=output,
        )
    else:
        with maybe_capture(output, format):
            get_console().print(
                f"[bold red][ERROR CONFIG_MISSING] {msg}[/bold red]", soft_wrap=True
            )
    raise SystemExit(exit_code_for_error(ErrorCode.CONFIG_MISSING))


def _validate_mutation_exclusivity(replace, add, remove, clear, field_name):
    from meminit.core.use_cases.state_document import _assert_single_mutation_mode

    try:
        _assert_single_mutation_mode(field_name, replace, add, remove, clear)
    except MeminitError as exc:
        flag_names = {
            "depends_on": (
                "--depends-on",
                "--add-depends-on/--remove-depends-on",
                "--clear-depends-on",
            ),
            "blocked_by": (
                "--blocked-by",
                "--add-blocked-by/--remove-blocked-by",
                "--clear-blocked-by",
            ),
        }
        active = [
            flag_names[field_name][i]
            for i, m in enumerate(
                [replace is not None, (add is not None or remove is not None), clear]
            )
            if m
        ]
        raise MeminitError(
            ErrorCode.STATE_MIXED_MUTATION_MODE,
            f"Conflicting mutation modes for {field_name}: "
            f"{' and '.join(active)} are mutually exclusive. "
            f"Use exactly one mode per field family.",
            details={"field": field_name, "conflicting_flags": active},
        ) from exc


def _normalize_mutation_arg(value):
    """Convert empty tuple/list to None for mutation arg validation."""
    if isinstance(value, (tuple, list)) and len(value) == 0:
        return None
    return value


def _state_set_validate_args(
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
):
    # Normalize empty tuples/lists from Click to None
    depends_on = _normalize_mutation_arg(depends_on)
    add_depends_on = _normalize_mutation_arg(add_depends_on)
    remove_depends_on = _normalize_mutation_arg(remove_depends_on)
    blocked_by = _normalize_mutation_arg(blocked_by)
    add_blocked_by = _normalize_mutation_arg(add_blocked_by)
    remove_blocked_by = _normalize_mutation_arg(remove_blocked_by)

    has_planning_flags = any(
        [
            priority,
            depends_on,
            add_depends_on,
            remove_depends_on,
            clear_depends_on,
            blocked_by,
            add_blocked_by,
            remove_blocked_by,
            clear_blocked_by,
            assignee is not None,
            next_action is not None,
        ]
    )
    if not clear and not impl_state and notes is None and not has_planning_flags:
        raise MeminitError(
            ErrorCode.STATE_NO_MUTATION_PROVIDED,
            "Must provide --impl-state, --notes, --clear, or a planning field flag.",
        )
    if clear and (impl_state or notes or has_planning_flags):
        raise MeminitError(
            ErrorCode.STATE_CLEAR_MUTATION_CONFLICT,
            "--clear is mutually exclusive with all other mutation flags.",
            details={"clear": True},
        )
    _validate_mutation_exclusivity(
        depends_on,
        add_depends_on,
        remove_depends_on,
        clear_depends_on,
        "depends_on",
    )
    _validate_mutation_exclusivity(
        blocked_by,
        add_blocked_by,
        remove_blocked_by,
        clear_blocked_by,
        "blocked_by",
    )


def _state_set_execute(
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
):
    from meminit.core.use_cases.state_document import StateDocumentUseCase

    use_case = StateDocumentUseCase(str(root_path), strict_config=True)
    return use_case.set_state(
        document_id,
        impl_state=impl_state,
        notes=notes,
        actor=actor,
        clear=clear,
        priority=priority,
        depends_on=list(depends_on) or None,
        add_depends_on=list(add_depends_on) or None,
        remove_depends_on=list(remove_depends_on) or None,
        clear_depends_on=clear_depends_on,
        blocked_by=list(blocked_by) or None,
        add_blocked_by=list(add_blocked_by) or None,
        remove_blocked_by=list(remove_blocked_by) or None,
        clear_blocked_by=clear_blocked_by,
        assignee=assignee,
        next_action=next_action,
    )


def _state_list_validate_filters(
    ready, no_ready, blocked, no_blocked, assignee, priority, impl_state
):
    if ready and no_ready:
        raise MeminitError(
            code=ErrorCode.STATE_INVALID_FILTER_VALUE,
            message="Cannot specify both --ready and --no-ready.",
            details={"conflicting_flags": ["--ready", "--no-ready"]},
        )
    if blocked and no_blocked:
        raise MeminitError(
            code=ErrorCode.STATE_INVALID_FILTER_VALUE,
            message="Cannot specify both --blocked and --no-blocked.",
            details={"conflicting_flags": ["--blocked", "--no-blocked"]},
        )
    if ready and blocked:
        raise MeminitError(
            code=ErrorCode.STATE_INVALID_FILTER_VALUE,
            message="Cannot specify both --ready and --blocked (an entry cannot be both ready and blocked).",
            details={"conflicting_flags": ["--ready", "--blocked"]},
        )
    ready_filter = True if ready else (False if no_ready else None)
    blocked_filter = True if blocked else (False if no_blocked else None)
    assignee_list = list(assignee) if assignee else None
    priority_list = list(priority) if priority else None
    impl_state_list = list(impl_state) if impl_state else None
    return ready_filter, blocked_filter, assignee_list, priority_list, impl_state_list


def _state_list_execute(
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
):
    from meminit.core.services.project_state import ImplState
    from meminit.core.services.repo_config import load_repo_layout
    from meminit.core.use_cases.state_document import StateDocumentUseCase

    validate_root_path(
        root_path,
        format=format,
        command="state list",
        include_timestamp=include_timestamp,
        run_id=run_id,
        output=output,
        correlation_id=correlation_id,
    )
    validate_initialized(
        root_path,
        format=format,
        command="state list",
        include_timestamp=include_timestamp,
        run_id=run_id,
        output=output,
        correlation_id=correlation_id,
    )
    use_case = StateDocumentUseCase(str(root_path), strict_config=True)
    result = use_case.list_states(
        ready=ready_filter,
        blocked=blocked_filter,
        assignee=assignee_list,
        priority=priority_list,
        impl_state=impl_state_list,
    )
    try:
        layout = load_repo_layout(root_path)
        valid_impl_states_set: set[str] = set()
        valid_doc_statuses_set: set[str] = set()
        for ns in layout.namespaces:
            valid_impl_states_set.update(ns.valid_impl_states)
            valid_doc_statuses_set.update(ns.valid_doc_statuses)
        valid_impl_states = sorted(list(valid_impl_states_set))
        valid_doc_statuses = sorted(list(valid_doc_statuses_set))
    except (MeminitError, ValueError, FileNotFoundError):
        valid_impl_states = ImplState.canonical_values()
        valid_doc_statuses = ["Draft", "In Review", "Approved", "Superseded"]
    return result, valid_impl_states, valid_doc_statuses


def _state_next_execute(root_path, assignee, priority_at_least):
    from meminit.core.use_cases.state_document import StateDocumentUseCase

    use_case = StateDocumentUseCase(str(root_path), strict_config=True)
    return use_case.next_state(assignee=assignee, priority_at_least=priority_at_least)


def _state_blockers_execute(root_path, assignee):
    from meminit.core.use_cases.state_document import StateDocumentUseCase

    use_case = StateDocumentUseCase(str(root_path), strict_config=True)
    return use_case.blockers_state(assignee=assignee)


_DRIFT_ERROR_CODE = {
    "missing": "PROTOCOL_ASSET_MISSING",
    "legacy": "PROTOCOL_ASSET_LEGACY",
    "stale": "PROTOCOL_ASSET_STALE",
    "tampered": "PROTOCOL_ASSET_TAMPERED",
    "unparseable": "PROTOCOL_ASSET_UNPARSEABLE",
}

_DRIFT_ERROR_STATES = frozenset({"tampered", "unparseable"})


def _drift_violations(assets, status_field):
    violations = []
    for a in assets:
        status = a[status_field]
        code = _DRIFT_ERROR_CODE.get(status)
        if code:
            violations.append(
                {
                    "code": code,
                    "message": f"{status}: {a['target_path']}",
                    "path": a["target_path"],
                    "severity": "error" if status in _DRIFT_ERROR_STATES else "warning",
                }
            )
    return violations
