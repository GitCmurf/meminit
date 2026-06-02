"""Document resolution commands (resolve, identify, link)."""

from pathlib import Path

import click

from meminit.core.use_cases.resolve_document import ResolveDocumentUseCase
from meminit.core.use_cases.identify_document import IdentifyDocumentUseCase
from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.output_formatter import format_envelope

from meminit.cli._helpers import command_output_handler, validate_root_path
from meminit.cli.shared.output_helpers import _write_output, maybe_capture
from meminit.cli.shared_flags import agent_repo_options


def register(cli: click.Group) -> None:
    """Register the document resolution commands with the CLI."""

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
            from meminit.cli._helpers import get_console

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
            "identify",
            format,
            output,
            include_timestamp,
            run_id,
            root_path,
            correlation_id=correlation_id,
        ):
            from meminit.cli._helpers import get_console

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
            "link",
            format,
            output,
            include_timestamp,
            run_id,
            root_path,
            correlation_id=correlation_id,
        ):
            from meminit.cli._helpers import get_console

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
                normalized_path = result.path.replace("\\", "/") if result.path else None
                _write_output(
                    format_envelope(
                        command="link",
                        root=str(root_path),
                        success=True,
                        data={
                            "document_id": document_id,
                            "link": f"[{document_id}]({normalized_path})" if normalized_path else None,
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