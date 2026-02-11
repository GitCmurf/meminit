import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from meminit.core.domain.entities import FixReport, Violation
from meminit.core.services.output_contracts import OUTPUT_SCHEMA_VERSION
from meminit.core.use_cases.check_repository import CheckRepositoryUseCase
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


def _json_payload(payload: dict) -> str:
    enriched = {"output_schema_version": OUTPUT_SCHEMA_VERSION, **payload}
    return json.dumps(enriched, indent=2)


def _md_escape(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def _md_table(headers: list[str], rows: list[list[object]]) -> str:
    head = "| " + " | ".join(_md_escape(h) for h in headers) + " |"
    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(_md_escape(c) for c in row) + " |" for row in rows]
    return "\n".join([head, sep, *body])


def validate_root_path(root_path: Path, format: str = "text") -> None:
    if root_path.exists() and root_path.is_dir():
        return

    if not root_path.exists():
        msg = f"Path does not exist: {root_path}"
    else:
        msg = f"Path is not a directory: {root_path}"

    if format == "json":
        click.echo(_json_payload({"status": "error", "message": msg}))
    elif format == "md":
        click.echo(f"# Meminit Error\n\n- {msg}\n")
    else:
        console.print(f"[bold red]Error: {msg}[/bold red]")
    raise SystemExit(1)


def get_severity_value(violation: Violation) -> str:
    return (
        violation.severity.value
        if hasattr(violation.severity, "value")
        else str(violation.severity)
    )


@click.group()
@click.version_option(package_name="meminit", prog_name="meminit")
def cli():
    """Meminit DocOps CLI"""
    pass


@cli.command()
@click.option("--root", default=".", help="Root directory of the repository")
@click.option(
    "--format", type=click.Choice(["text", "json", "md"]), default="text", help="Output format"
)
def check(root, format):
    """Run compliance checks on the repository."""
    if format == "text":
        console.print("[bold blue]Meminit Compliance Check[/bold blue]")

    root_path = Path(root).resolve()
    validate_root_path(root_path, format=format)

    if format == "text":
        console.print(f"Scanning root: {root_path}")

    try:
        use_case = CheckRepositoryUseCase(root_dir=str(root_path))
        violations = use_case.execute()
    except Exception as e:
        if format == "json":
            click.echo(_json_payload({"status": "error", "message": str(e)}))
        elif format == "md":
            click.echo(
                f"# Meminit Compliance Check\n\n- Status: error\n- Message: {_md_escape(e)}\n"
            )
        else:
            console.print(f"[bold red]Error during compliance check: {e}[/bold red]")
        exit(1)

    if not violations:
        if format == "json":
            click.echo(_json_payload({"status": "success", "violations": []}))
            return
        if format == "md":
            click.echo("# Meminit Compliance Check\n\n- Status: success\n- Violations: 0\n")
            return
        console.print("[bold green]Success! No violations found.[/bold green]")
        return

    if format == "json":
        data = {
            "status": "failed",
            "violations": [
                {
                    "file": v.file,
                    "line": v.line,
                    "rule": v.rule,
                    "message": v.message,
                    "severity": get_severity_value(v),
                }
                for v in violations
            ],
        }
        click.echo(_json_payload(data))
        exit(1)

    if format == "md":
        rows = [[get_severity_value(v), v.rule, v.file, v.line, v.message] for v in violations]
        click.echo(
            "# Meminit Compliance Check\n\n"
            f"- Status: failed\n- Violations: {len(violations)}\n\n"
            "## Violations\n\n"
            + _md_table(["Severity", "Rule", "File", "Line", "Message"], rows)
            + "\n"
        )
        raise SystemExit(1)

    table = Table(title="Compliance Violations")
    table.add_column("Severity")
    table.add_column("Rule", style="cyan")
    table.add_column("File")
    table.add_column("Message", overflow="fold")

    for v in violations:
        severity_val = get_severity_value(v)
        severity_color = "red" if severity_val == "error" else "yellow"
        table.add_row(
            f"[{severity_color}]{severity_val}[/{severity_color}]",
            v.rule,
            f"{v.file}:{v.line}",
            v.message,
        )
    console.print(table)
    console.print(f"\n[bold red]Found {len(violations)} violations.[/bold red]")
    exit(1)


