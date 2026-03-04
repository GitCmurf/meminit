---
document_id: MEMINIT-ADR-014
type: ADR
title: Templates v2 Architecture
status: Draft
version: "0.1"
last_updated: 2026-03-04
owner: Product Team
area: CORE
docops_version: "2.0"
template_type: adr-standard
template_version: "2.0"
related_ids:
  - MEMINIT-PRD-006
  - MEMINIT-SPEC-007
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-ADR-014
> **Owner:** Product Team
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2026-03-04
> **Type:** ADR

# MEMINIT-ADR-014: Templates v2 Architecture

<!-- MEMINIT_SECTION: title -->

<!-- AGENT: The title should be concise and descriptive of the decision being made. -->

- **Date decided:** 2026-03-04
- **Status:** Draft
- **Deciders:** Product Team
- **Consulted:** Engineering Team
- **Informed:** All Meminit users
- **References:** MEMINIT-PRD-006, MEMINIT-SPEC-007

## 1. Context & Problem Statement

<!-- MEMINIT_SECTION: context -->

<!-- AGENT: Describe the motivating problem, constraints, and forces. State the scope and what is explicitly out of scope. -->

Meminit v1 template system had several limitations:
- Dual syntax support (`{title}` and `{{title}}`) created confusion
- Template configuration split between `type_directories` and `templates` keys
- No stable section markers for agent orchestration
- Template resolution lacked clear precedence rules
- No security validation for template files

Given Meminit's pre-alpha status, we have an opportunity to establish clean, breaking changes without backward compatibility constraints.

Scope:
- Template resolution precedence chain
- Interpolation syntax standardization
- Section marker format for agent orchestration
- Template file validation rules
- Configuration model unification

Out of scope:
- Template content authoring guidelines
- Legacy v1 template behavior

## 2. Decision Drivers

<!-- MEMINIT_SECTION: decision_drivers -->

<!-- AGENT: List the key forces that influence the decision (e.g., latency, cost, safety, operability, compliance, UX, delivery risk). -->

- **Agent orchestration**: Need stable, parseable section structure
- **Security**: Template files must be validated before use
- **Determinism**: Template resolution must be predictable
- **Clarity**: Single syntax reduces confusion and errors
- **Pre-alpha freedom**: Breaking changes acceptable for clean architecture
- **Extensibility**: Design must support future template features

## 3. Options Considered

<!-- MEMINIT_SECTION: options -->

<!-- AGENT: For each option, capture summary, evidence, pros, cons, and risks. Present options fairly. -->

- **Option A: Continue dual syntax support**
  - Pros: Backward compatible with existing templates
  - Cons: Confusing, error-prone, harder to maintain
  - Evidence: Support requests indicate user confusion
  - Risks: Perpetuates complexity, limits future features
- **Option B: Deprecate legacy syntax gradually**
  - Pros: Allows transition period
  - Cons: More complex implementation, longer migration timeline
  - Evidence: Deprecation patterns often fail
  - Risks: Legacy patterns persist indefinitely
- **Option C: Enforce single syntax with immediate rejection**
  - Pros: Clean architecture, clear error messages, simple implementation
  - Cons: Breaking change, requires template migration
  - Evidence: Pre-alpha status allows breaking changes
  - Risks: User migration required (mitigated by migration tool)

**Chosen option:** Option C

## 4. Decision Outcome

<!-- MEMINIT_SECTION: decision -->

<!-- AGENT: Clearly state the chosen option with rationale tied to decision drivers. Include scope/applicability and status gates. -->

- **Chosen option:** Option C — Single `{{variable}}` syntax with legacy rejection
- **Why this option:**
  - Pre-alpha status permits breaking changes
  - Single syntax reduces confusion and maintenance burden
  - Clear error messages guide users to correct syntax
  - Enables future template features without legacy baggage
- **Scope/Applicability:**
  - All new template creation
  - All template validation
  - Configuration via `document_types` (replaces `type_directories`/`templates`)
- **Status gates:**
  - Draft → In Review: Migration tool available
  - In Review → Approved: All built-in templates migrated

## 5. Consequences

<!-- MEMINIT_SECTION: consequences -->

<!-- AGENT: Document positive outcomes, negative trade-offs, and any follow-up work needed. -->

