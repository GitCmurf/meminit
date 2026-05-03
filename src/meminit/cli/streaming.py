"""Shared NDJSON streaming support for CLI adapters."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol, TextIO

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.exit_codes import exit_code_for_error
from meminit.core.services.output_formatter import (
    canonical_json_dumps,
    normalize_correlation_id,
)
from meminit.core.services.safe_fs import ensure_safe_write_path

STREAM_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class SummaryPayload:
    """Payload returned by a streaming producer."""

    data: dict[str, Any] = field(default_factory=dict)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    violations: list[dict[str, Any]] = field(default_factory=list)
    advice: list[dict[str, Any]] = field(default_factory=list)


class StreamingProducer(Protocol):
    """Callable shape for a streaming producer."""

    def __call__(self, emit: "StreamEmitter") -> SummaryPayload: ...


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
            header["started_at"] = "1970-01-01T00:00:00Z"
        self._write(header)

    @property
    def counts(self) -> dict[str, int]:
        """Return item counts by kind."""
        return dict(sorted(self._counts.items()))

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
        error = {"code": error_code.value, "message": message}
        if details:
            error["details"] = details
        record = self._base_record("error")
        record["error"] = error
        self._closed = True
        self._write(record)

    def emit_summary(self, summary: SummaryPayload) -> None:
        self._assert_open()
        record = self._base_record("summary")
        record.update(
            {
                "success": True,
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
            raise AssertionError("cannot emit records after terminal record")


def streaming_output_handler(
    *,
    command: str,
    producer: StreamingProducer,
    output: str | None,
    include_timestamp: bool,
    run_id: str,
    root_path: Path | None = None,
    correlation_id: str | None = None,
) -> None:
    """Run a streaming producer and write a terminal summary or error."""
    stream = _open_stream(output=output, root_path=root_path)
    close_stream = stream is not sys.stdout
    emitter = StreamEmitter(
        command=command,
        run_id=run_id,
        root=root_path,
        stream=stream,
        correlation_id=correlation_id,
        include_timestamp=include_timestamp,
    )
    try:
        emitter.emit_summary(producer(emitter))
    except MeminitError as exc:
        emitter.emit_error(exc.code, exc.message, exc.details)
        raise SystemExit(exit_code_for_error(exc.code)) from exc
    except Exception as exc:
        emitter.emit_error(
            ErrorCode.STREAM_PRODUCER_FAILED,
            "Streaming producer failed.",
            {"exception": exc.__class__.__name__},
        )
        raise SystemExit(exit_code_for_error(ErrorCode.STREAM_PRODUCER_FAILED)) from exc
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


def _open_stream(*, output: str | None, root_path: Path | None) -> TextIO:
    if not output:
        return sys.stdout
    out_path = Path(output)
    if root_path is not None:
        ensure_safe_write_path(root_dir=root_path, target_path=out_path.resolve())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return out_path.open("w", encoding="utf-8")