@cli.command()
@click.option("--root", default=".", help="Root directory of the repository")
@click.option(
    "--format", type=click.Choice(["text", "json", "md"]), default="text", help="Output format"
)
@click.option(
    "--strict/--no-strict", default=False, help="Treat warnings as errors (exit non-zero)"
)
def doctor(root, format, strict):
    """Self-check: verify meminit can operate in this repository."""
    root_path = Path(root).resolve()
    validate_root_path(root_path, format=format)

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

    exit_code = 0
    if errors or (strict and warnings):
        exit_code = 1

    status = "ok"
    if errors:
        status = "error"
    elif warnings:
        status = "warn"

    if format == "json":
        click.echo(
            _json_payload(
                {
                    "status": status,
                    "strict": strict,
                    "issues": [
                        {
                            "file": v.file,
                            "line": v.line,
                            "rule": v.rule,
                            "message": v.message,
                            "severity": v.severity.value
                            if hasattr(v.severity, "value")
                            else str(v.severity),
                        }
                        for v in issues
                    ],
                }
            )
        )
        exit(exit_code)

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
        click.echo(
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
            )
        )
        exit(exit_code)

    console.print("[bold blue]Meminit Doctor[/bold blue]")
    console.print(f"Root: {root_path}")

    if not issues:
        console.print("[bold green]OK: meminit is ready to run here.[/bold green]")
        exit(exit_code)

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

    console.print(table)
    if errors:
        console.print(f"\n[bold red]{len(errors)} error(s), {len(warnings)} warning(s).[/bold red]")
    else:
        console.print(f"\n[bold yellow]{len(warnings)} warning(s).[/bold yellow]")

    exit(exit_code)


@cli.command()
@click.option("--root", default=".", help="Root directory of the repository")
@click.option("--dry-run/--no-dry-run", default=True, help="Simulate fixes without changing files")
@click.option(
    "--namespace", default=None, help="Limit fixes to a single namespace (monorepo safety)"
)
def fix(root, dry_run, namespace):
    """Automatically fix common compliance violations."""
    msg = "[bold blue]Meminit Compliance Fixer[/bold blue]"
    if dry_run:
        msg += " [yellow](DRY RUN)[/yellow]"
    console.print(msg)

    root_path = Path(root).resolve()
    validate_root_path(root_path, format="text")

    try:
        fixer = FixRepositoryUseCase(root_dir=str(root_path))
        report = fixer.execute(dry_run=dry_run, namespace=namespace)
    except Exception as e:
        console.print(f"[bold red]Error during processing: {e}[/bold red]")
        raise SystemExit(1)

    # Print fixed actions
    if report.fixed_violations:
        table = Table(title="Actions Taken" if not dry_run else "Proposed Actions")
        table.add_column("File")
        table.add_column("Action", style="green")
        table.add_column("Description")

        for action in report.fixed_violations:
            table.add_row(action.file, action.action, action.description)

        console.print(table)
        console.print(f"\n[bold green]Applied {len(report.fixed_violations)} fixes.[/bold green]")
    else:
        console.print("[yellow]No auto-fixes available for current violations.[/yellow]")

    # Print remaining
    if report.remaining_violations:
        console.print(
            f"\n[bold red]Remaining Violations ({len(report.remaining_violations)}):[/bold red]"
        )
        # Simplified list, suggest running check for details
        for v in report.remaining_violations[:5]:
            console.print(f"- {v.file}: {v.message}")
        if len(report.remaining_violations) > 5:
            console.print(f"... and {len(report.remaining_violations)-5} more.")
        console.print("\nRun [bold]meminit check[/bold] for full details.")
        raise SystemExit(1)

    console.print("\n[bold green]All clear![/bold green]")


