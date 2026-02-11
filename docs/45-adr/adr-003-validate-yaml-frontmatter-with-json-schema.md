---
document_id: MEMINIT-ADR-003
type: ADR
title: Validate YAML frontmatter with JSON Schema
status: Draft
version: 0.1
last_updated: 2025-12-14
owner: GitCmurf
docops_version: 2.0
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-ADR-003
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2025-12-14
> **Type:** ADR

# MEMINIT-ADR-003: Validate YAML frontmatter with JSON Schema

- **Date decided:** 2025-12-14
- **Deciders:** Repo maintainers
- **Status:** Draft

## 1. Context & Problem Statement

DocOps governance depends on consistent, machine-readable metadata in document frontmatter. We need a precise, tool-friendly validation mechanism that is stable over time and supports good error reporting.

## 2. Decision Drivers

- Standards-based validation and tooling interoperability.
- Clear errors (including which field failed).
- Ability to enforce required fields and constrained enums (e.g., `status`).

## 3. Options Considered

- **JSON Schema validation**
  - Pros: standardized; strong tooling (`jsonschema`); good fit for “schema-as-law”.
  - Cons: YAML parsing can coerce types (dates, floats) requiring normalization.
- **Ad-hoc Python validation**
  - Pros: fully custom error messages and semantics.
  - Cons: re-invents schema, harder to share, drifts from docs.

## 4. Decision Outcome

- **Chosen option:** JSON Schema validation of YAML frontmatter.
- **Scope/Applicability:** `docs/00-governance/metadata.schema.json` validated via `SchemaValidator`.

## 5. Consequences

- Positive: a single authoritative schema and consistent enforcement.
- Negative: requires careful handling of YAML scalar coercions to avoid false positives.

## 6. Implementation Notes

- Schema file: `docs/00-governance/metadata.schema.json`
- Validator: `src/meminit/core/services/validators.py` (`SchemaValidator`)
- Checker uses schema validation on normalized metadata for known YAML-coerced fields.

## 7. Validation & Compliance

- Tests cover valid metadata, missing required fields, and type errors (with field context in messages).

## 8. Alternatives Rejected

- Full bespoke validation: rejected for interoperability and drift risk.

## 9. Supersession

- Supersedes: none
- Superseded by: none

## 10. Notes for Agents

- Keywords: JSON Schema, Draft7, YAML frontmatter
- Code anchors: `docs/00-governance/metadata.schema.json`, `src/meminit/core/services/validators.py`
