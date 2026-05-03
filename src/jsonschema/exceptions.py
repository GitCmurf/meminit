from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SchemaError(Exception):
    """Raised when a JSON Schema itself is invalid."""


@dataclass
class ValidationError(Exception):
    """Raised when an instance does not satisfy a schema."""

    message: str
    instance: Any = None
    schema: Any = None
    path: tuple[Any, ...] = ()
    validator: str | None = None
    validator_value: Any = None

    def __str__(self) -> str:
        return self.message