@cli.command()
@click.option("--root", default=".", help="Root directory of the repository")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Optional path to write JSON report",
)
@click.option(
    "--format", type=click.Choice(["json", "text", "md"]), default="json", help="Output format"
)
def scan(root, output, format):
    """Scan a repository and suggest a DocOps migration plan (read-only)."""
    root_path = Path(root).resolve()
    validate_root_path(root_path, format=format)

    use_case = ScanRepositoryUseCase(root_dir=str(root_path))
    report = use_case.execute()
    payload = {"status": "ok", "report": report.as_dict()}

    if output:
        output.write_text(_json_payload(payload), encoding="utf-8")

    if format == "json":
        click.echo(_json_payload(payload))
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
                        ["Namespace", "Docs Root", "Repo Prefix", "Exists", "Governed .md"], rows
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
        click.echo("\n".join(lines))
        return

    console.print("[bold blue]Meminit Scan[/bold blue]")
    console.print(f"Root: {root_path}")
    console.print(f"Docs root: {report.docs_root or 'Not found'}")
    console.print(f"Markdown files: {report.markdown_count}")
    if getattr(report, "governed_markdown_count", None) is not None:
        console.print(
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
        console.print(table)

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
        console.print(table)
    if report.suggested_type_directories:
        table = Table(title="Suggested type_directories overrides")
        table.add_column("Type")
        table.add_column("Directory")
        for k, v in sorted(report.suggested_type_directories.items()):
            table.add_row(k, v)
        console.print(table)
    if report.ambiguous_types:
        table = Table(title="Ambiguous type_directories (manual decision required)")
        table.add_column("Type")
        table.add_column("Candidates")
        for k, v in sorted(report.ambiguous_types.items()):
            table.add_row(k, ", ".join(sorted(v)))
        console.print(table)
    if getattr(report, "suggested_namespaces", None):
        table = Table(title="Suggested namespaces (monorepo)")
        table.add_column("Name")
        table.add_column("Docs Root")
        table.add_column("Repo Prefix")
        for ns in report.suggested_namespaces:
            if not isinstance(ns, dict):
                continue
            table.add_row(
                str(ns.get("name")), str(ns.get("docs_root")), str(ns.get("repo_prefix_suggestion"))
            )
        console.print(table)
    for note in report.notes:
        console.print(f"- {note}")


@cli.command("install-precommit")
@click.option("--root", default=".", help="Root directory of the repository")
def install_precommit(root):
    """Install a pre-commit hook to enforce meminit check."""
    root_path = Path(root).resolve()
    validate_root_path(root_path, format="text")

    use_case = InstallPrecommitUseCase(root_dir=str(root_path))
    try:
        result = use_case.execute()
    except ValueError as exc:
        console.print(f"[bold red]Error: {exc}[/bold red]")
        raise SystemExit(1)

    if result.status == "already_installed":
        console.print("[yellow]meminit pre-commit hook already installed.[/yellow]")
        return
    if result.status == "created":
        console.print(f"[bold green]Created {result.config_path} with meminit hook.[/bold green]")
        return
    console.print(f"[bold green]Updated {result.config_path} with meminit hook.[/bold green]")


@cli.command()
@click.option("--root", default=".", help="Root directory of the repository")
@click.option(
    "--format", type=click.Choice(["text", "json", "md"]), default="text", help="Output format"
)
def index(root, format):
    """Build or update the repository index artifact."""
    root_path = Path(root).resolve()
    validate_root_path(root_path, format=format)

    use_case = IndexRepositoryUseCase(root_dir=str(root_path))
    try:
        report = use_case.execute()
    except FileNotFoundError as exc:
        if format == "json":
            click.echo(_json_payload({"status": "error", "message": str(exc)}))
        elif format == "md":
            click.echo(f"# Meminit Index\n\n- Status: error\n- Message: {_md_escape(exc)}\n")
        else:
            console.print(f"[bold red]Error: {exc}[/bold red]")
        raise SystemExit(1)

    rel_index_path = None
    try:
        rel_index_path = report.index_path.relative_to(root_path).as_posix()
    except Exception:
        rel_index_path = str(report.index_path)

    if format == "json":
        click.echo(
            _json_payload(
                {
                    "status": "ok",
                    "report": {
                        "index_path": rel_index_path,
                        "document_count": report.document_count,
                    },
                }
            )
        )
        return

    if format == "md":
        click.echo(
            "# Meminit Index\n\n"
            "- Status: ok\n"
            f"- Index path: `{rel_index_path}`\n"
            f"- Documents: {report.document_count}\n\n"
            "Next:\n"
            f"- `meminit resolve <DOCUMENT_ID> --root {root}`\n"
            f"- `meminit identify <PATH> --root {root}`\n"
        )
        return

    console.print(
        f"[bold green]Index written:[/bold green] {report.index_path} "
        f"({report.document_count} documents)"
    )


@cli.command()
@click.argument("document_id")
@click.option("--root", default=".", help="Root directory of the repository")
def resolve(document_id, root):
    """Resolve a document_id to a path using the index."""
    root_path = Path(root).resolve()
    validate_root_path(root_path, format="text")

    use_case = ResolveDocumentUseCase(root_dir=str(root_path))
    try:
        result = use_case.execute(document_id)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[bold red]Error: {exc}[/bold red]")
        raise SystemExit(1)

    if not result.path:
        console.print(f"[bold red]Not found:[/bold red] {document_id}")
        raise SystemExit(1)

    console.print(result.path)


@cli.command()
@click.argument("path")
@click.option("--root", default=".", help="Root directory of the repository")
def identify(path, root):
    """Identify a document_id for a given path using the index."""
    root_path = Path(root).resolve()
    validate_root_path(root_path, format="text")

    use_case = IdentifyDocumentUseCase(root_dir=str(root_path))
    try:
        result = use_case.execute(path)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[bold red]Error: {exc}[/bold red]")
        raise SystemExit(1)

    if not result.document_id:
        console.print(f"[bold red]Not governed:[/bold red] {result.path}")
        raise SystemExit(1)

    console.print(result.document_id)


@cli.command()
@click.argument("document_id")
@click.option("--root", default=".", help="Root directory of the repository")
def link(document_id, root):
    """Print a Markdown link for a document_id using the index."""
    root_path = Path(root).resolve()
    validate_root_path(root_path, format="text")

    use_case = ResolveDocumentUseCase(root_dir=str(root_path))
    try:
        result = use_case.execute(document_id)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[bold red]Error: {exc}[/bold red]")
        raise SystemExit(1)

    if not result.path:
        console.print(f"[bold red]Not found:[/bold red] {document_id}")
        raise SystemExit(1)

    console.print(f"[{document_id}]({result.path})")


@cli.command("migrate-ids")
@click.option("--root", default=".", help="Root directory of the repository")
@click.option("--dry-run/--no-dry-run", default=True, help="Preview changes without writing files")
@click.option(
    "--rewrite-references/--no-rewrite-references",
    default=False,
    help="Rewrite old IDs in document bodies",
)
@click.option(
    "--format", type=click.Choice(["text", "json", "md"]), default="text", help="Output format"
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Optional path to write JSON report",
)
def migrate_ids(root, dry_run, rewrite_references, format, output):
    """Migrate legacy document_id values into REPO-TYPE-SEQ format."""
    root_path = Path(root).resolve()
    validate_root_path(root_path, format=format)

    use_case = MigrateIdsUseCase(root_dir=str(root_path))
    try:
        report = use_case.execute(dry_run=dry_run, rewrite_references=rewrite_references)
    except Exception as exc:
        if format == "json":
            click.echo(_json_payload({"status": "error", "message": str(exc)}))
        elif format == "md":
            click.echo(f"# Meminit ID Migration\n\n- Status: error\n- Message: {_md_escape(exc)}\n")
        else:
            console.print(f"[bold red]Error: {exc}[/bold red]")
        raise SystemExit(1)

    payload = {"status": "ok", "report": report.as_dict()}
    if output:
        output.write_text(_json_payload(payload), encoding="utf-8")

    if format == "json":
        click.echo(_json_payload(payload))
        return
    if format == "md":
        rows = [
            [a.file, a.doc_type, a.old_id, a.new_id, a.rewritten_reference_count]
            for a in report.actions
        ]
        click.echo(
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
            )
        )
        return

    action_count = len(report.actions)
    console.print("[bold blue]Meminit ID Migration[/bold blue]")
    console.print(f"Root: {root_path}")
    console.print(f"Mode: {'DRY RUN' if dry_run else 'APPLY'}")
    console.print(f"Actions: {action_count}")
    if report.skipped_files:
        console.print(f"Skipped: {len(report.skipped_files)}")


