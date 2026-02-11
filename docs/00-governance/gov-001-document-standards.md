---
document_id: MEMINIT-GOV-001
owner: Repo Maintainers
status: Draft
version: 1.1
last_updated: 2025-12-30
title: Repository Document Standards
type: GOV
docops_version: 2.0
---

> **Document ID:** MEMINIT-GOV-001
> **Owner:** Repo Maintainers
> **Status:** Draft
> **Version:** 1.1
> **Last Updated:** 2025-12-30

# Repository Document Standards (v1.1)

These standards implement the organisation-wide **DocOps Constitution v2.0** for this repository.

---

## 1. Automation & Tooling

The validation of these standards is automated via the `meminit` CLI.

- `meminit check`: Validates directory structure, filenames, and frontmatter.
- `meminit fix`: Automatically corrects common violations (e.g., filenames, missing/invalid required frontmatter fields).

Failures in `meminit check` will block commits via pre-commit hooks.

---

## 2. Repository Prefix

By default, Meminit enforces that document IDs begin with this repository’s prefix:

`MEMINIT`

Exception (explicit namespace):

- Organisation-wide governance documents live under `docs/00-governance/org/` and use the `ORG-` prefix (e.g., `ORG-GOV-001`).
- This is intentional: those documents are designed to be re-used across multiple repos, and Meminit’s namespace model enforces prefixes per governed subtree.

Format: `REPO-TYPE-SEQ` (e.g., `MEMINIT-ADR-001`).
Note: `AREA` is a metadata tag, not part of the ID.

Example:
`MEMINIT-ADR-001`

---

## 3. AREA Registry

Valid AREA identifiers for this repository:

- `CORE` (Core logic, config, main CLI)
- `CLI` (Command line interface layer)
- `API` (API definitions)
- `AUTH` (Authentication & Authorization)
- `INGEST` (Data Ingestion)
- `DOCS` (Documentation specific logic)
- `AGENT` (Agent interaction layer)

Rules:

- Uppercase
- ASCII only
- Stable over time
- Coarse-grained domains

---

## 4. Allowed Document Types

This repository supports the document types defined in the Constitution.
Common types expected here:

- `gov` (Governance)
- `template` (Templated outlines for governed document types)
- `rfc` (RFCs)
- `strat` (Strategy)
- `plan` (Plans)
- `prd` (Product Requirements)
- `research` (Research)
- `spec` (Specs)
- `adr` (Decision Records)
- `task` (Tasks)
- `guide` (Guides/Runbooks)
- `ref` (Reference)
- `log` (Logs)

---

## 5. Directory Structure for This Repository

This repository MAY contain the following structure (only directories that are used need to exist):

```
docs/
  00-governance/  # GOV, RFC
  00-governance/templates/  # TEMPLATES
  01-indices/
  02-strategy/    # STRAT
  05-planning/    # PLAN, TASK
  08-security/    # GOV, GUIDE
  10-prd/         # PRD, RESEARCH
  20-specs/       # SPEC
  30-design/      # DESIGN
  40-decisions/   # DECISION
  45-adr/         # ADR
  50-fdd/         # FDD
  52-api/         # SPEC
  55-testing/     # TESTING
  58-logs/        # LOG
  60-runbooks/    # GUIDE
  70-devex/       # REF
  96-reference/   # REF
  99-archive/
```

Only directories that are used need to exist.

---

## 6. Metadata Requirements

All governed documents MUST include:

- Required YAML front matter (Constitution I.1)
- An auto-generated visible metadata block
- A unique Document ID
- Updated version and `last_updated` fields whenever content changes

Sidecar metadata MUST be used for non-Markdown artefacts.

---

## 7. Linking Rules

Documents MUST:

- Reference other docs by **Document ID**
- Use **relative links** within the repository
- Use **absolute GitHub links** across repositories

Example:
`See MEMINIT-ADR-001.`
`[Link](../45-adr/adr-001-use-python-for-meminit-cli.md)`

---

## 8. Workflow Expectations

- Any PR modifying APIs, config, operational behaviour, or user-facing system aspects MUST update docs.
- Documents MUST be created/updated via PR.
- Superseded documents MUST be moved to `99-archive/`.

---

## 8.1 Temporary / WIP Documents (Not Governed)

Some documents are intentionally **temporary** (working notes, scratchpads, in-progress drafts) and should not be governed by DocOps compliance checks.

Convention:

- Filename prefix `WIP-` indicates the document is **not governed**.
- `WIP-` files SHOULD be gitignored (so they are available locally for agents/humans, but not committed).

Tooling behavior:

- `meminit check` MUST skip `WIP-` documents under `docs/`.
- Repositories MAY customize this via `docops.config.yaml` (`excluded_filename_prefixes`).

## 9. Local Extensions

- **Task Files**: Task files (`type: task`) are stored in `docs/05-planning/tasks/` and are used to track human-AI shared work items. They use the statuses `Active` and `Done`.

---
