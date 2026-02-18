"""Observability service for structured logging and run tracking.

Per PRD N5:
- All logs go to stderr (never stdout, to avoid contaminating JSON output)
- Required fields: timestamp, run_id, operation, duration_ms, success
- Optional fields: error_code, details
- MEMINIT_LOG_FORMAT controls format (json | text)
"""

import json
import os
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Generator

from meminit.core.services.error_codes import MeminitError, ErrorCode

_current_run_id: Optional[str] = None


def get_run_id() -> str:
    """Generate or retrieve a unique run ID for this invocation."""
    return os.environ.get("MEMINIT_RUN_ID") or str(uuid.uuid4())[:8]


def get_current_run_id() -> str:
    """Get the current run ID, creating one if needed."""
    global _current_run_id
    if _current_run_id is None:
        _current_run_id = get_run_id()
    return _current_run_id


def get_log_format() -> str:
    """Get the configured log format (json or text)."""
    return os.environ.get("MEMINIT_LOG_FORMAT", "text")


def is_debug_enabled() -> bool:
    """Return True when trace-level debug logging is enabled."""
    return os.environ.get("MEMINIT_DEBUG") == "1"


def log_debug(
    operation: str,
    details: Optional[Dict[str, Any]] = None,
    run_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
) -> None:
    """Emit a trace-level debug log when MEMINIT_DEBUG=1."""
    if not is_debug_enabled():
        return
    log_event(
        operation=operation,
        success=True,
        duration_ms=duration_ms,
        details=details,
        run_id=run_id,
        level="debug",
    )


def _write_stderr(message: str) -> None:
    """Write message to stderr (never stdout)."""
    print(message, file=sys.stderr, flush=True)


def log_event(
    operation: str,
    success: bool,
    duration_ms: Optional[float] = None,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    run_id: Optional[str] = None,
    level: Optional[str] = None,
) -> None:
    """Log an operation event to stderr.

    Args:
        operation: Operation name (e.g., "document_created", "validation_failed")
        success: Whether the operation succeeded
        duration_ms: Duration in milliseconds (optional)
        error_code: Error code if operation failed (optional)
        details: Additional details (optional)
        run_id: Run ID (uses current if not provided)
        level: Optional log level/severity tag (e.g., "debug", "info", "warning", "error").
            When provided, it is included in both JSON and text logs.
    """
    entry: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "run_id": run_id or get_current_run_id(),
        "operation": operation,
        "success": success,
    }

    if level:
        entry["level"] = level

    rounded_duration: Optional[float] = None
    if duration_ms is not None:
        rounded_duration = round(duration_ms, 2)
        entry["duration_ms"] = rounded_duration

    if error_code:
        entry["error_code"] = error_code

    if details:
        entry["details"] = details

    if get_log_format() == "json":
        _write_stderr(json.dumps(entry, separators=(",", ":"), default=str))
    else:
        parts = [f"[{entry['run_id']}]", entry["timestamp"], operation]
        if level:
            parts.append(f"[{level}]")
        parts.append("OK" if success else "FAILED")
        if rounded_duration is not None:
            parts.append(f"({rounded_duration:.2f}ms)")
        if error_code:
            parts.append(f"[{error_code}]")
        if details:
            parts.append(json.dumps(details, default=str))
        _write_stderr(" ".join(parts))


@contextmanager
def log_operation(
    operation: str,
    details: Optional[Dict[str, Any]] = None,
    run_id: Optional[str] = None,
) -> Generator[Dict[str, Any], None, None]:
    """Context manager to log an operation with timing.

    Usage:
        with log_operation("document_create") as ctx:
            ctx["details"]["doc_type"] = "ADR"
            ctx["details"]["document_id"] = doc_id
        # Automatically logs success/failure with duration

    Yields a dict that can be modified to add details to the log entry.
    """
    start_time = time.monotonic()
    context: Dict[str, Any] = {"details": dict(details) if details else {}}
    error_code: Optional[str] = None

    try:
        yield context
        duration_ms = (time.monotonic() - start_time) * 1000
        log_event(
            operation=operation,
            success=True,
            duration_ms=duration_ms,
            details=context.get("details"),
            run_id=run_id,
        )
    except Exception as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        if isinstance(e, MeminitError):
            error_code = e.code.value
        else:
            error_code = ErrorCode.UNKNOWN_ERROR.value
        log_event(
            operation=operation,
            success=False,
            duration_ms=duration_ms,
            error_code=error_code,
            details=context.get("details"),
            run_id=run_id,
        )
        raise