@cli.command()
@click.option("--root", default=".", help="Root directory of the repository")
def init(root):
    """Initialize a new DocOps repository structure."""

    root_path = Path(root).resolve()
    validate_root_path(root_path, format="text")

    use_case = InitRepositoryUseCase(str(root_path))
    try:
        use_case.execute()
        console.print(f"[bold green]Initialized DocOps repository at {root}[/bold green]")
        console.print("- Created directory structure (docs/)")
        console.print("- Created docops.config.yaml")
        console.print("- Created AGENTS.md")
    except Exception as e:
        console.print(f"[bold red]Error during initialization: {e}[/bold red]")
        exit(1)


@cli.command(name="new")
@click.argument("doc_type")
@click.argument("title")
@click.option("--root", default=".", help="Root directory of the repository")
@click.option("--namespace", default=None, help="Namespace to create the doc in (monorepo mode)")
def new_doc(doc_type, title, root, namespace):
    """Create a new document of TYPE with TITLE.

    Supported types: ADR, PRD, FDD, etc.
    """
    root_path = Path(root).resolve()
    validate_root_path(root_path, format="text")
    # Implicit init check? Or just fail if no docs dir? UseCase handles path creation.

    # Simple alias handling for adr-tools compatibility (e.g. `meminit new adr ...`)
    if doc_type.lower() == "adr":
        doc_type = "ADR"

    use_case = NewDocumentUseCase(str(root_path))
    try:
        path = use_case.execute(doc_type, title, namespace=namespace)
        console.print(f"[bold green]Created {doc_type}: {path}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error creating document: {e}[/bold red]")
        exit(1)


