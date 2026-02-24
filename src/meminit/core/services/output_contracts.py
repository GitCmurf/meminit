"""Output contract version constants for the Meminit CLI."""

# Legacy v1 schema version — only for commands not yet migrated to format_envelope().
OUTPUT_SCHEMA_VERSION = "1.0"

# Unified v2 schema version — used by format_envelope() for all migrated commands.
OUTPUT_SCHEMA_VERSION_V2 = "2.0"

# Backward compat alias (used by check before migration).
CHECK_OUTPUT_SCHEMA_VERSION = OUTPUT_SCHEMA_VERSION_V2
