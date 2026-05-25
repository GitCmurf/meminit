# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Protocol asset governance:** `meminit protocol check` and `meminit protocol sync` commands
  for drift detection and remediation of governed assets (AGENTS.md, SKILL.md, scripts).
- **Templates v2:** New template system with section markers (`<!-- MEMINIT_SECTION: ... -->`)
  and agent prompts for machine-fillable content.
- **NDJSON streaming:** Large output support via `--format ndjson` for agent-friendly
  streaming (see [MEMINIT-SPEC-011](docs/20-specs/spec-011-ndjson-streaming-contract.md)).
- **Incremental cache:** Faster `meminit index` with namespace-aware caching and change detection.
- **Catalog and kanban artifacts:** `meminit index --output-catalog --output-kanban` generates
  markdown catalog and HTML kanban board with XSS sanitization.
- **Project state queue:** `meminit state set/list/next/blockers` for deterministic work item
  selection with dependency management and multi-agent routing.
- **Tag-triggered release workflow:** GitHub Actions workflow for automated PyPI publishing
  via OIDC trusted publishing.
- **Secret scanning:** gitleaks integration in pre-commit and CI for automated credential detection.

### Changed

- Normalized state-related public error codes to the `STATE_*` convention:
  `STATE_YAML_MALFORMED`, `STATE_SCHEMA_VIOLATION`, and
  `STATE_INVALID_FILTER_VALUE` replace the previous mixed-prefix names. No
  compatibility aliases are retained before the first stable release.
- Output contract v3: All commands now use unified JSON envelope with
  `output_schema_version: "3.0"`, standardized error/violation/advice structure,
  and run_id correlation tokens.
- Brownfield migration: `meminit scan --plan` generates deterministic plan artifacts,
  and `meminit fix --plan <PLAN_PATH>` applies plan-driven changes for safer migrations.
- **Breaking:** Legacy placeholder syntax `{title}`, `<REPO>`, `<SEQ>` is now rejected.
  Only `{{variable}}` syntax is supported.

### Fixed

- Targeted `check` now honors exclusions consistently for broad glob inputs (for example `docs/**/*.md`) and non-canonical paths.
- Improved portability and reliability of `new` command error/lock handling and deterministic creation edge cases.
- Template placeholder syntax: Fixed 112 malformed `{ { variable } }` placeholders across 16 template files.

### Removed

- Legacy `_apply_common_template_substitutions()` function (Templates v1 superseded).

## [0.2.0] - 2026-02-20

### Added

- `meminit new` command for governed document creation with schema-aware frontmatter generation, template rendering, and deterministic ID support.
- `meminit adr new` alias flow aligned with `new` initialization/safety checks.
- Structured `meminit check --format json` v2 output envelope for check commands, including grouped violations/warnings and operational counters (`files_checked`, `files_passed`, `files_failed`, `missing_paths_count`, `schema_failures_count`, `warnings_count`, `violations_count`, `files_with_warnings`, `files_outside_docs_root_count`, `checked_paths_count`).

### Changed

- `check` path handling now normalizes/canonicalizes targeted file matches before namespace resolution, exclusion checks, and validation.
- `check --quiet` behavior now stays silent on successful and warning-only runs.
- Repository initialization validation now requires `docops.config.yaml` to be a regular file (not directory/symlink) before `check`/`new` command execution.

### Fixed

- Targeted `check` now honors exclusions consistently for broad glob inputs (for example `docs/**/*.md`) and non-canonical paths.
- Improved portability and reliability of `new` command error/lock handling and deterministic creation edge cases.
