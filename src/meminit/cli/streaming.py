"""Shared NDJSON streaming support for CLI adapters."""

from __future__ import annotations

import signal
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import FrameType
from typing import Any, Callable, Protocol, TextIO

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.exit_codes import EX_CANTCREAT, exit_code_for_error
from meminit.core.services.observability import log_operation
from meminit.core.services.output_formatter import (
    canonical_json_dumps,
    normalize_correlation_id,
)
from meminit.core.services.path_utils import is_safe_cli_output_path

STREAM_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class SummaryPayload:
    """Payload returned by a streaming producer."""

    data: dict[str, Any] = field(default_factory=dict)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    violations: list[dict[str, Any]] = field(default_factory=list)
    advice: list[dict[str, Any]] = field(default_factory=list)


class StreamingProducer(Protocol):
    """Protocol implemented by streaming producers."""

    def produce(self, emit: "StreamEmitter") -> SummaryPayload: ...


@dataclass(frozen=True)
class CallableStreamingProducer:
    """Adapter for small CLI-local producers while use cases gain stream APIs."""

    # TODO(MEMINIT-PLAN-014): remove once command use cases expose stream()
    # producers directly and CLI closures are no longer needed.
    func: Callable[["StreamEmitter"], SummaryPayload]

    def produce(self, emit: "StreamEmitter") -> SummaryPayload:
        return self.func(emit)


