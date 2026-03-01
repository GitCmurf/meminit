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
from meminit.core.domain.entities import NewDocumentParams, Violation
from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.exit_codes import (
    EX_CANTCREAT,
    EX_COMPLIANCE_FAIL,
    EX_USAGE,
    exit_code_for_error,
)
from meminit.core.services.observability import get_current_run_id, log_operation
from meminit.core.services.output_formatter import (
    format_envelope,
    format_error_envelope,
)
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
        if ctx and hasattr(ctx, "obj") and isinstance(ctx.obj, dict) and "console" in ctx.obj:
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
):
    """Centralized error handling and output formatting for CLI commands."""
    try:
        yield
    except MeminitError as e:
        if format == "json":
            _write_output(
                format_error_envelope(
                    command=command_name,
                    root=str(root_path) if root_path else ".",
                    error_code=e.code,
                    message=e.message,
                    details=e.details,
                    include_timestamp=include_timestamp,
                    run_id=run_id,
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
                get_console().print(f"[bold red][ERROR {e.code.value}] {e.message}[/bold red]")
        raise SystemExit(exit_code_for_error(e.code))
    except Exception as e:
        # Secure error handling (Item 2): Mask raw exceptions in user-facing message
        safe_msg = "An unexpected internal error occurred."
        if format == "json":
            _write_output(
                format_error_envelope(
                    command=command_name,
                    root=str(root_path) if root_path else ".",
                    error_code=ErrorCode.UNKNOWN_ERROR,
                    message=safe_msg,
                    details={"internal_error": str(e)},
                    include_timestamp=include_timestamp,
                    run_id=run_id,
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
                get_console().print(f"[bold red][ERROR UNKNOWN_ERROR] {safe_msg}[/bold red]")

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
                if not (path_str == f"{home}/.meminit" or path_str.startswith(f"{home}/.meminit/")):
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
            try:
                payload = json.loads(output_str)
            except Exception:
                payload = None

            if (
                isinstance(payload, dict)
                and payload.get("output_schema_version") == "2.0"
                and isinstance(payload.get("command"), str)
                and isinstance(payload.get("root"), str)
            ):
                click.echo(
                    format_error_envelope(
                        command=payload["command"],
                        root=payload["root"],
                        error_code=ErrorCode.PATH_ESCAPE,
                        message=f"Output path is considered unsafe: {output}",
                        details={"output_path": output},
                        include_timestamp="timestamp" in payload,
                        run_id=payload.get("run_id")
                        if isinstance(payload.get("run_id"), str)
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
            try:
                payload = json.loads(output_str)
            except Exception:
                payload = None

            if (
                isinstance(payload, dict)
                and payload.get("output_schema_version") == "2.0"
                and isinstance(payload.get("command"), str)
                and isinstance(payload.get("root"), str)
            ):
                click.echo(
                    format_error_envelope(
                        command=payload["command"],
                        root=payload["root"],
                        error_code=ErrorCode.UNKNOWN_ERROR,
                        message=f"Failed to write output file: {output}",
                        details={"output_path": output, "reason": str(exc)},
                        include_timestamp="timestamp" in payload,
                        run_id=payload.get("run_id")
                        if isinstance(payload.get("run_id"), str)
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
    **_kwargs: object,
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
                error_code=ErrorCode.CONFIG_MISSING,
                message=msg,
                details=details,
                include_timestamp=include_timestamp,
                run_id=run_id or get_current_run_id(),
            ),
            output=output,
        )
    elif format == "md":
        _write_output(f"# Meminit Error\n\n- Code: CONFIG_MISSING\n- Message: {msg}\n", output=output)
    else:
        with maybe_capture(output, format):
            get_console().print(f"[bold red][ERROR CONFIG_MISSING] {msg}[/bold red]")
    raise SystemExit(exit_code_for_error(ErrorCode.CONFIG_MISSING))


def validate_initialized(
    root_path: Path,
    format: str = "text",
    command: str = "unknown",
    include_timestamp: bool = False,
    run_id: Optional[str] = None,
    output: Optional[str] = None,
    **_kwargs: object,
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
        return

    msg = (
        "Repository not initialized: missing valid docops.config.yaml. " "Run 'meminit init' first."
    )
    details = {
        "hint": "meminit init",
        "root": str(root_path),
        "missing_file": "docops.config.yaml",
        "required": "regular file (not directory/symlink)",
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
            ),
            output=output,
        )
    elif format == "md":
        _write_output(f"# Meminit Error\n\n- Code: CONFIG_MISSING\n- Message: {msg}\n", output=output)
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
@click.version_option(package_name="meminit", prog_name="meminit")
@click.option("--no-color", is_flag=True, default=False, help="Disable ANSI colors in text output.")
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


@cli.command()
@click.argument("paths", nargs=-1, required=False)
@agent_repo_options()
@click.option("--quiet", is_flag=True, default=False, help="Only show failures (text output)")
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Treat warnings as errors (e.g., outside docs_root)",
)
def check(root, format, output, include_timestamp, quiet, strict, paths):
    """Run compliance checks on the repository or specified PATHS.

    PATHS may be relative, absolute, or glob patterns. If omitted, all governed
    docs under the configured docs_root are checked.
    """
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler("check", format, output, include_timestamp, run_id, root_path):
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
        )
        validate_initialized(
            root_path,
            format=format,
            command="check",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
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
                    rows.append(["error", v.get("code"), path, v.get("line"), v.get("message")])
            for item in result.warnings:
                path = item.get("path")
                for w in item.get("warnings", []):
                    rows.append(["warning", w.get("code"), path, w.get("line"), w.get("message")])

            title = "# Meminit Compliance Check"
            summary = (
                f"- Status: {status}\n- Files checked: {result.files_checked}\n"
                f"- Violations: {result.violations_count}\n- Warnings: {result.warnings_count}\n\n"
            )
            table = "## Findings\n\n" + _md_table(["Severity", "Rule", "File", "Line", "Message"], rows) + "\n"
            _write_output(f"{title}\n\n{summary}{table}", output)
            raise SystemExit(0 if result.success else EX_COMPLIANCE_FAIL)

        with maybe_capture(output, format):
            violations_by_path = {item["path"]: item["violations"] for item in result.violations}
            warnings_by_path = {item["path"]: item["warnings"] for item in result.warnings}

            if quiet:
                for path in sorted(violations_by_path.keys()):
                    for v in violations_by_path[path]:
                        line_info = f" (line {v['line']})" if v.get("line") is not None else ""
                        get_console().print(f"FAIL {path}: [{v['code']}] {v['message']}{line_info}")
                raise SystemExit(0 if result.success else EX_COMPLIANCE_FAIL)

            if paths:
                label = "file" if result.files_checked == 1 else "files"
                get_console().print(f"Checking {result.files_checked} existing {label}...")
                for path in result.checked_paths:
                    if path in violations_by_path:
                        get_console().print(f"FAIL {path}")
                        for v in violations_by_path[path]:
                            line_info = f" (line {v['line']})" if v.get("line") is not None else ""
                            get_console().print(f"  - [{v['code']}] {v['message']}{line_info}")
                        continue
                    if path in warnings_by_path:
                        get_console().print(f"WARN {path}")
                        for w in warnings_by_path[path]:
                            line_info = f" (line {w['line']})" if w.get("line") is not None else ""
                            get_console().print(f"  - [{w['code']}] {w['message']}{line_info}")
                        continue
                    get_console().print(f"OK {path}")
            else:
                table_title = "Compliance Violations" if result.violations_count else "Compliance Warnings"
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
                get_console().print(f"\n[bold yellow]Found {result.warnings_count} warning(s).[/bold yellow]")
            else:
                get_console().print("[bold green]Success! No violations found.[/bold green]")
            raise SystemExit(0)


@cli.command()
@agent_repo_options()
@click.option(
    "--strict/--no-strict",
    default=False,
    help="Treat warnings as errors (exit non-zero)",
)
def doctor(root, format, output, include_timestamp, strict):
    """Self-check: verify meminit can operate in this repository."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler("doctor", format, output, include_timestamp, run_id, root_path):
        validate_root_path(
            root_path,
            format=format,
            command="doctor",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
        )

        use_case = DoctorRepositoryUseCase(root_dir=str(root_path))
        issues = use_case.execute()

        errors = [
            i
            for i in issues
            if (i.severity.value if hasattr(i.severity, "value") else str(i.severity)) == "error"
        ]
        warnings = [
            i
            for i in issues
            if (i.severity.value if hasattr(i.severity, "value") else str(i.severity)) == "warning"
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
                    "severity": i.severity.value if hasattr(i.severity, "value") else str(i.severity),
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
                ),
                output,
            )
            raise SystemExit(exit_code)

        if format == "md":
            rows = [
                [
                    v.severity.value if hasattr(v.severity, "value") else str(v.severity),
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
                get_console().print("[bold green]OK: meminit is ready to run here.[/bold green]")
                return

            table = Table(title="Doctor Findings")
            table.add_column("Severity")
            table.add_column("Rule", style="cyan")
            table.add_column("File")
            table.add_column("Message", overflow="fold")

            for v in issues:
                severity_val = v.severity.value if hasattr(v.severity, "value") else str(v.severity)
                severity_color = "red" if severity_val == "error" else "yellow"
                table.add_row(
                    f"[{severity_color}]{severity_val}[/{severity_color}]",
                    v.rule,
                    v.file,
                    v.message,
                )

            get_console().print(table)
            if errors:
                get_console().print(f"\n[bold red]{len(errors)} error(s), {len(warnings)} warning(s).[/bold red]")
            else:
                get_console().print(f"\n[bold yellow]{len(warnings)} warning(s).[/bold yellow]")
            raise SystemExit(exit_code)


@cli.command()
@agent_repo_options()
@click.option("--plan", type=click.Path(exists=True, dir_okay=False), default=None, help="Apply a deterministic migration plan")
@click.option("--dry-run/--no-dry-run", default=True, help="Simulate fixes without changing files")
@click.option(
    "--namespace",
    default=None,
    help="Limit fixes to a single namespace (monorepo safety)",
)
def fix(root, plan, dry_run, namespace, format, output, include_timestamp):
    """Automatically fix common compliance violations."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler("fix", format, output, include_timestamp, run_id, root_path):
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
        )

        plan_obj = None
        if plan:
            try:
                with open(plan, "r", encoding="utf-8") as f:
                    data = json.load(f)
                plan_data = data.get("data", {}).get("plan") or data  # Handle envelope or direct
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
                            include_timestamp=include_timestamp
                        ),
                        output
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

            # Print remaining
            if report.remaining_violations:
                get_console().print(
                    f"\n[bold red]Remaining Violations ({len(report.remaining_violations)}):[/bold red]"
                )
                # Simplified list, suggest running check for details
                for v in report.remaining_violations[:5]:
                    get_console().print(f"- {v.file}: {v.message}")
                if len(report.remaining_violations) > 5:
                    get_console().print(f"... and {len(report.remaining_violations) - 5} more.")
                get_console().print("\nRun [bold]meminit check[/bold] for full details.")
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
def scan(root, plan, format, output, include_timestamp):
    """Scan a repository and suggest a DocOps migration plan (read-only)."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler("scan", format, output, include_timestamp, run_id, root_path):
        validate_root_path(
            root_path,
            format=format,
            command="scan",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
        )

        use_case = ScanRepositoryUseCase(root_dir=str(root_path))
        report = use_case.execute(generate_plan=bool(plan))
        scan_data = report.as_dict()

        if plan and report.plan:
            try:
                plan_json = format_envelope(
                    command="scan",
                    root=str(root_path),
                    success=True,
                    data={"plan": report.plan.as_dict()},
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                )
                with open(plan, "w", encoding="utf-8") as f:
                    f.write(plan_json + "\n")
                if format != "json":
                    get_console().print(f"[bold green]Saved migration plan to {plan}[/bold green]")
            except Exception as e:
                if format == "json":
                    _write_output(
                        format_error_envelope(
                            command="scan", 
                            root=str(root_path), 
                            error_code=ErrorCode.UNKNOWN_ERROR,
                            message=f"Failed to save plan: {e}", 
                            run_id=run_id,
                            include_timestamp=include_timestamp
                        ),
                        output
                    )
                    raise SystemExit(1) from e
                else:
                    get_console().print(f"[bold red]Failed to save plan: {e}[/bold red]")
                    raise SystemExit(1) from e

        if format == "json":
            _write_output(
                format_envelope(
                    command="scan",
                    root=str(root_path),
                    success=True,
                    data={"report": scan_data},
                    include_timestamp=include_timestamp,
                    run_id=run_id,
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
                rows = [[k, ", ".join(sorted(v))] for k, v in sorted(report.ambiguous_types.items())]
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
                    [ns.get("name"), ns.get("docs_root"), ns.get("repo_prefix_suggestion")]
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
                table = Table(title="Ambiguous type_directories (manual decision required)")
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
def install_precommit(root, format, output, include_timestamp):
    """Install a pre-commit hook to enforce meminit check."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler("install-precommit", format, output, include_timestamp, run_id, root_path):
        validate_root_path(
            root_path,
            format=format,
            command="install-precommit",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
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
                get_console().print("[yellow]meminit pre-commit hook already installed.[/yellow]")
                return
            if result.status == "created":
                get_console().print(f"[bold green]Created {result.config_path} with meminit hook.[/bold green]")
                return
            get_console().print(f"[bold green]Updated {result.config_path} with meminit hook.[/bold green]")


@cli.command()
@agent_repo_options()
def index(root, format, output, include_timestamp):
    """Build or update the repository index artifact."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler("index", format, output, include_timestamp, run_id, root_path):
        validate_root_path(
            root_path,
            format=format,
            command="index",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
        )

        use_case = IndexRepositoryUseCase(root_dir=str(root_path))
        report = use_case.execute()

        rel_index_path = None
        try:
            rel_index_path = report.index_path.relative_to(root_path).as_posix()
        except Exception:
            rel_index_path = str(report.index_path)

        if format == "json":
            _write_output(
                format_envelope(
                    command="index",
                    root=str(root_path),
                    success=True,
                    data={
                        "index_path": rel_index_path,
                        "document_count": report.document_count,
                    },
                    include_timestamp=include_timestamp,
                    run_id=run_id,
                ),
                output,
            )
            return

        if format == "md":
            _write_output(
                "# Meminit Index\n\n"
                "- Status: ok\n"
                f"- Index path: `{rel_index_path}`\n"
                f"- Documents: {report.document_count}\n",
                output,
            )
            return

        with maybe_capture(output, format):
            get_console().print(
                f"[bold green]Index written:[/bold green] {report.index_path} "
                f"({report.document_count} documents)"
            )


@cli.command()
@click.argument("document_id")
@agent_repo_options()
def resolve(document_id, root, format, output, include_timestamp):
    """Resolve a document_id to a path using the index."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler("resolve", format, output, include_timestamp, run_id, root_path):
        validate_root_path(
            root_path,
            format=format,
            command="resolve",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
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
def identify(path, root, format, output, include_timestamp):
    """Identify a document_id for a given path using the index."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler("identify", format, output, include_timestamp, run_id, root_path):
        validate_root_path(
            root_path,
            format=format,
            command="identify",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
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
def link(document_id, root, format, output, include_timestamp):
    """Print a Markdown link for a document_id using the index."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler("link", format, output, include_timestamp, run_id, root_path):
        validate_root_path(
            root_path,
            format=format,
            command="link",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
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
@click.option("--dry-run/--no-dry-run", default=True, help="Preview changes without writing files")
@click.option(
    "--rewrite-references/--no-rewrite-references",
    default=False,
    help="Rewrite old IDs in document bodies",
)
def migrate_ids(root, dry_run, rewrite_references, format, output, include_timestamp):
    """Migrate legacy document_id values into REPO-TYPE-SEQ format."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler("migrate-ids", format, output, include_timestamp, run_id, root_path):
        validate_root_path(
            root_path,
            format=format,
            command="migrate-ids",
            include_timestamp=include_timestamp,
            run_id=run_id,
            output=output,
        )

        use_case = MigrateIdsUseCase(root_dir=str(root_path))
        report = use_case.execute(dry_run=dry_run, rewrite_references=rewrite_references)

        if format == "json":
            _write_output(
                format_envelope(
                    command="migrate-ids",
                    root=str(root_path),
                    success=True,
                    data={"report": report.as_dict()},
                    include_timestamp=include_timestamp,
                    run_id=run_id,
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
            action_count = len(report.actions)
            get_console().print("[bold blue]Meminit ID Migration[/bold blue]")
            get_console().print(f"Root: {root_path}")
            get_console().print(f"Mode: {'DRY RUN' if dry_run else 'APPLY'}")
            get_console().print(f"Actions: {action_count}")
            if report.skipped_files:
                get_console().print(f"Skipped: {len(report.skipped_files)}")


@cli.command()
@agent_repo_options()
def init(root, format, output, include_timestamp):
    """Initialize a new DocOps repository structure."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler("init", format, output, include_timestamp, run_id, root_path):
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
            get_console().print(f"[bold green]Initialized DocOps repository at {root}[/bold green]")
            get_console().print("- Created directory structure (docs/)")
            get_console().print("- Created docops.config.yaml")
            get_console().print("- Created AGENTS.md")


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
    interactive,
):
    """Create a new document of TYPE with TITLE."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler("new", format, output, include_timestamp, run_id, root_path):
        if interactive and format == "json":
            raise MeminitError(ErrorCode.INVALID_FLAG_COMBINATION, "--interactive and --format json are incompatible")

        if edit and (dry_run or format == "json"):
            raise MeminitError(ErrorCode.INVALID_FLAG_COMBINATION, "--edit is incompatible with --dry-run and --format json")

        if list_types and (doc_type or title):
            raise MeminitError(ErrorCode.INVALID_FLAG_COMBINATION, "--list-types cannot be combined with TYPE or TITLE arguments")

        if list_types:
            validate_root_path(root_path, format=format, command="new", include_timestamp=include_timestamp, run_id=run_id, output=output)
            validate_initialized(root_path, format=format, command="new", include_timestamp=include_timestamp, run_id=run_id, output=output)
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
            validate_root_path(root_path, format=format, command="new", output=output)
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
            raise MeminitError(ErrorCode.INVALID_FLAG_COMBINATION, "TYPE and TITLE are required unless --list-types is specified")

        validate_root_path(root_path, format=format, command="new", include_timestamp=include_timestamp, run_id=run_id, output=output)
        validate_initialized(root_path, format=format, command="new", include_timestamp=include_timestamp, run_id=run_id, output=output)

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
            raise MeminitError(ErrorCode.UNKNOWN_ERROR, str(result.error) if result.error else "Unknown error")

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
                lines.extend([
                    "",
                    "## Would Create",
                    "",
                    f"- Path: `{_md_escape(rel_path)}`",
                    f"- Document ID: `{_md_escape(result.document_id)}`"
                ])
            _write_output("\n".join(lines), output)
        else:
            with maybe_capture(output, format):
                if dry_run:
                    get_console().print(f"[bold yellow]Would create {result.doc_type}: {result.path}[/bold yellow]")
                else:
                    get_console().print(f"[bold green]Created {result.doc_type}: {result.path}[/bold green]")

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
def adr_new(title, root, format, output, include_timestamp, namespace):
    """Create a new ADR (alias for 'meminit new ADR')."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler("adr new", format, output, include_timestamp, run_id, root_path):
        validate_root_path(root_path, format=format, command="adr new", include_timestamp=include_timestamp, run_id=run_id, output=output)
        validate_initialized(root_path, format=format, command="adr new", include_timestamp=include_timestamp, run_id=run_id, output=output)
        
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
            raise MeminitError(ErrorCode.UNKNOWN_ERROR, str(result.error) if result.error else "Unknown error")

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
                ),
                output,
            )
        elif format == "md":
            lines = ["# Meminit ADR New", "", "- Status: ok", f"- Title: `{_md_escape(result.title)}`"]
            if rel_path:
                lines.append(f"- Path: `{_md_escape(rel_path)}`")
            _write_output("\n".join(lines), output)
        else:
            with maybe_capture(output, format):
                get_console().print(f"[bold green]Created ADR: {result.path}[/bold green]")


@cli.command()
@agent_repo_options()
@click.option("--deep", is_flag=True, default=False, help="Include per-namespace document counts (10s budget)")
def context(root, deep, format, output, include_timestamp):
    """Emit repository configuration context for agent bootstrap (FR-6)."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler("context", format, output, include_timestamp, run_id, root_path):
        validate_root_path(root_path, format=format, command="context", include_timestamp=include_timestamp, run_id=run_id, output=output)
        validate_initialized(root_path, format=format, command="context", include_timestamp=include_timestamp, run_id=run_id, output=output)

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
                    get_console().print(f"  - {warning.get('code')}: {warning.get('message')}")


@cli.group()
def org():
    """Org profiles (XDG install + vendoring into repos)."""
    pass


@org.command("install")
@click.option("--profile", default="default", help="Org profile name to install")
@click.option("--dry-run/--no-dry-run", default=True, help="Preview without writing to XDG paths")
@click.option("--force/--no-force", default=False, help="Overwrite an existing installed profile")
@agent_output_options()
def org_install(profile, dry_run, force, format, output, include_timestamp):
    """Install the packaged org profile into XDG user data directories."""
    run_id = get_current_run_id()
    with command_output_handler("org install", format, output, include_timestamp, run_id):
        use_case = InstallOrgProfileUseCase()
        report = use_case.execute(profile_name=profile, dry_run=dry_run, force=force)

        if format == "json":
            _write_output(
                format_envelope(
                    command="org install",
                    root=".",
                    success=True,
                    data=report.as_dict(),
                    include_timestamp=include_timestamp,
                    run_id=run_id,
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
@click.option("--force/--no-force", default=False, help="Overwrite an existing lock and update vendored files")
@click.option("--include-org-docs/--no-include-org-docs", default=True, help="Vendor ORG governance markdown docs too")
def org_vendor(root, profile, dry_run, force, include_org_docs, format, output, include_timestamp):
    """Vendor (copy + pin) org standards into a repo to prevent unintentional drift."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler("org vendor", format, output, include_timestamp, run_id, root_path):
        validate_root_path(root_path, format=format, command="org vendor", include_timestamp=include_timestamp, run_id=run_id, output=output)

        use_case = VendorOrgProfileUseCase(root_dir=str(root_path))
        report = use_case.execute(profile_name=profile, dry_run=dry_run, force=force, include_org_docs=include_org_docs)

        if format == "json":
            _write_output(
                format_envelope(
                    command="org vendor",
                    root=str(root_path),
                    success=True,
                    data=report.as_dict(),
                    include_timestamp=include_timestamp,
                    run_id=run_id,
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
def org_status(root, profile, format, output, include_timestamp):
    """Show org profile install + repo lock status (drift visibility)."""
    run_id = get_current_run_id()
    root_path = Path(root).resolve()

    with command_output_handler("org status", format, output, include_timestamp, run_id, root_path):
        validate_root_path(root_path, format=format, command="org status", include_timestamp=include_timestamp, run_id=run_id, output=output)

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
                ),
                output,
            )
            return

        with maybe_capture(output, format):
            get_console().print("[bold blue]Meminit Org Status[/bold blue]")
            get_console().print(f"Profile: {profile}")
            get_console().print(f"Global installed: {report.global_installed}")


if __name__ == "__main__":
    cli()
