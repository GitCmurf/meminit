from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict


def normalize_yaml_scalar_footguns(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize YAML-coerced scalars that commonly cause false positives or type drift.

    Why:
    - YAML parsers often coerce unquoted ISO dates into `datetime.date`
    - YAML parsers often coerce unquoted version-like numbers (0.1, 2.0) into floats

    Our schema expects these fields to be strings, and we prefer writing them as strings
    to keep round-trips stable and predictable.
    """

    normalized: Dict[str, Any] = dict(metadata)

    def _coerce_float_int_to_version_string(value: Any) -> Any:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return f"{value}.0"
        if isinstance(value, float):
            if value.is_integer():
                return f"{int(value)}.0"
            return str(value)
        return value

    if "last_updated" in normalized:
        value = normalized.get("last_updated")
        if isinstance(value, datetime):
            normalized["last_updated"] = value.date().isoformat()
        elif isinstance(value, date):
            normalized["last_updated"] = value.isoformat()

    for key in ("version", "docops_version"):
        if key in normalized:
            normalized[key] = _coerce_float_int_to_version_string(normalized.get(key))

    for key in list(normalized.keys()):
        if key.endswith("_version") and key not in ("version", "docops_version"):
            normalized[key] = _coerce_float_int_to_version_string(normalized.get(key))

    return normalized
