# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial repository setup.
- Directory structure following DocOps Constitution.
- Basic governance documentation.
- Development environment configuration.

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
