"""Use case for the 'meminit capabilities' command.

Returns a deterministic capability descriptor derived from code-level
registrations — no filesystem scanning required.
"""
from __future__ import annotations

from typing import Any

from meminit.core.services.versioning import get_cli_version


CAPABILITIES_VERSION = "1.0"


class CapabilitiesUseCase:
    """Build the capabilities descriptor for the current CLI build."""

    def execute(self) -> dict[str, Any]:
        from meminit.cli.shared_flags import _CAPABILITIES_REGISTRY
        from meminit.core.services.error_codes import ErrorCode
        from meminit.core.services.output_contracts import OUTPUT_SCHEMA_VERSION_V3

        commands = sorted(
            _CAPABILITIES_REGISTRY.values(), key=lambda c: c["name"]
        )

        return {
            "capabilities_version": CAPABILITIES_VERSION,
            "cli_version": get_cli_version(),
            "output_schema_version": OUTPUT_SCHEMA_VERSION_V3,
            "commands": commands,
            "output_formats": ["json", "md", "text"],
            "global_flags": sorted(
                [
                    {
                        "flag": "--format",
                        "type": "choice",
                        "values": ["text", "json", "md"],
                        "default": "text",
                        "description": "Output format",
                    },
                    {
                        "flag": "--correlation-id",
                        "type": "string",
                        "description": "Caller-supplied orchestration trace token",
                    },
                    {
                        "flag": "--include-timestamp",
                        "type": "boolean",
                        "default": False,
                        "description": "Include ISO 8601 UTC timestamp in JSON output",
                    },
                    {
                        "flag": "--output",
                        "type": "string",
                        "description": "Write output to file instead of stdout",
                    },
                ],
                key=lambda f: f["flag"],
            ),
            "features": {
                "correlation_id": True,
                "include_timestamp": True,
                "structured_output": True,
                "explain": True,
                "capabilities": True,
                "streaming": False,
                "graph_index": False,
            },
            "error_codes": sorted(code.value for code in ErrorCode),
        }
