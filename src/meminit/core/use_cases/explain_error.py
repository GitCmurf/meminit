"""Use case for the 'meminit explain' command."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from meminit.core.services.error_codes import ERROR_EXPLANATIONS, ErrorExplanation, ErrorCode


class ExplainErrorUseCase:
    """Look up and return explanation metadata for a given error code."""

    def list_codes(self) -> List[Dict[str, str]]:
        """Return summary info for all known error codes, sorted by code."""
        results = []
        for explanation in sorted(ERROR_EXPLANATIONS.values(), key=lambda e: e.code):
            results.append({
                "code": explanation.code,
                "category": explanation.category,
                "summary": explanation.summary,
            })
        return results

    def explain(self, code: str) -> Optional[Dict[str, Any]]:
        """Return the full explanation for a given error code string.

        Returns None if the code is not recognized.
        """
        explanation = ERROR_EXPLANATIONS.get(code)
        if explanation is None:
            return None
        return asdict(explanation)
