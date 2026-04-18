"""Shared deterministic helpers for diagnostic payloads.

These helpers keep warning/advice ordering consistent anywhere Meminit emits
or persists structured diagnostics.
"""

from __future__ import annotations

from typing import Any


def recursively_sort_keys(obj: Any) -> Any:
    """Recursively sort dictionary keys for deterministic output."""
    if isinstance(obj, dict):
        return {k: recursively_sort_keys(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [recursively_sort_keys(item) for item in obj]
    return obj


def line_sort_key(line: Any) -> tuple[int, Any]:
    """Sort numeric lines first, missing lines second, non-numeric last."""
    if line is None:
        return (1, 0.0)
    try:
        return (0, float(line))
    except (TypeError, ValueError):
        return (2, str(line))


def strip_none_line(item: dict[str, Any]) -> dict[str, Any]:
    """Remove ``line`` when its value is ``None`` to match JSON contracts."""
    if "line" in item and item.get("line") is None:
        cleaned = dict(item)
        cleaned.pop("line", None)
        return cleaned
    return item


def sort_warnings(warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort warnings by ``(path, line, code, message)``."""
    cleaned = [strip_none_line(w) for w in warnings]

    def _key(warning: dict[str, Any]) -> tuple[Any, ...]:
        return (
            warning.get("path", ""),
            *line_sort_key(warning.get("line")),
            warning.get("code", ""),
            warning.get("message", ""),
        )

    return sorted(cleaned, key=_key)


def sort_advice(advice: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort advice by ``(code, message)``."""

    def _key(item: dict[str, Any]) -> tuple[str, str]:
        return (item.get("code", ""), item.get("message", ""))

    return sorted(advice, key=_key)


def canonicalize_warning_list(warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return warnings with canonical array order and nested dict ordering."""
    return [recursively_sort_keys(w) for w in sort_warnings(warnings)]


def canonicalize_advice_list(advice: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return advice with canonical array order and nested dict ordering."""
    return [recursively_sort_keys(item) for item in sort_advice(advice)]
