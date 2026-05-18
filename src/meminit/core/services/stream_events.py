"""Core-owned stream payload types for producer-side streaming APIs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator


def summary_data(data: dict[str, Any], *excluded_keys: str) -> dict[str, Any]:
    """Create a summary dict by copying data and removing excluded keys."""
    summary = dict(data)
    for key in excluded_keys:
        summary.pop(key, None)
    return summary


@dataclass(frozen=True)
class StreamItem:
    """A structured item emitted by a core streaming producer."""

    kind: str
    data: dict[str, Any]


@dataclass(frozen=True)
class StreamProgress:
    """A progress update emitted by a core streaming producer."""

    processed: int
    total: int | None = None
    stage: str | None = None


StreamRecord = StreamItem | StreamProgress


@dataclass
class StreamSummary:
    """Terminal summary populated by a streaming producer."""

    data: dict[str, Any] = field(default_factory=dict)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    violations: list[dict[str, Any]] = field(default_factory=list)
    advice: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class StreamingResult:
    """Core streaming result: records first, summary after consumption."""

    records: Iterator[StreamRecord]
    summary: StreamSummary