@cli.group()
def adr():
    """ADR tools (compatibility alias)."""
    pass


@adr.command(name="new")
@click.argument("title")
@click.option("--root", default=".", help="Root directory of the repository")
@click.option("--namespace", default=None, help="Namespace to create the ADR in (monorepo mode)")
def adr_new(title, root, namespace):
    """Create a new ADR (alias for 'meminit new ADR')."""
    root_path = Path(root).resolve()
    validate_root_path(root_path, format="text")
    use_case = NewDocumentUseCase(str(root_path))
    try:
        path = use_case.execute("ADR", title, namespace=namespace)
        console.print(f"[bold green]Created ADR: {path}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error creating document: {e}[/bold red]")
        exit(1)


@cli.group()
def org():
    """Org profiles (XDG install + vendoring into repos)."""
    pass


@org.command("install")
@click.option("--profile", default="default", help="Org profile name to install")
@click.option("--dry-run/--no-dry-run", default=True, help="Preview without writing to XDG paths")
@click.option("--force/--no-force", default=False, help="Overwrite an existing installed profile")
@click.option(
    "--format", type=click.Choice(["text", "json", "md"]), default="text", help="Output format"
)
def org_install(profile, dry_run, force, format):
    """Install the packaged org profile into XDG user data directories."""
    use_case = InstallOrgProfileUseCase()
    report = use_case.execute(profile_name=profile, dry_run=dry_run, force=force)

    if format == "json":
        click.echo(_json_payload({"status": "ok", "report": report.as_dict()}))
        return
    if format == "md":
        click.echo(
            "# Meminit Org Install\n\n"
            f"- Profile: `{profile}`\n"
            f"- Dry run: `{dry_run}`\n"
            f"- Target: `{report.target_dir}`\n"
            f"- Message: {_md_escape(report.message)}\n"
        )
        return

    console.print("[bold blue]Meminit Org Install[/bold blue]")
    console.print(f"Profile: {profile}")
    console.print(f"Target: {report.target_dir}")
    console.print(report.message)