class StreamEmitter:
    """Emit deterministic SPEC-011 NDJSON records."""

    def __init__(
        self,
        *,
        command: str,
        run_id: str,
        stream: TextIO,
        root: Path | None = None,
        correlation_id: str | None = None,
        include_timestamp: bool = False,
    ) -> None:
        self._command = command
        self._stream = stream
        self._sequence = 0
        self._closed = False
        self._counts: dict[str, int] = {}
        header = self._base_record("header")
        header["run_id"] = run_id
        cid = normalize_correlation_id(correlation_id)
        if cid is not None:
            header["correlation_id"] = cid
        if root is not None:
            header["root"] = root.resolve().as_posix()
        if include_timestamp:
            header["started_at"] = (
                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            )
        self._write(header)

    @property
    def counts(self) -> dict[str, int]:
        """Return item counts by kind."""
        return dict(sorted(self._counts.items()))

    @property
    def closed(self) -> bool:
        """Return whether a terminal record has already been emitted."""
        return self._closed

    def emit_item(self, kind: str, data: dict[str, Any]) -> None:
        self._assert_open()
        self._counts[kind] = self._counts.get(kind, 0) + 1
        record = self._base_record("item")
        record.update({"kind": kind, "data": data})
        self._write(record)

    def emit_progress(
        self, *, processed: int, total: int | None = None, stage: str | None = None
    ) -> None:
        self._assert_open()
        record = self._base_record("progress")
        record["processed"] = processed
        if total is not None:
            record["total"] = total
        if stage:
            record["stage"] = stage
        self._write(record)

    def emit_error(
        self,
        error_code: ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self._assert_open()
        error: dict[str, Any] = {"code": error_code.value, "message": message}
        if details:
            error["details"] = details
        record = self._base_record("error")
        record["error"] = error
        self._closed = True
        self._write(record)

    def emit_summary(self, summary: SummaryPayload, *, success: bool = True) -> None:
        self._assert_open()
        record = self._base_record("summary")
        record.update(
            {
                "success": success,
                "data": summary.data,
                "warnings": summary.warnings,
                "violations": summary.violations,
                "advice": summary.advice,
                "counts": self.counts,
            }
        )
        self._closed = True
        self._write(record)

    def _base_record(self, record_type: str) -> dict[str, Any]:
        return {
            "stream_schema_version": STREAM_SCHEMA_VERSION,
            "record_type": record_type,
            "command": self._command,
            "sequence": self._sequence,
        }

    def _write(self, record: dict[str, Any]) -> None:
        self._stream.write(canonical_json_dumps(record) + "\n")
        self._stream.flush()
        self._sequence += 1

    def _assert_open(self) -> None:
        if self._closed:
            raise RuntimeError("cannot emit records after terminal record")


def streaming_output_handler(
    *,
    command: str,
    producer: StreamingProducer,
    output: str | None,
    include_timestamp: bool,
    run_id: str,
    root_path: Path | None = None,
    correlation_id: str | None = None,
    success: bool = True,
) -> None:
    """Run a streaming producer and write a terminal summary or error."""
    stream, close_stream, open_error, exit_code = _open_stream(output=output)
    previous_handlers = {}
    emitter: StreamEmitter | None = None
    try:
        emitter = StreamEmitter(
            command=command,
            run_id=run_id,
            root=root_path,
            stream=stream,
            correlation_id=correlation_id,
            include_timestamp=include_timestamp,
        )
        if open_error is not None:
            emitter.emit_error(
                open_error["code"], open_error["message"], open_error.get("details")
            )
            raise SystemExit(exit_code)
        previous_handlers = _register_interrupt_handlers(emitter)
        with log_operation(
            operation=f"{command}_stream",
            details={"stream_schema_version": STREAM_SCHEMA_VERSION},
            run_id=run_id,
        ) as log_ctx:
            summary = producer.produce(emitter)
            log_ctx["details"]["counts"] = emitter.counts
        emitter.emit_summary(summary, success=success)
    except MeminitError as exc:
        if emitter is None:
            raise
        emitter.emit_error(exc.code, exc.message, exc.details)
        raise SystemExit(exit_code_for_error(exc.code)) from exc
    except SystemExit:
        raise
    except Exception as exc:
        if emitter is None:
            raise
        emitter.emit_error(
            ErrorCode.STREAM_PRODUCER_FAILED,
            "Streaming producer failed.",
            {"exception": exc.__class__.__name__},
        )
        raise SystemExit(exit_code_for_error(ErrorCode.STREAM_PRODUCER_FAILED)) from exc
    finally:
        _restore_interrupt_handlers(previous_handlers)
        if close_stream:
            stream.close()


def write_ndjson_error(
    *,
    command_name: str,
    error: MeminitError,
    output: str | None,
    include_timestamp: bool,
    run_id: str,
    root_path: Path | None = None,
    correlation_id: str | None = None,
) -> None:
    """Emit a single terminal NDJSON error record."""
    stream, close_stream, open_error, exit_code = _open_stream(output=output)
    try:
        emitter = StreamEmitter(
            command=command_name,
            root=root_path,
            run_id=run_id,
            stream=stream,
            correlation_id=correlation_id,
            include_timestamp=include_timestamp,
        )
        if open_error is not None:
            emitter.emit_error(
                open_error["code"], open_error["message"], open_error.get("details")
            )
            raise SystemExit(exit_code)
        emitter.emit_error(error.code, error.message, error.details)
    finally:
        if close_stream:
            stream.close()


def unsupported_ndjson(command: str, message: str) -> MeminitError:
    """Build the standard unsupported-streaming error."""
    return MeminitError(
        ErrorCode.STREAM_UNSUPPORTED_FORMAT,
        message,
        details={"command": command, "format": "ndjson"},
    )


def _open_stream(
    *, output: str | None
) -> tuple[TextIO, bool, dict[str, Any] | None, int | None]:
    if not output:
        return sys.stdout, False, None, None
    out_path = Path(output)
    if not is_safe_cli_output_path(out_path):
        return (
            sys.stdout,
            False,
            {
                "code": ErrorCode.PATH_ESCAPE,
                "message": f"Output path is considered unsafe: {output}",
                "details": {"output_path": output},
            },
            exit_code_for_error(ErrorCode.PATH_ESCAPE),
        )
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        return out_path.open("w", encoding="utf-8"), True, None, None
    except OSError as exc:
        return (
            sys.stdout,
            False,
            {
                "code": ErrorCode.UNKNOWN_ERROR,
                "message": f"Failed to write output file: {output}",
                "details": {"output_path": output, "reason": str(exc)},
            },
            EX_CANTCREAT,
        )

def _register_interrupt_handlers(
    emitter: StreamEmitter,
) -> dict[signal.Signals, Any]:
    previous: dict[signal.Signals, Any] = {}

    def handle(signum: int, _frame: FrameType | None) -> None:
        if not emitter.closed:
            emitter.emit_error(
                ErrorCode.STREAM_INTERRUPTED,
                "Streaming output interrupted.",
                {"signal": signum},
            )
        raise SystemExit(128 + signum)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            previous[sig] = signal.getsignal(sig)
            signal.signal(sig, handle)
        except (ValueError, OSError, RuntimeError):
            previous.pop(sig, None)
    return previous


def _restore_interrupt_handlers(
    previous: dict[signal.Signals, Any],
) -> None:
    for sig, handler in previous.items():
        try:
            signal.signal(sig, handler)
        except (ValueError, OSError, RuntimeError):
            pass
