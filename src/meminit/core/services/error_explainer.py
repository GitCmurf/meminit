"""Error code explanation lookups for the 'meminit explain' command.

The canonical error explanation registry (ERROR_EXPLANATIONS) and its data
classes (RemediationInfo, ErrorExplanation) are defined in error_codes.py,
co-located with the ErrorCode enum to prevent drift. This module re-exports
them for backward compatibility and provides convenience helpers.
"""
from __future__ import annotations

from meminit.core.services.error_codes import (
    ERROR_EXPLANATIONS,
    ErrorExplanation,
    RemediationInfo,
)

__all__ = [
    "ERROR_EXPLANATIONS",
    "ErrorExplanation",
    "RemediationInfo",
    "get_explanation",
    "list_codes",
]


def get_explanation(code: str) -> ErrorExplanation | None:
    """Look up the explanation for an error code string."""
    return ERROR_EXPLANATIONS.get(code)


def list_codes() -> list[str]:
    """Return all known error code values, sorted."""
    return sorted(ERROR_EXPLANATIONS.keys())