@org.command("vendor")
@click.option("--root", default=".", help="Root directory of the repository")
@click.option("--profile", default="default", help="Org profile name to vendor")
@click.option("--dry-run/--no-dry-run", default=True, help="Preview without writing files")
@click.option(
    "--force/--no-force", default=False, help="Overwrite an existing lock and update vendored files"
)
@click.option(
    "--include-org-docs/--no-include-org-docs",
    default=True,
    help="Vendor ORG governance markdown docs too",
)
@click.option(
    "--format", type=click.Choice(["text", "json", "md"]), default="text", help="Output format"
)
def org_vendor(root, profile, dry_run, force, include_org_docs, format):
    """Vendor (copy + pin) org standards into a repo to prevent unintentional drift."""
    root_path = Path(root).resolve()
    validate_root_path(root_path, format=format)

    use_case = VendorOrgProfileUseCase(root_dir=str(root_path))
    report = use_case.execute(
        profile_name=profile,
        dry_run=dry_run,
        force=force,
        include_org_docs=include_org_docs,
    )

    if format == "json":
        click.echo(_json_payload({"status": "ok", "report": report.as_dict()}))
        return
    if format == "md":
        click.echo(
            "# Meminit Org Vendor\n\n"
            f"- Root: `{root_path}`\n"
            f"- Profile: `{profile}` ({report.source})\n"
            f"- Dry run: `{dry_run}`\n"
            f"- Would create: {report.created_files}\n"
            f"- Would update: {report.updated_files}\n"
            f"- Unchanged: {report.unchanged_files}\n"
            f"- Lock: `{report.lock_path}`\n"
            f"- Message: {_md_escape(report.message)}\n"
        )
        return

    console.print("[bold blue]Meminit Org Vendor[/bold blue]")
    console.print(f"Root: {root_path}")
    console.print(f"Profile: {profile} ({report.source})")
    console.print(f"Dry run: {dry_run}")
    console.print(
        f"Create: {report.created_files}  Update: {report.updated_files}  Unchanged: {report.unchanged_files}"
    )
    console.print(f"Lock: {report.lock_path}")
    console.print(report.message)


@org.command("status")
@click.option("--root", default=".", help="Root directory of the repository")
@click.option("--profile", default="default", help="Org profile name")
@click.option(
    "--format", type=click.Choice(["text", "json", "md"]), default="text", help="Output format"
)
def org_status(root, profile, format):
    """Show org profile install + repo lock status (drift visibility)."""
    root_path = Path(root).resolve()
    validate_root_path(root_path, format=format)

    report = OrgStatusUseCase(root_dir=str(root_path)).execute(profile_name=profile)
    if format == "json":
        click.echo(_json_payload({"status": "ok", "report": report.as_dict()}))
        return
    if format == "md":
        click.echo(
            "# Meminit Org Status\n\n"
            f"- Root: `{root_path}`\n"
            f"- Profile: `{profile}`\n"
            f"- Global installed: `{report.global_installed}` (`{report.global_dir}`)\n"
            f"- Repo lock present: `{report.repo_lock_present}` (`{report.repo_lock_path}`)\n"
            f"- Current source: `{report.current_profile_source}`\n"
            f"- Lock matches current: `{report.repo_lock_matches_current}`\n"
        )
        return

    console.print("[bold blue]Meminit Org Status[/bold blue]")
    console.print(f"Root: {root_path}")
    console.print(f"Profile: {profile}")
    console.print(f"Global installed: {report.global_installed} ({report.global_dir})")
    console.print(f"Repo lock present: {report.repo_lock_present} ({report.repo_lock_path})")
    console.print(f"Current source: {report.current_profile_source}")
    console.print(f"Lock matches current: {report.repo_lock_matches_current}")
