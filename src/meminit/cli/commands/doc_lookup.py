"""Document lookup commands: resolve, identify, link."""

from pathlib import Path

import click

from meminit.core.use_cases.identify_document import IdentifyDocumentUseCase
from meminit.core.use_cases.resolve_document import ResolveDocumentUseCase

from meminit.cli._helpers import command_output_handler, get_console, validate_initialized, validate_root_path
from meminit.cli.shared.output_helpers import _write_output
from meminit.cli.shared_flags import agent_repo_options
from meminit.core.services.observability import get_current_run_id
from meminit.core.services.output_formatter import format_envelope


def register(cli: click.Group) -> None:
    """Register resolve, identify, and link commands with the CLI."""

    @cli.command()
    @click.argument("document_id")
    @agent_repo_options()
    def resolve(document_id, root, format, output, include_timestamp, correlation_id):
        """Resolve a document_id to a path using the index."""
        run_id = get_current_run_id()
        root_path = Path(root).resolve()

        with command_output_handler(
            "resolve",
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
                command="resolve",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )
            validate_initialized(
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

            if format == "json":
                _write_output(
                    format_envelope(
                        command="resolve",
                        root=str(root_path),
                        success=result.path is not None,
                        extra_top_level={"document_id": document_id, "path": result.path or None},
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
            else:
                if result.path:
                    get_console().print(result.path)
                else:
                    get_console().print(f"[red]Document not found: {document_id}[/red]")
            raise SystemExit(0 if result.path else 1)

    @cli.command()
    @click.argument("path")
    @agent_repo_options()
    def identify(path, root, format, output, include_timestamp, correlation_id):
        """Identify a document by path and return its document_id."""
        run_id = get_current_run_id()
        root_path = Path(root).resolve()
        target_path = (root_path / path).resolve()

        with command_output_handler(
            "identify",
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
                command="identify",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )

            use_case = IdentifyDocumentUseCase(root_dir=str(root_path))
            result = use_case.execute(target_path)

            if format == "json":
                _write_output(
                    format_envelope(
                        command="identify",
                        root=str(root_path),
                        success=result.document_id is not None,
                        extra_top_level={"path": str(target_path), "document_id": result.document_id or None},
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
            else:
                if result.document_id:
                    get_console().print(result.document_id)
                else:
                    get_console().print(f"[red]No document_id found: {path}[/red]")
            raise SystemExit(0 if result.document_id else 1)

    @cli.command()
    @click.argument("document_id")
    @agent_repo_options()
    def link(document_id, root, format, output, include_timestamp, correlation_id):
        """Open a document in the default editor (link)."""
        run_id = get_current_run_id()
        root_path = Path(root).resolve()

        with command_output_handler(
            "link",
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
                command="link",
                include_timestamp=include_timestamp,
                run_id=run_id,
                output=output,
                correlation_id=correlation_id,
            )
            validate_initialized(
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

            if result.path:
                full_path = root_path / result.path
                click.edit(filename=full_path)
                _write_output(
                    format_envelope(
                        command="link",
                        root=str(root_path),
                        success=True,
                        extra_top_level={"document_id": document_id, "path": result.path},
                        include_timestamp=include_timestamp,
                        run_id=run_id,
                        correlation_id=correlation_id,
                    ),
                    output,
                )
            else:
                get_console().print(f"[red]Document not found: {document_id}[/red]")
                raise SystemExit(1)
