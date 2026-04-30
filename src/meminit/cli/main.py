import contextlib
import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import click
from rich.console import Console
from rich.table import Table

from meminit.cli.shared_flags import agent_output_options, agent_repo_options
from meminit.core.domain.entities import NewDocumentParams, Severity, Violation
from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.exit_codes import (
    EX_CANTCREAT,
    EX_COMPLIANCE_FAIL,
    exit_code_for_error,
)
from meminit.core.services.observability import get_current_run_id, log_operation
from meminit.core.services.output_formatter import (
    normalize_correlation_id,
    format_envelope,
    format_error_envelope,
)
from meminit.core.services.versioning import get_cli_version
from meminit.core.services.path_utils import relative_path_string
from meminit.core.services.scan_plan import MigrationPlan
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

console = Console()


def get_console() -> Console:
    """Helper to get the rich console from context if available."""
    try:
        ctx = click.get_current_context(silent=True)
        if (
            ctx
            and hasattr(ctx, "obj")
            and isinstance(ctx.obj, dict)
            and "console" in ctx.obj
        ):
            return ctx.obj["console"]
    except Exception:
        pass
    return console


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
            else:
                _write_output(f"Error: {error_msg}\n", output)
            raise SystemExit(exit_code_for_error(ErrorCode.INVALID_FLAG_COMBINATION)) from e
    try:
        yield
    except MeminitError as e:
        if format == "json":
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
                get_console().print(
                    f"[bold red][ERROR {e.code.value}] {e.message}[/bold red]"
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
                    details={"internal_error": str(e)},
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
        elif format == "md":
            _write_output(
                f"# Error\n\n- Code: UNKNOWN_ERROR\n- Message: {safe_msg}\n",
                output,
            )
        else:
            with maybe_capture(output, format):
                get_console().print(
                    f"[bold red][ERROR UNKNOWN_ERROR] {safe_msg}[/bold red]"
                )

        # Always log the real error to stderr for operators
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


def _is_safe_path(path: Path) -> bool:
    """Basic safety check for output paths."""
    # Forbidden system paths (simplified)
    forbidden = ["/etc", "/bin", "/sbin", "/usr/bin", "/usr/sbin", "/root", "/var"]
    try:
        # Resolve to handle symlinks and relative paths
        abs_path = path.resolve()
        path_str = abs_path.as_posix()
        for f in forbidden:
            if path_str == f or path_str.startswith(f + "/"):
                return False
        # Prevent hidden files in home directory (e.g. .ssh, .bashrc)
        try:
            home = Path.home().resolve().as_posix()
            if path_str.startswith(home) and abs_path.name.startswith("."):
                # Allow .meminit specific files if any
                if not (
                    path_str == f"{home}/.meminit"
                    or path_str.startswith(f"{home}/.meminit/")
                ):
                    return False
        except (RuntimeError, OSError):
            # No home directory or cannot resolve
            pass
    except (OSError, ValueError):
        # Cannot resolve path (e.g. permission denied on parent)
        # If we can't resolve it, we err on the side of safety if it looks absolute
        if path.is_absolute():
            path_str = path.as_posix()
            for f in forbidden:
                if path_str == f or path_str.startswith(f + "/"):
                    return False
    return True


def _extract_envelope_metadata(output_str: str) -> Optional[Dict[str, Any]]:
    """Parse a CLI envelope string and extract metadata fields for error rebuilding.

    Returns None if the string is not a valid envelope.
    """
    from meminit.core.services.output_contracts import OUTPUT_SCHEMA_VERSION_V2, OUTPUT_SCHEMA_VERSION_V3

    try:
        payload = json.loads(output_str)
    except Exception:
        return None
    if (
        isinstance(payload, dict)
        and payload.get("output_schema_version") in (OUTPUT_SCHEMA_VERSION_V2, OUTPUT_SCHEMA_VERSION_V3)
        and isinstance(payload.get("command"), str)
    ):
        return payload
    return None


def _write_output(
    output_str: str,
    output: Optional[str] = None,
    append: bool = False,
    add_newline: bool = True,
) -> None:
    """Write output to stdout or to a file if requested."""
    if output:
        out_path = Path(output)
        if not _is_safe_path(out_path):
            payload = _extract_envelope_metadata(output_str)
            if payload is not None:
                click.echo(
                    format_error_envelope(
                        command=payload["command"],
                        root=payload.get("root"),
                        error_code=ErrorCode.PATH_ESCAPE,
                        message=f"Output path is considered unsafe: {output}",
                        details={"output_path": output},
                        include_timestamp="timestamp" in payload,
                        run_id=payload.get("run_id")
                        if isinstance(payload.get("run_id"), str)
                        else None,
                        correlation_id=payload.get("correlation_id")
                        if isinstance(payload.get("correlation_id"), str)
                        else None,
                    )
                )
            else:
                click.echo(
                    f"ERROR: Output path '{output}' is considered unsafe. Writing blocked.",
                    err=True,
                )
            raise SystemExit(exit_code_for_error(ErrorCode.PATH_ESCAPE))

        try:
            mode = "a" if append else "w"
            with out_path.open(mode, encoding="utf-8") as handle:
                if add_newline:
                    handle.write(output_str + "\n")
                else:
                    handle.write(output_str)
            return
        except OSError as exc:
            # Preserve machine-safe behavior for JSON output when file writes fail.
            payload = _extract_envelope_metadata(output_str)
            if payload is not None:
                click.echo(
                    format_error_envelope(
                        command=payload["command"],
                        root=payload.get("root"),
                        error_code=ErrorCode.UNKNOWN_ERROR,
                        message=f"Failed to write output file: {output}",
                        details={"output_path": output, "reason": str(exc)},
                        include_timestamp="timestamp" in payload,
                        run_id=payload.get("run_id")
                        if isinstance(payload.get("run_id"), str)
                        else None,
                        correlation_id=payload.get("correlation_id")
                        if isinstance(payload.get("correlation_id"), str)
                        else None,
                    )
                )
            else:
                # Fallback to click.echo
                click.echo(f"Error writing output file '{output}': {exc}", err=True)
            raise SystemExit(EX_CANTCREAT)
    click.echo(output_str, nl=add_newline)


@contextlib.contextmanager
def maybe_capture(output: Optional[str], format: str):
    """Capture console output if output file is specified and format is text."""
    if format == "text" and output:
        capture_obj = None
        try:
            with get_console().capture() as capture:
                capture_obj = capture
                yield
        finally:
            if capture_obj:
                captured_text = capture_obj.get()
                # Avoid clobbering a file with empty content in nested capture flows.
                if captured_text.strip():
                    _write_output(
                        captured_text,
                        output=output,
                        append=True,
                        add_newline=False,
                    )
    else:
        yield


def _md_escape(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


_MD_INLINE_SPECIAL = str.maketrans({
    "\\": "\\\\", "*": "\\*", "_": "\\_", "[": "\\[", "]": "\\]",
    "`": "\\`", "|": "\\|", "<": "&lt;", ">": "&gt;",
    "&": "&amp;", "\n": " ",
})


def _md_inline(value: object) -> str:
    text = "" if value is None else str(value)
    return text.translate(_MD_INLINE_SPECIAL)


def _md_table(headers: list[str], rows: list[list[object]]) -> str:
    head = "| " + " | ".join(_md_escape(h) for h in headers) + " |"
    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(_md_escape(c) for c in row) + " |" for row in rows]
    return "\n".join([head, sep, *body])


def _flatten_warning_groups(warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for item in warnings:
        path = item.get("path")
        for warning in item.get("warnings", []):
            entry: Dict[str, Any] = {
                "code": warning.get("code"),
                "path": path,
                "message": warning.get("message"),
            }
            if "line" in warning and warning.get("line") is not None:
                entry["line"] = warning.get("line")
            flat.append(entry)
    return flat


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
    elif format == "md":
        _write_output(
            f"# Meminit Error\n\n- Code: INVALID_ROOT_PATH\n- Message: {msg}\n",
            output=output,
        )
    else:
        with maybe_capture(output, format):
            get_console().print(f"[bold red][ERROR INVALID_ROOT_PATH] {msg}[/bold red]")
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
        msg = (
            "Repository not initialized: missing docops.config.yaml. "
            "Run 'meminit init' first."
        )
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
    elif format == "md":
        _write_output(
            f"# Meminit Error\n\n- Code: CONFIG_MISSING\n- Message: {msg}\n",
            output=output,
        )
    else:
        with maybe_capture(output, format):
            get_console().print(f"[bold red][ERROR CONFIG_MISSING] {msg}[/bold red]")
    raise SystemExit(exit_code_for_error(ErrorCode.CONFIG_MISSING))


def get_severity_value(violation: Violation) -> str:
    return (
        violation.severity.value
        if hasattr(violation.severity, "value")
        else str(violation.severity)
    )


@click.group()
@click.version_option(version=get_cli_version(), prog_name="meminit")
@click.option(
    "--no-color",
    is_flag=True,
    default=False,
    help="Disable ANSI colors in text output.",
)
@click.option(
    "--verbose", is_flag=True, default=False, help="Enable verbose debug logging."
)
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


@cli.command()
@click.argument("paths", nargs=-1, required=False)
@agent_repo_options()
@click.option(
    "--quiet", is_flag=True, default=False, help="Only show failures (text output)"
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Treat warnings as errors (e.g., outside docs_root)",
)
def check(paths, root, format, output, include_timestamp, correlation_id, quiet, strict):
    """Run compliance checks on the repository or specified PATHS.

    PATHS may be relative, absolute, or glob patterns. If omitted, all governed
    docs under the configured docs_root are checked.
    """
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "check", format, output, include_timestamp, run_id, root_path,
        correlation_id=correlation_id,
    ):
        if format == "text" and not quiet and not paths:
            with maybe_capture(output, format):
                get_console().print("[bold blue]Meminit Compliance Check[/bold blue]")

        validate_root_path(
            root_path,
            format=format,
            command="check",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )
        validate_initialized(
            root_path,
            format=format,
            command="check",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )

        use_case = CheckRepositoryUseCase(root_dir=str(root_path))

        if paths:
            with log_operation(
                operation="check_targeted",
                details={"paths": list(paths), "strict": strict},
                run_id=run_id,
            ) as _check_ctx:
                result = use_case.execute_targeted(list(paths), strict=strict)
                _check_ctx["details"]["files_checked"] = result.files_checked
                _check_ctx["details"]["files_failed"] = result.files_failed
                _check_ctx["details"]["violations_count"] = result.violations_count
                _check_ctx["details"]["warnings_count"] = result.warnings_count
        else:
            if format == "text" and not quiet:
                with maybe_capture(output, format):
                    get_console().print(f"Scanning root: {root_path}")

            with log_operation(
                operation="check_full",
                details={"root": str(root_path)},
                run_id=run_id,
            ) as _check_ctx:
                result = use_case.execute_full_summary(strict=strict)
                _check_ctx["details"]["files_checked"] = result.files_checked
                _check_ctx["details"]["files_failed"] = result.files_failed
                _check_ctx["details"]["violations_count"] = result.violations_count
                _check_ctx["details"]["warnings_count"] = result.warnings_count

        if format == "json":
            checked_paths_sorted = sorted(result.checked_paths)
            check_counters = {
                "checked_paths_count": len(checked_paths_sorted),
                "checked_paths": checked_paths_sorted,
                "files_checked": result.files_checked,
                "files_failed": result.files_failed,
                "files_outside_docs_root_count": result.files_outside_docs_root_count,
                "files_passed": result.files_passed,
                "files_with_warnings": result.files_with_warnings,
                "missing_paths_count": result.missing_paths_count,
                "schema_failures_count": result.schema_failures_count,
                "violations_count": result.violations_count,
                "warnings_count": result.warnings_count,
            }
            _write_output(
                format_envelope(
                    command="check",
                    root=str(root_path),
                    success=result.success,
                    violations=result.violations,
                    warnings=_flatten_warning_groups(result.warnings),
                    extra_top_level=check_counters,
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
            raise SystemExit(0 if result.success else EX_COMPLIANCE_FAIL)

        if format == "md":
            status = "failed" if not result.success else "success"
            rows: list[list[object]] = []
            for item in result.violations:
                path = item.get("path")
                for v in item.get("violations", []):
                    rows.append(
                        ["error", v.get("code"), path, v.get("line"), v.get("message")]
                    )
            for item in result.warnings:
                path = item.get("path")
                for w in item.get("warnings", []):
                    rows.append(
                        [
                            "warning",
                            w.get("code"),
                            path,
                            w.get("line"),
                            w.get("message"),
                        ]
                    )

            title = "# Meminit Compliance Check"
            summary = (
                f"- Status: {status}\n- Files checked: {result.files_checked}\n"
                f"- Violations: {result.violations_count}\n- Warnings: {result.warnings_count}\n\n"
            )
            table = (
                "## Findings\n\n"
                + _md_table(["Severity", "Rule", "File", "Line", "Message"], rows)
                + "\n"
            )
            _write_output(f"{title}\n\n{summary}{table}", output)
            raise SystemExit(0 if result.success else EX_COMPLIANCE_FAIL)

        with maybe_capture(output, format):
            violations_by_path = {
                item["path"]: item["violations"] for item in result.violations
            }
            warnings_by_path = {
                item["path"]: item["warnings"] for item in result.warnings
            }

            if quiet:
                for path in sorted(violations_by_path.keys()):
                    for v in violations_by_path[path]:
                        line_info = (
                            f" (line {v['line']})" if v.get("line") is not None else ""
                        )
                        get_console().print(
                            f"FAIL {path}: [{v['code']}] {v['message']}{line_info}"
                        )
                raise SystemExit(0 if result.success else EX_COMPLIANCE_FAIL)

            if paths:
                label = "file" if result.files_checked == 1 else "files"
                get_console().print(
                    f"Checking {result.files_checked} existing {label}..."
                )
                for path in result.checked_paths:
                    if path in violations_by_path:
                        get_console().print(f"FAIL {path}")
                        for v in violations_by_path[path]:
                            line_info = (
                                f" (line {v['line']})"
                                if v.get("line") is not None
                                else ""
                            )
                            get_console().print(
                                f"  - [{v['code']}] {v['message']}{line_info}"
                            )
                        continue
                    if path in warnings_by_path:
                        get_console().print(f"WARN {path}")
                        for w in warnings_by_path[path]:
                            line_info = (
                                f" (line {w['line']})"
                                if w.get("line") is not None
                                else ""
                            )
                            get_console().print(
                                f"  - [{w['code']}] {w['message']}{line_info}"
                            )
                        continue
                    get_console().print(f"OK {path}")
            else:
                table_title = (
                    "Compliance Violations"
                    if result.violations_count
                    else "Compliance Warnings"
                )
                table = Table(title=table_title)
                table.add_column("Severity")
                table.add_column("Rule", style="cyan")
                table.add_column("File")
                table.add_column("Message", overflow="fold")

                for item in result.violations:
                    for v in item.get("violations", []):
                        table.add_row(
                            "[red]error[/red]",
                            str(v.get("code")),
                            f"{item.get('path')}:{v.get('line', 0)}",
                            str(v.get("message")),
                        )
                for item in result.warnings:
                    for w in item.get("warnings", []):
                        table.add_row(
                            "[yellow]warning[/yellow]",
                            str(w.get("code")),
                            f"{item.get('path')}:{w.get('line', 0)}",
                            str(w.get("message")),
                        )
                get_console().print(table)

            if not result.success:
                get_console().print(
                    f"\n[bold red]Found {result.violations_count} violations across {result.files_checked} checked files.[/bold red]"
                )
                raise SystemExit(EX_COMPLIANCE_FAIL)
            if result.warnings_count:
                get_console().print(
                    f"\n[bold yellow]Found {result.warnings_count} warning(s).[/bold yellow]"
                )
            else:
                get_console().print(
                    "[bold green]Success! No violations found.[/bold green]"
                )
            raise SystemExit(0)


@cli.command()
@agent_repo_options()
@click.option(
    "--strict/--no-strict",
    default=False,
    help="Treat warnings as errors (exit non-zero)",
)
def doctor(root, format, output, include_timestamp, correlation_id, strict):
    """Self-check: verify meminit can operate in this repository."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "doctor", format, output, include_timestamp, run_id, root_path,
        correlation_id=correlation_id,
    ):
        validate_root_path(
            root_path,
            format=format,
            command="doctor",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )

        use_case = DoctorRepositoryUseCase(root_dir=str(root_path))
        issues = use_case.execute()

        errors = [
            i
            for i in issues
            if (i.severity.value if hasattr(i.severity, "value") else str(i.severity))
            == "error"
        ]
        warnings = [
            i
            for i in issues
            if (i.severity.value if hasattr(i.severity, "value") else str(i.severity))
            == "warning"
        ]

        status = "ok"
        if errors:
            status = "error"
        elif warnings:
            status = "warn"
        has_failure = bool(errors) or (strict and bool(warnings))
        exit_code = EX_COMPLIANCE_FAIL if has_failure else 0

        if format == "json":
            # PRD §15.1 Mapping Rule:
            promoted_warnings = warnings if strict else []
            unpromoted_warnings = [] if strict else warnings
            v2_warnings = [
                {
                    "code": v.rule,
                    "message": v.message,
                    "path": v.file or "",
                    "line": v.line,
                    "severity": "warning",
                }
                for v in unpromoted_warnings
            ]
            v2_violations = [
                {
                    "code": v.rule,
                    "message": v.message,
                    "path": v.file or "",
                    "line": v.line,
                    "severity": "error",
                }
                for v in errors
            ] + [
                {
                    "code": v.rule,
                    "message": v.message,
                    "path": v.file or "",
                    "line": v.line,
                    "severity": "error",
                }
                for v in promoted_warnings
            ]
            # Include original issues in data for backward compatibility (PRD §15.1)
            issues_payload = [
                {
                    "severity": i.severity.value
                    if hasattr(i.severity, "value")
                    else str(i.severity),
                    "rule": i.rule,
                    "file": i.file,
                    "line": i.line,
                    "message": i.message,
                }
                for i in issues
            ]
            _write_output(
                format_envelope(
                    command="doctor",
                    root=str(root_path),
                    success=not has_failure,
                    data={"strict": strict, "status": status, "issues": issues_payload},
                    warnings=v2_warnings,
                    violations=v2_violations,
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
            raise SystemExit(exit_code)

        if format == "md":
            rows = [
                [
                    v.severity.value
                    if hasattr(v.severity, "value")
                    else str(v.severity),
                    v.rule,
                    v.file,
                    v.line,
                    v.message,
                ]
                for v in issues
            ]
            _write_output(
                "# Meminit Doctor\n\n"
                f"- Status: {status}\n"
                f"- Strict: {strict}\n"
                f"- Errors: {len(errors)}\n"
                f"- Warnings: {len(warnings)}\n\n"
                "## Issues\n\n"
                + (
                    _md_table(["Severity", "Rule", "File", "Line", "Message"], rows)
                    if rows
                    else "_None_\n"
                ),
                output,
            )
            raise SystemExit(exit_code)

        with maybe_capture(output, format):
            get_console().print("[bold blue]Meminit Doctor[/bold blue]")
            get_console().print(f"Root: {root_path}")

            if not issues:
                get_console().print(
                    "[bold green]OK: meminit is ready to run here.[/bold green]"
                )
                return

            table = Table(title="Doctor Findings")
            table.add_column("Severity")
            table.add_column("Rule", style="cyan")
            table.add_column("File")
            table.add_column("Message", overflow="fold")

            for v in issues:
                severity_val = (
                    v.severity.value
                    if hasattr(v.severity, "value")
                    else str(v.severity)
                )
                severity_color = "red" if severity_val == "error" else "yellow"
                table.add_row(
                    f"[{severity_color}]{severity_val}[/{severity_color}]",
                    v.rule,
                    v.file,
                    v.message,
                )

            get_console().print(table)
            if errors:
                get_console().print(
                    f"\n[bold red]{len(errors)} error(s), {len(warnings)} warning(s).[/bold red]"
                )
            else:
                get_console().print(
                    f"\n[bold yellow]{len(warnings)} warning(s).[/bold yellow]"
                )
            raise SystemExit(exit_code)


@cli.command()
@agent_repo_options()
@click.option(
    "--plan",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Apply a deterministic migration plan",
)
@click.option(
    "--dry-run/--no-dry-run", default=True, help="Simulate fixes without changing files"
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
        "fix", format, output, include_timestamp, run_id, root_path,
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
                plan_data = (
                    data.get("data", {}).get("plan") or data
                )  # Handle envelope or direct
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
                    get_console().print(
                        f"[bold red]Failed to load plan: {e}[/bold red]"
                    )
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
            # Print fixed actions
            if report.fixed_violations:
                table = Table(
                    title="Actions Taken" if not dry_run else "Proposed Actions"
                )
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

            # Print remaining
            if report.remaining_violations:
                get_console().print(
                    f"\n[bold red]Remaining Violations ({len(report.remaining_violations)}):[/bold red]"
                )
                # Simplified list, suggest running check for details
                for v in report.remaining_violations[:5]:
                    get_console().print(f"- {v.file}: {v.message}")
                if len(report.remaining_violations) > 5:
                    get_console().print(
                        f"... and {len(report.remaining_violations) - 5} more."
                    )
                get_console().print(
                    "\nRun [bold]meminit check[/bold] for full details."
                )
                raise SystemExit(exit_code)
            else:
                get_console().print("\n[bold green]All clear![/bold green]")
                raise SystemExit(exit_code)


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
        "scan", format, output, include_timestamp, run_id, root_path,
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

        use_case = ScanRepositoryUseCase(root_dir=str(root_path))
        report = use_case.execute(generate_plan=bool(plan))
        scan_data = report.as_dict()

        if plan and report.plan:
            plan_path = Path(plan)
            if not _is_safe_path(plan_path):
                raise MeminitError(
                    ErrorCode.PATH_ESCAPE,
                    f"Plan path is considered unsafe: {plan}",
                    details={"plan_path": plan},
                )
            try:
                plan_json = format_envelope(
                    command="scan",
                    root=str(root_path),
                    success=True,
                    data={"plan": report.plan.as_dict()},
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                )
                with open(plan_path, "w", encoding="utf-8") as f:
                    f.write(plan_json + "\n")
                if format != "json":
                    get_console().print(
                        f"[bold green]Saved migration plan to {plan}[/bold green]"
                    )
            except Exception as e:
                if format == "json":
                    _write_output(
                        format_error_envelope(
                            command="scan",
                            root=str(root_path),
                            error_code=ErrorCode.UNKNOWN_ERROR,
                            message=f"Failed to save plan: {e}",
                            run_id=run_id,
                            include_timestamp=include_timestamp,
                            correlation_id=correlation_id,
                        ),
                        output,
                    )
                    raise SystemExit(1) from e
                else:
                    get_console().print(
                        f"[bold red]Failed to save plan: {e}[/bold red]"
                    )
                    raise SystemExit(1) from e
        elif plan:
            # Plan was requested but no actions were generated
            if format != "json":
                get_console().print(
                    "[yellow]No plan actions generated — repository may already be compliant.[/yellow]"
                )
            # Write an empty plan envelope so downstream tooling gets a stable artifact
            try:
                from meminit.core.services.scan_plan import MigrationPlan

                plan_path = Path(plan)
                if not _is_safe_path(plan_path):
                    pass  # Best-effort, skip file write for unsafe path
                else:
                    empty_plan = MigrationPlan(
                        plan_version="1.0",
                        generated_at="1970-01-01T00:00:00Z",
                        config_fingerprint="",
                        actions=[],
                    )
                    empty_plan_json = format_envelope(
                        command="scan",
                        root=str(root_path),
                        success=True,
                        data={"plan": empty_plan.as_dict()},
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    )
                    with open(plan_path, "w", encoding="utf-8") as f:
                        f.write(empty_plan_json + "\n")
                    if format != "json":
                        get_console().print(f"[dim]Saved empty plan to {plan}[/dim]")
            except Exception:
                pass  # Best-effort write, don't fail on empty plan

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
            lines: list[str] = [
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
                                "Governed .md",
                            ],
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
                        _md_table(
                            ["Parent", "Parent Root", "Child", "Child Root"], rows
                        ),
                        "",
                    ]
                )
            if report.suggested_type_directories:
                rows = [
                    [k, v] for k, v in sorted(report.suggested_type_directories.items())
                ]
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
                    [k, ", ".join(sorted(v))]
                    for k, v in sorted(report.ambiguous_types.items())
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
            _write_output("\n".join(lines), output=output)
            return

        with maybe_capture(output, format):
            get_console().print("[bold blue]Meminit Scan[/bold blue]")
            get_console().print(f"Root: {root_path}")
            get_console().print(f"Docs root: {report.docs_root or 'Not found'}")
            get_console().print(f"Markdown files: {report.markdown_count}")
            if getattr(report, "governed_markdown_count", None) is not None:
                get_console().print(
                    f"Governed markdown (all namespaces): {getattr(report, 'governed_markdown_count', 0)}"
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
                table = Table(
                    title="Ambiguous type_directories (manual decision required)"
                )
                table.add_column("Type")
                table.add_column("Candidates")
                for k, v in sorted(report.ambiguous_types.items()):
                    table.add_row(k, ", ".join(sorted(v)))
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


@cli.command("install-precommit")
@agent_repo_options()
def install_precommit(root, format, output, include_timestamp, correlation_id):
    """Install a pre-commit hook to enforce meminit check."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "install-precommit", format, output, include_timestamp, run_id, root_path,
        correlation_id=correlation_id,
    ):
        validate_root_path(
            root_path,
            format=format,
            command="install-precommit",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )

        use_case = InstallPrecommitUseCase(root_dir=str(root_path))
        result = use_case.execute()

        if format == "json":
            _write_output(
                format_envelope(
                    command="install-precommit",
                    root=str(root_path),
                    success=True,
                    data={
                        "installed": result.status in ("created", "updated"),
                        "hook_path": str(result.config_path),
                        "already_present": result.status == "already_installed",
                    },
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
            return

        if format == "md":
            _write_output(
                "# Meminit Install Precommit\n\n"
                f"- Status: {'ok' if result.status in ('created', 'updated') else 'noop'}\n"
                f"- Installed: `{result.status in ('created', 'updated')}`\n"
                f"- Already present: `{result.status == 'already_installed'}`\n"
                f"- Hook path: `{result.config_path}`\n",
                output,
            )
            return

        with maybe_capture(output, format):
            if result.status == "already_installed":
                get_console().print(
                    "[yellow]meminit pre-commit hook already installed.[/yellow]"
                )
                return
            if result.status == "created":
                get_console().print(
                    f"[bold green]Created {result.config_path} with meminit hook.[/bold green]"
                )
                return
            get_console().print(
                f"[bold green]Updated {result.config_path} with meminit hook.[/bold green]"
            )


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
):
    """Build or update the repository index artifact."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "index", format, output, include_timestamp, run_id, root_path,
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

        use_case = IndexRepositoryUseCase(
            root_dir=str(root_path),
            output_catalog=output_catalog,
            catalog_name=catalog_name,
            output_kanban=output_kanban,
            status_filter=status_filter,
            impl_state_filter=impl_state_filter,
        )
        try:
            report = use_case.execute()
        except MeminitError as e:
            # Only intercept graph fatal diagnostics (details.errors present).
            # Re-raise all other MeminitErrors so command_output_handler
            # formats them consistently for text/md/json modes.
            is_graph_fatal = isinstance(e.details, dict) and "errors" in e.details
            if is_graph_fatal:
                violations = e.details["errors"]
                if format == "json":
                    _write_output(
                        format_envelope(
                            command="index",
                            root=str(root_path),
                            success=False,
                            violations=violations,
                            error={"code": e.code.value, "message": e.message, "details": e.details},
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
                        ["ERROR", str(v.get("code")), str(v.get("path")), str(v.get("message"))]
                        for v in violations
                    ]
                    lines.append(_md_table(["Severity", "Code", "Path", "Message"], rows))
                    _write_output("\n".join(lines), output)
                else:
                    with maybe_capture(output, format):
                        for v in violations:
                            get_console().print(
                                f"[bold red][ERROR {v.get('code')}] {v.get('message')}[/bold red]"
                            )
                raise SystemExit(exit_code_for_error(e.code)) from e
            raise

        warnings_list = getattr(report, "warnings", [])
        has_error = any(
            w.get("severity") == Severity.ERROR.value for w in warnings_list
        )
        status = "error" if has_error else ("warn" if warnings_list else "ok")

        # Filter edges to only include those whose endpoints are in the visible
        # node set — but only when the user requested node filtering.  On the
        # unfiltered path we must preserve dangling edges (e.g. related_ids
        # pointing to a non-existent document) so agents see the full graph.
        has_filter = status_filter is not None or impl_state_filter is not None
        if has_filter:
            visible_ids = {n["document_id"] for n in report.documents}
            display_edges = [
                e for e in report.edges
                if e.get("source") in visible_ids and e.get("target") in visible_ids
            ]
        else:
            display_edges = report.edges

        data: Dict[str, Any] = {
            "index_path": relative_path_string(report.index_path, root_path),
            "node_count": report.document_count,
            "edge_count": len(display_edges),
            "nodes": report.documents,
            "edges": display_edges,
            "filtered": has_filter,
        }
        if report.catalog_path:
            data["catalog_path"] = relative_path_string(report.catalog_path, root_path)
        if report.kanban_path:
            data["kanban_path"] = relative_path_string(report.kanban_path, root_path)

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
                lines.append(
                    _md_table(["Severity", "Code", "Path", "Line", "Message"], rows)
                )
            advice_list = getattr(report, "advice", [])
            if advice_list:
                lines.extend(["", "## Advice", ""])
                advice_rows = [
                    ["INFO", str(a.get("code")), str(a.get("message"))]
                    for a in advice_list
                ]
                lines.append(_md_table(["Severity", "Code", "Message"], advice_rows))
            lines.append("")
            _write_output("\n".join(lines), output)
            if has_error:
                raise SystemExit(1)
            return

        with maybe_capture(output, format):
            style = "red" if has_error else ("yellow" if warnings_list else "green")
            get_console().print(
                f"[bold {style}]Index written:[/bold {style}] {report.index_path} "
                f"({report.document_count} nodes, {len(display_edges)} edges)"
            )
            for warning in warnings_list:
                get_console().print(
                    f"  - [{warning.get('severity')}] {warning.get('code')}: {warning.get('message')}"
                )
            for advice_item in getattr(report, "advice", []):
                get_console().print(
                    f"  - [dim]advice[/dim] {advice_item.get('code')}: {advice_item.get('message')}"
                )
            if report.catalog_path:
                get_console().print(f"[green]Catalog:[/green] {report.catalog_path}")
            if report.kanban_path:
                get_console().print(f"[green]Kanban:[/green] {report.kanban_path}")

        # Exit with error if any validation issues occurred (applies to all formats)
        if has_error:
            raise SystemExit(1)


@cli.command()
@click.argument("document_id")
@agent_repo_options()
def resolve(document_id, root, format, output, include_timestamp, correlation_id):
    """Resolve a document_id to a path using the index."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "resolve", format, output, include_timestamp, run_id, root_path,
        correlation_id=correlation_id,
    ):
        validate_root_path(
            root_path,
            format=format,
            command="resolve",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )

        use_case = ResolveDocumentUseCase(root_dir=str(root_path))
        result = use_case.execute(document_id)

        if not result.path:
            raise MeminitError(ErrorCode.FILE_NOT_FOUND, f"Not found: {document_id}")

        if format == "json":
            _write_output(
                format_envelope(
                    command="resolve",
                    root=str(root_path),
                    success=True,
                    data={
                        "document_id": document_id,
                        "path": result.path.replace("\\", "/") if result.path else None,
                    },
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
            return

        if format == "md":
            _write_output(
                "# Meminit Resolve\n\n"
                f"- Document ID: `{document_id}`\n"
                f"- Path: `{result.path}`\n",
                output,
            )
            return

        with maybe_capture(output, format):
            get_console().print(result.path)


@cli.command()
@click.argument("path")
@agent_repo_options()
def identify(path, root, format, output, include_timestamp, correlation_id):
    """Identify a document_id for a given path using the index."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "identify", format, output, include_timestamp, run_id, root_path,
        correlation_id=correlation_id,
    ):
        validate_root_path(
            root_path,
            format=format,
            command="identify",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )

        use_case = IdentifyDocumentUseCase(root_dir=str(root_path))
        result = use_case.execute(path)

        if not result.document_id:
            raise MeminitError(ErrorCode.FILE_NOT_FOUND, f"Not governed: {result.path}")

        if format == "json":
            _write_output(
                format_envelope(
                    command="identify",
                    root=str(root_path),
                    success=True,
                    data={
                        "document_id": result.document_id,
                        "path": result.path.replace("\\", "/") if result.path else None,
                    },
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
            return

        if format == "md":
            _write_output(
                "# Meminit Identify\n\n"
                f"- Path: `{result.path}`\n"
                f"- Document ID: `{result.document_id}`\n",
                output,
            )
            return

        with maybe_capture(output, format):
            get_console().print(result.document_id)


@cli.command()
@click.argument("document_id")
@agent_repo_options()
def link(document_id, root, format, output, include_timestamp, correlation_id):
    """Print a Markdown link for a document_id using the index."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "link", format, output, include_timestamp, run_id, root_path,
        correlation_id=correlation_id,
    ):
        validate_root_path(
            root_path,
            format=format,
            command="link",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )

        use_case = ResolveDocumentUseCase(root_dir=str(root_path))
        result = use_case.execute(document_id)

        if not result.path:
            raise MeminitError(ErrorCode.FILE_NOT_FOUND, f"Not found: {document_id}")

        if format == "json":
            _write_output(
                format_envelope(
                    command="link",
                    root=str(root_path),
                    success=True,
                    data={
                        "document_id": document_id,
                        "link": f"[{document_id}]({result.path.replace('\\', '/')})"
                        if result.path
                        else None,
                    },
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
            return

        if format == "md":
            _write_output(
                "# Meminit Link\n\n"
                f"- Document ID: `{document_id}`\n"
                f"- Link: [{document_id}]({result.path})\n",
                output,
            )
            return

        with maybe_capture(output, format):
            get_console().print(f"[{document_id}]({result.path})")


@cli.command("migrate-ids")
@agent_repo_options()
@click.option(
    "--dry-run/--no-dry-run", default=True, help="Preview changes without writing files"
)
@click.option(
    "--rewrite-references/--no-rewrite-references",
    default=False,
    help="Rewrite old IDs in document bodies",
)
def migrate_ids(root, dry_run, rewrite_references, format, output, include_timestamp, correlation_id):
    """Migrate legacy document_id values into REPO-TYPE-SEQ format."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "migrate-ids", format, output, include_timestamp, run_id, root_path,
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
            dry_run=dry_run, rewrite_references=rewrite_references
        )

        if format == "json":
            _write_output(
                format_envelope(
                    command="migrate-ids",
                    root=str(root_path),
                    success=True,
                    data={"report": report.as_dict()},
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
                    _md_table(
                        ["File", "Type", "Old ID", "New ID", "Refs Rewritten"], rows
                    )
                    if rows
                    else "_None_\n"
                ),
                output,
            )
            return

        with maybe_capture(output, format):
            action_count = len(report.actions)
            get_console().print("[bold blue]Meminit ID Migration[/bold blue]")
            get_console().print(f"Root: {root_path}")
            get_console().print(f"Mode: {'DRY RUN' if dry_run else 'APPLY'}")
            get_console().print(f"Actions: {action_count}")
            if report.skipped_files:
                get_console().print(f"Skipped: {len(report.skipped_files)}")


@cli.command("migrate-templates")
@agent_repo_options()
@click.option(
    "--dry-run/--no-dry-run", default=True, help="Preview changes without writing files"
)
@click.option(
    "--backup/--no-backup", default=True, help="Create backup before modifying files"
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
def migrate_templates(
    root,
    dry_run,
    backup,
    legacy_type_dirs,
    legacy_templates,
    placeholder_syntax,
    rename_files,
    format,
    output,
    include_timestamp,
    correlation_id,
):
    """Migrate legacy template configs and placeholders to Templates v2 format."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "migrate-templates", format, output, include_timestamp, run_id, root_path,
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
                        "message": report.warnings[0]
                        if report.warnings
                        else "Template migration failed.",
                        "details": payload_data,
                    },
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                )
            _write_output(
                payload,
                output,
            )
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
                        f"- Replace {action.placeholder_from} with {action.placeholder_to} in {action.file} ({action.count} occurrences)"
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
            get_console().print(
                f"Config entries migrated: {report.config_entries_migrated}"
            )
            get_console().print(f"Template files found: {report.template_files_found}")
            get_console().print(
                f"Template files renamed: {report.template_files_renamed}"
            )
            get_console().print(
                f"Placeholder replacements: {report.placeholder_replacements}"
            )
            if report.warnings:
                get_console().print("\nWarnings:")
                for warning in report.warnings:
                    get_console().print(f"  - {warning}")
            if report.backup_path and not dry_run:
                get_console().print(f"\nBackup: {report.backup_path}")

        if not report.success:
            raise SystemExit(1)


@cli.command()
@agent_repo_options()
def init(root, format, output, include_timestamp, correlation_id):
    """Initialize a new DocOps repository structure."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "init", format, output, include_timestamp, run_id, root_path,
        correlation_id=correlation_id,
    ):
        use_case = InitRepositoryUseCase(str(root_path))
        report = use_case.execute()

        if format == "json":
            _write_output(
                format_envelope(
                    command="init",
                    root=str(root_path),
                    success=True,
                    data={
                        "created_paths": report.created_paths,
                        "skipped_paths": report.skipped_paths,
                    },
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
            return

        if format == "md":
            created = report.created_paths
            skipped = report.skipped_paths
            lines = [
                "# Meminit Init",
                "",
                "- Status: ok",
                f"- Created: {len(created)}",
                f"- Skipped: {len(skipped)}",
                "",
            ]
            if created:
                lines.append("## Created Paths\n")
                lines.extend([f"- `{p}`" for p in created])
                lines.append("")
            if skipped:
                lines.append("## Skipped Paths\n")
                lines.extend([f"- `{p}`" for p in skipped])
                lines.append("")
            _write_output("\n".join(lines), output)
            return

        with maybe_capture(output, format):
            get_console().print(
                f"[bold green]Initialized DocOps repository at {root}[/bold green]"
            )
            get_console().print("- Created directory structure (docs/)")
            get_console().print("- Created docops.config.yaml")
            get_console().print("- Created AGENTS.md")


@cli.command(name="new")
@click.argument("doc_type", required=False, shell_complete=complete_document_types)
@click.argument("title", required=False)
@agent_repo_options()
@click.option(
    "--namespace", default=None, help="Namespace to create the doc in (monorepo mode)"
)
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
@click.option(
    "--list-types", is_flag=True, default=False, help="List valid document types"
)
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
        "new", format, output, include_timestamp, run_id, root_path,
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
                        get_console().print(
                            f"  {item['type']:10} → {item['directory']}"
                        )
            return

        if interactive:
            validate_root_path(root_path, format=format, command="new", output=output, include_timestamp=include_timestamp, run_id=run_id, correlation_id=correlation_id)
            use_case = NewDocumentUseCase(str(root_path))
            valid_types = use_case.get_valid_types(namespace)
            if not doc_type:
                doc_type = click.prompt("Document type", type=click.Choice(valid_types))
            if not title:
                title = click.prompt("Document title")
            if not owner:
                owner = click.prompt(
                    "Owner (optional)", default="__TBD__", show_default=True
                )
            if not area:
                area = click.prompt("Area (optional)", default="", show_default=False)
            if not description:
                description = click.prompt(
                    "Description (optional)", default="", show_default=False
                )

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
            response_data = {
                "path": result.path.relative_to(root_path).as_posix()
                if result.path
                else None,
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
            rel_path = (
                result.path.relative_to(root_path).as_posix() if result.path else None
            )
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
@click.option(
    "--namespace", default=None, help="Namespace to create the ADR in (monorepo mode)"
)
def adr_new(title, root, format, output, include_timestamp, correlation_id, namespace):
    """Create a new ADR (alias for 'meminit new ADR')."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "adr new", format, output, include_timestamp, run_id, root_path,
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

        rel_path = (
            result.path.relative_to(root_path).as_posix() if result.path else None
        )
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
                get_console().print(
                    f"[bold green]Created ADR: {result.path}[/bold green]"
                )


@cli.command()
@agent_output_options()
def capabilities(format, output, include_timestamp, correlation_id):
    """Show CLI capabilities and feature descriptor."""
    run_id = get_current_run_id()

    with command_output_handler(
        "capabilities", format, output, include_timestamp, run_id,
        correlation_id=correlation_id,
    ):
        from meminit.core.use_cases.capabilities import CapabilitiesUseCase

        use_case = CapabilitiesUseCase()
        caps = use_case.execute()

        if format == "json":
            _write_output(
                format_envelope(
                    command="capabilities",
                    success=True,
                    data=caps,
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
            return

        if format == "md":
            lines = [
                "# Meminit Capabilities",
                "",
                f"**Version:** {caps['cli_version']}",
                f"**Capabilities:** {caps['capabilities_version']}",
                f"**Schema:** {caps['output_schema_version']}",
                "",
                "## Features",
                "",
            ]
            for feat, enabled in sorted(caps["features"].items()):
                status = "yes" if enabled else "no"
                lines.append(f"- `{feat}`: {status}")
            lines.append("")
            lines.append("## Commands")
            lines.append("")
            lines.append("| Name | Agent | JSON | Correlation ID |")
            lines.append("|------|-------|-----|----------------|")
            for cmd in caps["commands"]:
                af = "yes" if cmd["agent_facing"] else "no"
                sj = "yes" if cmd["supports_json"] else "no"
                sc = "yes" if cmd["supports_correlation_id"] else "no"
                lines.append(f"| {cmd['name']} | {af} | {sj} | {sc} |")
            _write_output("\n".join(lines) + "\n", output)
            return

        with maybe_capture(output, format):
            get_console().print(
                f"[bold]meminit[/bold] v{caps['cli_version']} "
                f"(capabilities {caps['capabilities_version']}, "
                f"schema {caps['output_schema_version']})"
            )
            table = Table(title="Commands")
            table.add_column("Name", style="cyan")
            table.add_column("Agent")
            table.add_column("JSON")
            table.add_column("Corr. ID")
            for cmd in caps["commands"]:
                af = "[green]yes[/green]" if cmd["agent_facing"] else "no"
                sj = "[green]yes[/green]" if cmd["supports_json"] else "no"
                sc = "[green]yes[/green]" if cmd["supports_correlation_id"] else "no"
                table.add_row(cmd["name"], af, sj, sc)
            get_console().print(table)

            feat_table = Table(title="Features")
            feat_table.add_column("Feature", style="cyan")
            feat_table.add_column("Available")
            for feat, enabled in sorted(caps["features"].items()):
                status = "[green]yes[/green]" if enabled else "no"
                feat_table.add_row(feat, status)
            get_console().print(feat_table)


@cli.command()
@agent_output_options()
@click.argument("error_code", required=False)
@click.option("--list", "list_codes", is_flag=True, default=False,
              help="List all known error codes.")
def explain(error_code, list_codes, format, output, include_timestamp, correlation_id):
    """Explain a Meminit error code in detail."""
    run_id = get_current_run_id()

    with command_output_handler(
        "explain", format, output, include_timestamp, run_id,
        correlation_id=correlation_id,
    ):
        from meminit.core.use_cases.explain_error import ExplainErrorUseCase

        use_case = ExplainErrorUseCase()

        if list_codes:
            codes = use_case.list_codes()
            if format == "json":
                _write_output(
                    format_envelope(
                        command="explain",
                        success=True,
                        data={"error_codes": codes},
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
                return

            if format == "md":
                lines = ["# Meminit Error Codes", ""]
                lines.append("| Code | Category | Summary |")
                lines.append("|------|----------|---------|")
                for entry in codes:
                    lines.append(
                        f"| `{entry['code']}` | {entry['category']} "
                        f"| {entry['summary']} |"
                    )
                _write_output("\n".join(lines) + "\n", output)
                return

            with maybe_capture(output, format):
                table = Table(title="Error Codes")
                table.add_column("Code", style="cyan")
                table.add_column("Category")
                table.add_column("Summary")
                for entry in codes:
                    table.add_row(entry["code"], entry["category"], entry["summary"])
                get_console().print(table)
            return

        if not error_code:
            raise MeminitError(
                ErrorCode.INVALID_FLAG_COMBINATION,
                "Provide an error code argument or use --list.",
            )

        explanation = use_case.explain(error_code)
        if explanation is None:
            if format == "json":
                _write_output(
                    format_envelope(
                        command="explain",
                        success=False,
                        data={"requested_code": error_code},
                        error={
                            "code": ErrorCode.UNKNOWN_ERROR_CODE.value,
                            "message": f"Unknown error code: {error_code}",
                        },
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
            elif format == "md":
                _write_output(
                    f"# Error\n\n- Code: UNKNOWN_ERROR_CODE\n"
                    f"- Message: Unknown error code: {error_code}\n",
                    output,
                )
            else:
                with maybe_capture(output, format):
                    get_console().print(
                        f"[bold red]Unknown error code: {error_code}[/bold red]"
                    )
            raise SystemExit(exit_code_for_error(ErrorCode.UNKNOWN_ERROR_CODE))

        if format == "json":
            _write_output(
                format_envelope(
                    command="explain",
                    success=True,
                    data=explanation,
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
            return

        if format == "md":
            lines = [
                f"# {explanation['code']}",
                "",
                f"**Category:** {explanation['category']}",
                f"**Summary:** {explanation['summary']}",
                "",
                "## Cause",
                "",
                explanation["cause"],
                "",
                "## Remediation",
                "",
                f"**Action:** {explanation['remediation']['action']}",
                f"**Type:** {explanation['remediation']['resolution_type']}",
                f"**Automatable:** {'yes' if explanation['remediation']['automatable'] else 'no'}",
            ]
            cmds = explanation["remediation"].get("relevant_commands", [])
            if cmds:
                lines.append(f"**Commands:** {', '.join(f'`meminit {c}`' for c in cmds)}")
            if explanation.get("spec_reference"):
                lines.append(f"**Reference:** {explanation['spec_reference']}")
            _write_output("\n".join(lines) + "\n", output)
            return

        with maybe_capture(output, format):
            e = explanation
            get_console().print(f"[bold cyan]{e['code']}[/bold cyan] ({e['category']})")
            get_console().print(f"  {e['summary']}")
            get_console().print()
            get_console().print("[bold]Cause:[/bold]")
            get_console().print(f"  {e['cause']}")
            get_console().print()
            get_console().print("[bold]Remediation:[/bold]")
            r = e["remediation"]
            get_console().print(f"  {r['action']}")
            get_console().print(
                f"  Type: {r['resolution_type']} | "
                f"Automatable: {'yes' if r['automatable'] else 'no'}"
            )
            if r.get("relevant_commands"):
                get_console().print(
                    f"  Commands: {', '.join(f'meminit {c}' for c in r['relevant_commands'])}"
                )


@cli.command()
@agent_repo_options()
@click.option(
    "--deep",
    is_flag=True,
    default=False,
    help="Include per-namespace document counts (10s budget)",
)
def context(root, deep, format, output, include_timestamp, correlation_id):
    """Emit repository configuration context for agent bootstrap (FR-6)."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "context", format, output, include_timestamp, run_id, root_path,
        correlation_id=correlation_id,
    ):
        validate_root_path(
            root_path,
            format=format,
            command="context",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )
        validate_initialized(
            root_path,
            format=format,
            command="context",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
            correlation_id=correlation_id,
        )

        use_case = ContextRepositoryUseCase(root_dir=root_path)
        result = use_case.execute(deep=deep)

        if format == "json":
            _write_output(
                format_envelope(
                    command="context",
                    root=str(root_path),
                    success=True,
                    data=result.data,
                    warnings=result.warnings,
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
            return

        if format == "md":
            lines = [
                "# Meminit Context\n",
                f"- Root: `{root_path}`",
                f"- Project: `{result.data.get('project_name', 'N/A')}`",
                f"- Config: `{result.data.get('config_path', 'N/A')}`",
                "",
            ]
            if result.warnings:
                lines.append("## Warnings\n")
                for warning in result.warnings:
                    code = warning.get("code", "WARNING")
                    message = _md_escape(warning.get("message", ""))
                    lines.append(f"- [{code}] {message}")
                lines.append("")
            _write_output("\n".join(lines), output)
            return

        with maybe_capture(output, format):
            get_console().print("[bold blue]Meminit Context[/bold blue]")
            get_console().print(f"Root: {root_path}")
            get_console().print(f"Project: {result.data.get('project_name', 'N/A')}")
            if result.warnings:
                get_console().print("Warnings:")
                for warning in result.warnings:
                    get_console().print(
                        f"  - {warning.get('code')}: {warning.get('message')}"
                    )


@cli.group()
def org():
    """Org profiles (XDG install + vendoring into repos)."""
    pass


@org.command("install")
@click.option("--profile", default="default", help="Org profile name to install")
@click.option(
    "--dry-run/--no-dry-run", default=True, help="Preview without writing to XDG paths"
)
@click.option(
    "--force/--no-force", default=False, help="Overwrite an existing installed profile"
)
@agent_output_options()
def org_install(profile, dry_run, force, format, output, include_timestamp, correlation_id):
    """Install the packaged org profile into XDG user data directories."""
    run_id = get_current_run_id()
    with command_output_handler(
        "org install", format, output, include_timestamp, run_id,
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
@click.option(
    "--dry-run/--no-dry-run", default=True, help="Preview without writing files"
)
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
    root, profile, dry_run, force, include_org_docs, format, output, include_timestamp, correlation_id
):
    """Vendor (copy + pin) org standards into a repo to prevent unintentional drift."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "org vendor", format, output, include_timestamp, run_id, root_path,
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
        "org status", format, output, include_timestamp, run_id, root_path,
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


def _validate_mutation_exclusivity(
    replace, add, remove, clear, field_name
):
    from meminit.core.use_cases.state_document import _assert_single_mutation_mode

    try:
        _assert_single_mutation_mode(field_name, replace, add, remove, clear)
    except MeminitError as exc:
        flag_names = {
            "depends_on": ("--depends-on", "--add-depends-on/--remove-depends-on", "--clear-depends-on"),
            "blocked_by": ("--blocked-by", "--add-blocked-by/--remove-blocked-by", "--clear-blocked-by"),
        }
        active = [flag_names[field_name][i] for i, m in enumerate(
            [replace is not None, (add is not None or remove is not None), clear]
        ) if m]
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
    impl_state, notes, clear, priority,
    depends_on, add_depends_on, remove_depends_on, clear_depends_on,
    blocked_by, add_blocked_by, remove_blocked_by, clear_blocked_by,
    assignee, next_action,
):
    # Normalize empty tuples/lists from Click to None
    depends_on = _normalize_mutation_arg(depends_on)
    add_depends_on = _normalize_mutation_arg(add_depends_on)
    remove_depends_on = _normalize_mutation_arg(remove_depends_on)
    blocked_by = _normalize_mutation_arg(blocked_by)
    add_blocked_by = _normalize_mutation_arg(add_blocked_by)
    remove_blocked_by = _normalize_mutation_arg(remove_blocked_by)

    has_planning_flags = any([
        priority, depends_on, add_depends_on, remove_depends_on,
        clear_depends_on, blocked_by, add_blocked_by, remove_blocked_by,
        clear_blocked_by, assignee is not None, next_action is not None,
    ])
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
        depends_on, add_depends_on, remove_depends_on, clear_depends_on,
        "depends_on",
    )
    _validate_mutation_exclusivity(
        blocked_by, add_blocked_by, remove_blocked_by, clear_blocked_by,
        "blocked_by",
    )


def _state_set_execute(
    root_path, document_id, impl_state, notes, actor, clear, priority,
    depends_on, add_depends_on, remove_depends_on, clear_depends_on,
    blocked_by, add_blocked_by, remove_blocked_by, clear_blocked_by,
    assignee, next_action,
):
    from meminit.core.use_cases.state_document import StateDocumentUseCase

    use_case = StateDocumentUseCase(str(root_path))
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


def _render_state_set_json(
    result, root_path, include_timestamp, run_id, correlation_id, output,
):
    data: dict = {"action": result.action, "document_id": result.document_id}
    if result.entry:
        data.update(result.entry)
    _write_output(
        format_envelope(
            command="state set",
            root=str(root_path),
            success=True,
            data=data,
            warnings=result.warnings,
            include_timestamp=include_timestamp,
            run_id=run_id,
            correlation_id=correlation_id,
        ),
        output,
    )


def _render_state_set_text(result, format, output):
    if format == "md":
        if result.action == "clear":
            lines = (
                f"# Meminit State Set\n\n"
                f"- Document ID: `{result.document_id}`\n"
                f"- Action: Cleared\n"
            )
        else:
            lines = (
                f"# Meminit State Set\n\n"
                f"- Document ID: `{result.document_id}`\n"
                f"- Impl State: {_md_inline(result.entry.get('impl_state', ''))}\n"
                f"- Updated By: {_md_inline(result.entry.get('updated_by', ''))}\n"
            )
            if result.entry.get("priority"):
                lines += f"- Priority: {_md_inline(result.entry.get('priority'))}\n"
            if result.entry.get("assignee"):
                lines += f"- Assignee: {_md_inline(result.entry.get('assignee'))}\n"
            if result.entry.get("next_action"):
                lines += f"- Next Action: {_md_inline(result.entry.get('next_action'))}\n"
            if result.entry.get("notes"):
                lines += f"- Notes: {_md_inline(result.entry.get('notes'))}\n"
        if result.warnings:
            lines += "\n## Warnings\n"
            for w in result.warnings:
                lines += f"- **{_md_inline(w.get('code', 'UNKNOWN'))}**: {_md_inline(w.get('message', ''))}\n"
        _write_output(lines, output)
        return

    with maybe_capture(output, format):
        if result.action == "clear":
            get_console().print(
                f"[bold yellow]Cleared state for {result.document_id}[/bold yellow]"
            )
        else:
            get_console().print(
                f"[bold green]Updated state for {result.document_id}[/bold green]"
            )
            get_console().print(f"Impl State: {result.entry.get('impl_state', '')}")
            get_console().print(f"Updated By: {result.entry.get('updated_by', '')}")
            if result.entry.get("priority"):
                get_console().print(f"Priority: {result.entry.get('priority')}")
            if result.entry.get("assignee"):
                get_console().print(f"Assignee: {result.entry.get('assignee')}")
            if result.entry.get("next_action"):
                get_console().print(f"Next Action: {result.entry.get('next_action')}")
            if result.entry.get("notes"):
                get_console().print(f"Notes: {result.entry.get('notes')}")
        _render_warnings_text(result.warnings, format, output)


@state.command("set")
@click.argument("document_id")
@agent_repo_options()
@click.option("--impl-state", help="Set implementation state (e.g., 'In Progress').")
@click.option("--notes", help="Set notes (max 500 chars).")
@click.option("--actor", help="Override the updated_by actor identity.")
@click.option(
    "--clear", "-c", is_flag=True, help="Clear the tracking state for this document."
)
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
        "state set", format, output, include_timestamp, run_id, root_path,
        correlation_id=correlation_id,
    ):
        validate_root_path(root_path, format=format, command="state set",
            include_timestamp=include_timestamp, run_id=run_id,
            output=output, correlation_id=correlation_id)
        validate_initialized(root_path, format=format, command="state set",
            include_timestamp=include_timestamp, run_id=run_id,
            output=output, correlation_id=correlation_id)

        _state_set_validate_args(
            impl_state, notes, clear, priority,
            depends_on, add_depends_on, remove_depends_on, clear_depends_on,
            blocked_by, add_blocked_by, remove_blocked_by, clear_blocked_by,
            assignee, next_action,
        )
        result = _state_set_execute(
            root_path, document_id, impl_state, notes, actor, clear, priority,
            depends_on, add_depends_on, remove_depends_on, clear_depends_on,
            blocked_by, add_blocked_by, remove_blocked_by, clear_blocked_by,
            assignee, next_action,
        )

        if format == "json":
            _render_state_set_json(
                result, root_path, include_timestamp, run_id,
                correlation_id, output,
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
        "state get", format, output, include_timestamp, run_id, root_path,
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

        use_case = StateDocumentUseCase(str(root_path))
        result = use_case.get_state(document_id)

        if format == "json":
            _write_output(
                format_envelope(
                    command="state get",
                    root=str(root_path),
                    success=True,
                    data=result.entry,
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                    correlation_id=correlation_id,
                ),
                output,
            )
            return

        if format == "md":
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
            get_console().print(f"[bold blue]{document_id}[/bold blue]")
            get_console().print(f"Impl State: {result.entry.get('impl_state')}")
            get_console().print(f"Updated By: {result.entry.get('updated_by')}")
            get_console().print(f"Updated: {result.entry.get('updated')}")
            if result.entry.get("notes"):
                get_console().print(f"Notes: {result.entry.get('notes')}")


def _state_list_validate_filters(ready, no_ready, blocked, no_blocked, assignee, priority, impl_state):
    if ready and no_ready:
        raise MeminitError(
            code=ErrorCode.E_INVALID_FILTER_VALUE,
            message="Cannot specify both --ready and --no-ready.",
            details={"conflicting_flags": ["--ready", "--no-ready"]},
        )
    if blocked and no_blocked:
        raise MeminitError(
            code=ErrorCode.E_INVALID_FILTER_VALUE,
            message="Cannot specify both --blocked and --no-blocked.",
            details={"conflicting_flags": ["--blocked", "--no-blocked"]},
        )
    if ready and blocked:
        raise MeminitError(
            code=ErrorCode.E_INVALID_FILTER_VALUE,
            message="Cannot specify both --ready and --blocked (an entry cannot be both ready and blocked).",
            details={"conflicting_flags": ["--ready", "--blocked"]},
        )
    ready_filter = True if ready else (False if no_ready else None)
    blocked_filter = True if blocked else (False if no_blocked else None)
    assignee_list = list(assignee) if assignee else None
    priority_list = list(priority) if priority else None
    impl_state_list = list(impl_state) if impl_state else None
    return ready_filter, blocked_filter, assignee_list, priority_list, impl_state_list


def _state_list_execute(root_path, format, include_timestamp, run_id, output, correlation_id,
                        ready_filter, blocked_filter, assignee_list, priority_list, impl_state_list):
    from meminit.core.use_cases.state_document import StateDocumentUseCase
    from meminit.core.services.repo_config import load_repo_layout
    from meminit.core.services.project_state import ImplState

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
    use_case = StateDocumentUseCase(str(root_path))
    result = use_case.list_states(
        ready=ready_filter,
        blocked=blocked_filter,
        assignee=assignee_list,
        priority=priority_list,
        impl_state=impl_state_list,
    )
    try:
        layout = load_repo_layout(root_path)
        valid_impl_states_set = set()
        valid_doc_statuses_set = set()
        for ns in layout.namespaces:
            valid_impl_states_set.update(ns.valid_impl_states)
            valid_doc_statuses_set.update(ns.valid_doc_statuses)
        valid_impl_states = sorted(list(valid_impl_states_set))
        valid_doc_statuses = sorted(list(valid_doc_statuses_set))
    except (MeminitError, ValueError, FileNotFoundError):
        valid_impl_states = ImplState.canonical_values()
        valid_doc_statuses = ["Draft", "In Review", "Approved", "Superseded"]
    return result, valid_impl_states, valid_doc_statuses


def _render_state_list_json(result, valid_impl_states, valid_doc_statuses, root_path,
                            include_timestamp, run_id, correlation_id, output):
    json_data = {
        "entries": result.entries,
        "valid_impl_states": valid_impl_states,
        "valid_doc_statuses": valid_doc_statuses,
    }
    if result.summary:
        json_data["summary"] = result.summary
    _write_output(
        format_envelope(
            command="state list",
            root=str(root_path),
            success=True,
            data=json_data,
            warnings=result.warnings,
            advice=result.advice,
            include_timestamp=include_timestamp,
            run_id=run_id,
            correlation_id=correlation_id,
        ),
        output,
    )


def _render_warnings_text(warnings, fmt, output):
    if not warnings:
        return
    if fmt == "md":
        lines = ["\n## Warnings\n"]
        for w in warnings:
            lines.append(f"- **{_md_inline(w.get('code', 'UNKNOWN'))}**: {_md_inline(w.get('message', ''))}")
        lines.append("")
        _write_output("\n".join(lines), output)
        return
    for w in warnings:
        get_console().print(
            f"[yellow]Warning ({w.get('code', 'UNKNOWN')}): {w.get('message', '')}[/yellow]"
        )


def _render_state_list_text(result, valid_impl_states, valid_doc_statuses, format, output):
    if format == "md":
        lines = ["# Meminit State List\n"]
        lines.append(
            f"**Valid Implementation States**: `{', '.join(valid_impl_states)}`  "
        )
        lines.append(
            f"**Valid Document Statuses**: `{', '.join(valid_doc_statuses)}`\n"
        )
        if not result.entries:
            lines.append("_No entries found._\n")
        else:
            rows = [
                [
                    e.get("document_id", ""),
                    e.get("impl_state", ""),
                    e.get("priority", ""),
                    "Yes" if e.get("ready") else "No",
                    _md_inline(e.get("assignee", "")),
                    str(e.get("updated", ""))[:10],
                ]
                for e in result.entries
            ]
            lines.append(
                _md_table(
                    ["Document ID", "Impl State", "Priority", "Ready", "Assignee", "Updated Date"],
                    rows,
                )
            )
            lines.append("")
        if result.warnings:
            lines.append("## Warnings\n")
            for w in result.warnings:
                lines.append(f"- **{_md_inline(w.get('code', 'UNKNOWN'))}**: {_md_inline(w.get('message', ''))}")
            lines.append("")
        if result.advice:
            lines.append("## Advisories\n")
            for a in result.advice:
                lines.append(f"- **{_md_inline(a.get('code', 'UNKNOWN'))}**: {_md_inline(a.get('message', ''))}")
            lines.append("")
        _write_output("\n".join(lines), output)
        return
    with maybe_capture(output, format):
        get_console().print(
            f"[bold]Valid Implementation States:[/bold] {', '.join(valid_impl_states)}"
        )
        get_console().print(
            f"[bold]Valid Document Statuses:[/bold] {', '.join(valid_doc_statuses)}\n"
        )
        if not result.entries:
            get_console().print(
                "[yellow]No entries found in project-state.yaml[/yellow]"
            )
            _render_warnings_text(result.warnings, format, output)
            return
        table = Table(title="Project State Entries")
        table.add_column("Document ID", style="cyan")
        table.add_column("Impl State", style="green")
        table.add_column("Priority")
        table.add_column("Ready")
        table.add_column("Assignee")
        table.add_column("Updated Date")
        for e in result.entries:
            table.add_row(
                e.get("document_id", ""),
                e.get("impl_state", ""),
                e.get("priority", ""),
                "Yes" if e.get("ready") else "No",
                e.get("assignee", ""),
                str(e.get("updated", ""))[:10],
            )
        get_console().print(table)
        _render_warnings_text(result.warnings, format, output)
        if result.advice:
            for a in result.advice:
                get_console().print(
                    f"[cyan]Advisory ({a.get('code', 'UNKNOWN')}): {a.get('message', '')}[/cyan]"
                )


@state.command("list")
@agent_repo_options()
@click.option("--ready", is_flag=True, default=False, help="Show only ready entries.")
@click.option("--no-ready", is_flag=True, default=False, help="Show only non-ready entries.")
@click.option("--blocked", is_flag=True, default=False, help="Show only blocked entries.")
@click.option("--no-blocked", is_flag=True, default=False, help="Show only non-blocked entries.")
@click.option("--assignee", multiple=True, help="Filter by assignee (repeatable).")
@click.option("--priority", multiple=True, help="Filter by priority (repeatable, e.g., P0 P1).")
@click.option("--impl-state", "impl_state", multiple=True, help="Filter by impl_state (repeatable).")
def state_list(root, format, output, include_timestamp, correlation_id,
               ready, no_ready, blocked, no_blocked, assignee, priority, impl_state):
    """List entries in project-state.yaml with optional filters."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "state list", format, output, include_timestamp, run_id, root_path,
        correlation_id=correlation_id,
    ):
        ready_filter, blocked_filter, assignee_list, priority_list, impl_state_list = (
            _state_list_validate_filters(ready, no_ready, blocked, no_blocked, assignee, priority, impl_state)
        )

        result, valid_impl_states, valid_doc_statuses = _state_list_execute(
            root_path, format, include_timestamp, run_id, output, correlation_id,
            ready_filter, blocked_filter, assignee_list, priority_list, impl_state_list,
        )

        if format == "json":
            _render_state_list_json(
                result, valid_impl_states, valid_doc_statuses, root_path,
                include_timestamp, run_id, correlation_id, output,
            )
            return

        _render_state_list_text(result, valid_impl_states, valid_doc_statuses, format, output)


def _state_next_execute(root_path, assignee, priority_at_least):
    from meminit.core.use_cases.state_document import StateDocumentUseCase

    use_case = StateDocumentUseCase(str(root_path))
    return use_case.next_state(assignee=assignee, priority_at_least=priority_at_least)


def _render_state_next_json(result, root_path, include_timestamp, run_id, correlation_id, output):
    _write_output(
        format_envelope(
            command="state next",
            root=str(root_path),
            success=True,
            data={
                "entry": result.entry,
                "selection": result.selection,
                "reason": result.reason,
            },
            warnings=result.warnings,
            include_timestamp=include_timestamp,
            run_id=run_id,
            correlation_id=correlation_id,
        ),
        output,
    )


def _render_state_next_text(result, fmt, output):
    if fmt == "md":
        lines = ["# Meminit State Next\n"]
        if result.entry:
            lines.append(f"- **Document ID**: `{result.entry.get('document_id')}`")
            lines.append(f"- **Impl State**: {_md_inline(result.entry.get('impl_state'))}")
            if result.entry.get("priority"):
                lines.append(f"- **Priority**: {_md_inline(result.entry.get('priority'))}")
            if result.entry.get("assignee"):
                lines.append(f"- **Assignee**: {_md_inline(result.entry.get('assignee'))}")
            if result.entry.get("next_action"):
                lines.append(f"- **Next Action**: {_md_inline(result.entry.get('next_action'))}")
            lines.append(f"- **Candidates Considered**: {result.selection.get('candidates_considered', 0)}")
        else:
            lines.append(f"_No ready items: {result.reason}_")
        if result.warnings:
            lines.append("\n## Warnings\n")
            for w in result.warnings:
                lines.append(f"- **{_md_inline(w.get('code', 'UNKNOWN'))}**: {_md_inline(w.get('message', ''))}")
            lines.append("")
        _write_output("\n".join(lines) + "\n", output)
        return
    with maybe_capture(output, fmt):
        if result.entry:
            get_console().print(
                f"[bold green]Next: {result.entry.get('document_id')}[/bold green]"
            )
            get_console().print(f"Impl State: {result.entry.get('impl_state')}")
            if result.entry.get("priority"):
                get_console().print(f"Priority: {result.entry.get('priority')}")
            if result.entry.get("assignee"):
                get_console().print(f"Assignee: {result.entry.get('assignee')}")
            if result.entry.get("next_action"):
                get_console().print(f"Next Action: {result.entry.get('next_action')}")
            get_console().print(
                f"Candidates considered: {result.selection.get('candidates_considered', 0)}"
            )
        else:
            get_console().print(
                f"[yellow]No ready items: {result.reason}[/yellow]"
            )
        _render_warnings_text(result.warnings, fmt, output)


def _state_blockers_execute(root_path, assignee):
    from meminit.core.use_cases.state_document import StateDocumentUseCase

    use_case = StateDocumentUseCase(str(root_path))
    return use_case.blockers_state(assignee=assignee)


def _render_state_blockers_json(result, root_path, include_timestamp, run_id, correlation_id, output):
    _write_output(
        format_envelope(
            command="state blockers",
            root=str(root_path),
            success=True,
            data={
                "blocked": result.blocked,
                "summary": result.summary,
            },
            warnings=result.warnings,
            include_timestamp=include_timestamp,
            run_id=run_id,
            correlation_id=correlation_id,
        ),
        output,
    )


def _render_state_blockers_text(result, fmt, output):
    if fmt == "md":
        lines = ["# Meminit State Blockers\n"]
        if not result.blocked:
            lines.append("_No blocked entries._\n")
        else:
            for b in result.blocked:
                lines.append(f"## {_md_inline(b['document_id'])}")
                lines.append(f"- **Impl State**: {_md_inline(b.get('impl_state', ''))}")
                if b.get("priority"):
                    lines.append(f"- **Priority**: {_md_inline(b['priority'])}")
                if b.get("assignee"):
                    lines.append(f"- **Assignee**: {_md_inline(b['assignee'])}")
                lines.append("- **Open Blockers**:")
                for ob in b.get("open_blockers", []):
                    known = "known" if ob.get("known") else "unknown"
                    lines.append(f"  - `{ob['id']}` ({_md_inline(ob.get('impl_state', 'N/A'))}, {known})")
                lines.append("")
        lines.append(f"**Summary**: {result.summary.get('total_entries', 0)} entries, "
                     f"{result.summary.get('blocked', 0)} blocked, "
                     f"{result.summary.get('ready', 0)} ready")
        if result.warnings:
            lines.append("\n## Warnings\n")
            for w in result.warnings:
                lines.append(f"- **{_md_inline(w.get('code', 'UNKNOWN'))}**: {_md_inline(w.get('message', ''))}")
            lines.append("")
        _write_output("\n".join(lines) + "\n", output)
        return
    with maybe_capture(output, fmt):
        if not result.blocked:
            get_console().print("[green]No blocked entries.[/green]")
        else:
            table = Table(title="Blocked Entries")
            table.add_column("Document ID", style="cyan")
            table.add_column("Impl State")
            table.add_column("Open Blockers", style="red")
            for b in result.blocked:
                blocker_ids = ", ".join(ob["id"] for ob in b.get("open_blockers", []))
                table.add_row(b["document_id"], b.get("impl_state", ""), blocker_ids)
            get_console().print(table)
        get_console().print(
            f"Summary: {result.summary.get('ready', 0)} ready, "
            f"{result.summary.get('blocked', 0)} blocked, "
            f"{result.summary.get('total_entries', 0)} total"
        )
        _render_warnings_text(result.warnings, fmt, output)


@state.command("next")
@agent_repo_options()
@click.option("--assignee", help="Restrict candidates to a specific assignee.")
@click.option("--priority-at-least", help="Restrict to priorities at or above threshold (P0-P3).")
def state_next(root, format, output, include_timestamp, correlation_id, assignee, priority_at_least):
    """Return the deterministically-selected next work item."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "state next", format, output, include_timestamp, run_id, root_path,
        correlation_id=correlation_id,
    ):
        validate_root_path(
            root_path, format=format, command="state next",
            include_timestamp=include_timestamp, run_id=run_id,
            output=output, correlation_id=correlation_id,
        )
        validate_initialized(
            root_path, format=format, command="state next",
            include_timestamp=include_timestamp, run_id=run_id,
            output=output, correlation_id=correlation_id,
        )
        result = _state_next_execute(root_path, assignee, priority_at_least)
        if format == "json":
            _render_state_next_json(result, root_path, include_timestamp, run_id, correlation_id, output)
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
        "state blockers", format, output, include_timestamp, run_id, root_path,
        correlation_id=correlation_id,
    ):
        validate_root_path(
            root_path, format=format, command="state blockers",
            include_timestamp=include_timestamp, run_id=run_id,
            output=output, correlation_id=correlation_id,
        )
        validate_initialized(
            root_path, format=format, command="state blockers",
            include_timestamp=include_timestamp, run_id=run_id,
            output=output, correlation_id=correlation_id,
        )
        result = _state_blockers_execute(root_path, assignee)
        if format == "json":
            _render_state_blockers_json(result, root_path, include_timestamp, run_id, correlation_id, output)
            return
        _render_state_blockers_text(result, format, output)


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
            violations.append({
                "code": code,
                "message": f"{status}: {a['target_path']}",
                "path": a["target_path"],
                "severity": "error" if status in _DRIFT_ERROR_STATES else "warning",
            })
    return violations


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
        "protocol check", format, output, include_timestamp, run_id, root_path,
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
                        get_console().print(f"  [{color}]{a['status'].upper()}[/{color}] {a['target_path']}")
        raise SystemExit(exit_code)


@protocol.command("sync")
@agent_repo_options()
@click.option(
    "--asset",
    "asset_ids",
    multiple=True,
    help="Restrict sync to specific asset IDs (repeatable).",
)
@click.option("--dry-run/--no-dry-run", default=True, help="Preview without writing (default: dry-run).")
@click.option("--force/--no-force", default=False, help="Allow overwriting tampered assets.")
def protocol_sync(asset_ids, dry_run, force, root, format, output, include_timestamp, correlation_id):
    """Synchronize protocol assets with the canonical contract."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler(
        "protocol sync", format, output, include_timestamp, run_id, root_path,
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
            sync_violations = _drift_violations(report.assets, "prior_status") if not report.success else []
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
            get_console().print(f"[bold blue]Meminit Protocol Sync[/bold blue] [yellow]({label})[/yellow]")
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
