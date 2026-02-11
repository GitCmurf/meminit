---
document_id: ORG-GOV-001
owner: DocOps Working Group
status: Draft
version: 2.0
last_updated: 2025-12-11
title: DocOps Constitution
type: GOV
docops_version: 2.0
---

# DocOps Constitution v2.0 (Draft)

> **Status:** DRAFT for Review  
> **Supersedes:** v1.3

## Preamble
This Constitution defines the immutable laws of documentation for the organisation. It prioritizes **machine-readability**, **long-term stability**, and **agent-interoperability**.

---

# Article I — The Document Identifier (ID)

## I.1 Immutability Principle
The Document ID is the **permanent, invariant primary key** of a document.
It MUST NOT change when the document is renamed, moved, or updated.
It MUST NOT contain mutable attributes (like "Area" or "Status").

## I.2 ID Format
The ID format is:

```
<REPO_PREFIX>-<TYPE>-<SEQ>
```

* **REPO_PREFIX**: 3-10 char uppercase code unique to the repository (e.g., `MEMINIT`, `OZYS`).
* **TYPE**: Standard document type code (e.g., `ADR`, `PRD`, `TASK`).
* **SEQ**: 3-digit zero-padded integer sequence (e.g., `001`, `042`).

**Examples:**

* `MEMINIT-ADR-001` (Valid)
* `OZYS-PRD-023` (Valid)
* `MEMINIT-INGEST-ADR-001` (INVALID - Contains mutable 'Area')

## I.3 Filename Convention
Filenames MUST be ASCII and SHOULD be kebab-case.
Filenames MAY (and are **strongly encouraged** to) include the ID but are NOT REQUIRED to include the `REPO_PREFIX` whilst they are saved within that repository.

**Recommended Patterns:**

* `0001-redis-cache.md` (ADR style)
* `prd-001-login-flow.md` (Type-Seq-Slug style)
* `ADR-001.md` (Explicit ID style, excluding `REPO_PREFIX`)

**Constraint:**
Tools MUST be able to map `document_id` to the file path via an index. The filename is for human convenience.

---

# Article II — Metadata Schema

## II.1 Standard Frontmatter
Every governed document MUST contain the following YAML frontmatter.
Undefined fields MUST be represented by `null` or `~` (YAML null), or omitted if optional.

```yaml
document_id: <ID>           # Immutable. Matches regex.
type: <TYPE>                # Immutable. Matches ID Type.
title: "<Title String>"     # Human readable title.
status: <Status>            # Workflow state.
owner: <Owner>              # Responsible person/team.
version: <Major.Minor>      # Semantic version.
last_updated: <YYYY-MM-DD>  # ISO 8601 Date.
docops_version: <Version>   # Constitution version.
```

## II.2 Recommended Context Fields
```yaml
area: <Area>                # Mutable. The functional domain.
description: "<String>"     # Summary.
template_type: "<ID>"       # e.g. "adr-minimal"
template_version: "<Ver>"   # e.g. "1.0"
keywords: [<List>]          # Controlled vocabulary.
tags: [<List>]              # Folksonomy.
superseded_by: <ID>         # If status is Superseded.
related_ids: [<List>]       # Explicit ID links.
```

## II.3 Controlled Vocabularies

* **Status:** `Draft`, `In Review`, `Approved`, `Superseded`. (`Deprecated` reserved).
* **Type:** Defined in Article III.
* **Area:** Defined in Repository Configuration (`docops.config.yaml`). Represents the **Functional Domain** (mutable grouping).

---

# Article III — Taxonomy

## III.1 Core Types (Immutable)
These types have fixed semantics across the organisation.

| Type Code | Full Name | Purpose |
| :--- | :--- | :--- |
| **Governance** | | |
| `GOV` | Governance | Rules, Standards, Policies. |
| `RFC` | Request for Comments | Proposals for change. |
| **Strategy** | | |
| `STRAT` | Strategy | High-level vision and goals. |
| **Product** | | |
| `PRD` | Product Requirements | User needs and functional reqs. |
| `RESEARCH` | Research & Insights | User feedback, market analysis. |
| **Technical** | | |
| `SPEC` | Specification | Detailed engineering design. |
| `ADR` | Decision Record | Immutable technical choices. |
| **Execution** | | |
| `PLAN` | Plan | Roadmaps, Epics, Backlogs. |
| `TASK` | Task List | Work items (Human/AI). |
| **Knowledge** | | |
| `GUIDE` | Guide / Runbook | How-to, Procedures, Tutorials. |
| `REF` | Reference | Encyclopedic info, Glossaries. |
| **Records** | | |
| `LOG` | Log / Record | Point-in-time records. |

## III.2 Local Types (Extensible)
Repositories MAY define local types in `docops.config.yaml`.
Examples: `RUNBOOK`, `MIGRATION`, `MINUTES`.

---

# Article IV — Versioning & Lifecycle

## IV.1 Semantic Versioning

* **Major (1.0):** Significant change or Approval.
* **Minor (1.1):** Clarification or Draft iteration.

## IV.2 Supersession
When a document is replaced:

1. Status -> `Superseded`.
2. Frontmatter `superseded_by: <New_ID>`.
3. Moved to `docs/99-archive/`.

---

# Article V — Directory Structure

Directories are organizational conveniences, NOT part of the document identity.
However, specific Types SHOULD reside in specific directories by default.

## V.1 Default Mappings

Tools MAY warn if a document is misplaced, but MUST NOT fail validation based on directory alone.

### Core Type Mappings (Normative Defaults)
* `00-governance/` -> `GOV`, `RFC`
* `02-strategy/` -> `STRAT`
* `05-planning/` -> `PLAN`, `TASK`
* `08-security/` -> `GOV`, `GUIDE` (Security Policies & Runbooks)
* `10-prd/` -> `PRD`, `RESEARCH`
* `20-specs/` -> `SPEC`
* `45-adr/` -> `ADR`
* `52-api/` -> `SPEC` (Internal API Contracts)
* `58-logs/` -> `LOG` (Outputs/Records)
* `60-runbooks/` -> `GUIDE`
* `70-devex/` -> `REF` (Glossaries, Cheat Sheets)
* `96-reference/` -> `REF` (Third-party Reference)

### Local Type Mappings (Repository-Specific Examples)
Local types are defined by the repository (e.g., via configuration and templates) and are not organization-wide normative.

* `01-indices/` -> `INDEX` (Local)
* `30-design/` -> `DESIGN` (Local)
* `40-decisions/` -> `DECISION` (Local)
* `50-fdd/` -> `FDD` (Local)
* `55-testing/` -> `TESTING` (Local)

## V.2 Repository-Level Conventions (Informational)
For reference, key repository directories:

* `docs/` — All documented artifacts (governed by this taxonomy).
* `src/` — Source code (not governed by document taxonomy).
* `tests/` — Test code (not governed by document taxonomy).

---