- Positive:
  - Clear, single interpolation syntax
  - Stable section markers enable agent workflows
  - Template security validation prevents abuse
  - Unified `document_types` configuration simplifies setup
  - Template resolution chain is deterministic and predictable
- Negative / trade-offs:
  - Breaking change requires template migration
  - Legacy configs must be converted to `document_types`
  - Legacy placeholder syntax must be updated
- Follow-up migrations / cleanups:
  - `meminit migrate-templates` command to automate migration
  - Documentation updates for template authors
  - Migration guide for existing repositories

## 6. Implementation Notes

<!-- MEMINIT_SECTION: implementation -->

<!-- AGENT: Include implementation plan, owners, rollout strategy, and monitoring needs. -->

- Plan / milestones:
  - WP-1: Core template engine (TemplateResolver, TemplateInterpolator, SectionParser)
  - WP-2: Update new_document.py to use new services
  - WP-3: JSON output enhancements (template provenance, sections)
  - WP-4: Built-in templates (ADR, PRD, FDD)
  - WP-5: Vendored template updates
  - WP-6: Test coverage
  - WP-7: Migration tooling (`meminit migrate-templates`)
- Owners: Product Team, Engineering Team
- Backward compatibility / rollout strategy:
  - No backward compatibility (pre-alpha)
  - Legacy configs rejected with `LEGACY_CONFIG_UNSUPPORTED` error
  - Legacy syntax rejected with `INVALID_TEMPLATE_PLACEHOLDER` error
- Telemetry / monitoring to add:
  - Track template resolution source (config/convention/builtin/none)
  - Monitor validation failures (size, encoding, symlink)

## 7. Validation & Compliance

<!-- MEMINIT_SECTION: validation -->

<!-- AGENT: Specify tests, tooling checks, operational checks, and success metrics. -->

- Tests required (unit/integration/e2e):
  - Unit tests for TemplateResolver (precedence, validation)
  - Unit tests for TemplateInterpolator (syntax, legacy rejection)
  - Unit tests for SectionParser (markers, code fences, duplicates)
  - Integration tests for `meminit new` with Templates v2 output
- Tooling checks (lint/format/static analysis):
  - All templates must pass validation
  - Config must use `document_types` (not legacy keys)
- Operational checks (dashboards/alerts/runbooks):
  - Template resolution success rate
  - Validation failure rate by error type
- Success metrics or acceptance criteria:
  - 100% of new templates use `{{variable}}` syntax
  - All built-in templates include section markers
  - Migration tool converts legacy configs successfully

## 8. Alternatives Rejected

<!-- MEMINIT_SECTION: alternatives -->

<!-- AGENT: List rejected options with one-line reason each. -->

- **Dual syntax support**: Rejected due to confusion and maintenance burden
- **Gradual deprecation**: Rejected due to complexity and pre-alpha freedom
- **Keep legacy config keys**: Rejected due to configuration duplication

## 9. Supersession

<!-- MEMINIT_SECTION: supersession -->

<!-- AGENT: Track what this ADR supersedes and what supersedes it. -->

- Supersedes: None (new template system)
- Superseded by: None

## 10. Notes for Agents

<!-- MEMINIT_SECTION: agent_notes -->

<!-- AGENT: Include key entities/terms for RAG, code anchors this ADR governs, and known gaps/TODOs. -->

- Key entities/terms for RAG:
  - Templates v2, TemplateResolver, TemplateInterpolator, SectionParser
  - document_types, document_id, template resolution, section markers
  - `{{variable}}` syntax, `<!-- MEMINIT_SECTION: -->`, `<!-- AGENT: -->`
- Code anchors (paths, modules, APIs) this ADR governs:
  - `src/meminit/core/services/template_resolver.py`
  - `src/meminit/core/services/template_interpolation.py`
  - `src/meminit/core/services/section_parser.py`
  - `src/meminit/core/services/repo_config.py` (DocumentTypeConfig)
  - `src/meminit/core/use_cases/new_document.py`
  - `docops.config.yaml` (document_types configuration)
- Known gaps / TODOs:
  - Migration tool (`meminit migrate-templates`) not yet implemented
  - Legacy config rejection currently logs warning only (should raise error)

## 11. Version History

<!-- MEMINIT_SECTION: version_history -->

<!-- AGENT: Track version changes with dates, authors, and change summaries. -->

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-03-04 | Product Team | Initial draft |
