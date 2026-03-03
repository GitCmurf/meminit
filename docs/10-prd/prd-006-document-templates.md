---
document_id: MEMINIT-PRD-006
type: PRD
title: Document Templates v2 — Content Archetypes for Human & Machine Authoring
status: In Review
version: "1.0"
last_updated: 2026-03-02
owner: GitCmurf
docops_version: "2.0"
area: DOCS
description: "Defines a template contract for meminit new that produces deterministic, agent-friendly document bodies: stable section IDs, explicit placeholders, and embedded prompt guidance. Specifies backward-compatible evolution from templates v1 to a unified document_types schema with built-in fallback templates."
keywords:
  - templates
  - archetypes
  - document-types
  - standardization
  - content
  - new
  - agents
  - architext
  - machine-authoring
  - scaffolding
related_ids:
  - MEMINIT-PLAN-003
  - MEMINIT-STRAT-001
  - MEMINIT-PRD-002
  - MEMINIT-PRD-003
  - MEMINIT-PRD-004
  - MEMINIT-PRD-005
  - MEMINIT-SPEC-004
  - ORG-GOV-001
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-PRD-006
> **Owner:** GitCmurf
> **Status:** In Review
> **Version:** 1.0
> **Last Updated:** 2026-03-02
> **Type:** PRD
> **Area:** DOCS

<!-- MEMINIT_SECTION: metadata_block -->

<!-- AGENT: This metadata block follows the standard Meminit format. Preserve this structure in all generated documents. -->

---

# PRD: Document Templates v2 — Content Archetypes for Human & Machine Authoring

<!-- MEMINIT_SECTION: title -->

<!-- AGENT: The title follows the format "PRD: <Feature> — <Tagline>". The tagline should communicate the core value proposition in under 10 words. -->

---

## Table of Contents

<!-- MEMINIT_SECTION: toc -->

<!-- AGENT: Generate a table of contents with anchor links to all numbered sections. Ensure all level-2 headings (##) are included. -->

1. [Executive Summary](#1-executive-summary)
   1.1 [TL;DR](#11-tldr)
   1.2 [Before vs After](#12-before-vs-after)
   1.3 [Key Deliverables](#13-key-deliverables)
   1.4 [Value Proposition](#14-value-proposition)
   1.5 [Success Definition](#15-success-definition)
   1.6 [Visual Architecture Diagram](#16-visual-architecture-diagram)
   1.7 [Quick-Start Guide](#17-quick-start-guide)
2. [Changelog](#2-changelog)
3. [Current State Analysis](#3-current-state-analysis)
4. [Problem Statement](#4-problem-statement)
5. [Goals, Non-Goals, and Success Metrics](#5-goals-non-goals-and-success-metrics)
   5.1 [Goals](#51-goals)
   5.2 [Non-Goals](#52-nongoals)
   5.3 [Success Metrics](#53-success-metrics)
   5.4 [Key Architectural Decisions](#54-key-architectural-decisions)
6. [Personas and Primary Use Cases](#6-personas-and-primary-use-cases)
7. [Proposed Solution](#7-proposed-solution)
8. [Requirements](#8-requirements)
9. [Template Contract (Markdown Spec)](#9-template-contract-markdown-spec)
10. [Configuration Spec (docops.config.yaml)](#10-configuration-spec-docopsconfigyaml)
11. [Agent Orchestrator Integration Guide](#11-agent-orchestrator-integration-guide)
12. [Deliverable Implementation Plan (Agent-Executable)](#12-deliverable-implementation-plan-agent-executable)
13. [Acceptance Criteria](#13-acceptance-criteria)
14. [Test Plan](#14-test-plan)
15. [Rollout and Migration](#15-rollout-and-migration)
16. [Security and Safety](#16-security-and-safety)
17. [Risks and Mitigations](#17-risks-and-mitigations)
18. [Resolved Design Questions](#18-resolved-design-questions)
19. [Future Scope (Deferred)](#19-future-scope-deferred)
20. [Related Documents](#20-related-documents)
21. [Appendix A: Canonical Content Inventory (Archetypes)](#21-appendix-a-canonical-content-inventory-archetypes)
22. [Appendix B: Requirements Traceability Matrix](#22-appendix-b-requirements-traceability-matrix)
23. [Appendix C: Error Scenarios and Recovery](#23-appendix-c-error-scenarios-and-recovery)
24. [Appendix D: Test Fixtures Specification](#24-appendix-d-test-fixtures-specification)

---

> **EXECUTIVE SUMMARY**
>
> **Decision:** Approve Templates v2 implementation
>
> **What:** Template system evolution from v1 to v2
>
> - Adds stable section IDs for agent orchestration
> - Unifies config under `document_types` schema
> - Ships built-in fallback templates (ADR/PRD/FDD)
> - Preserves 100% backward compatibility
>
> **Impact:**
>
> - Agent error rate: 15-20% → <2% (90%+ reduction)
> - Config reduction: 50% (two keys → one schema)
> - No-config repos: Generic skeleton → meaningful scaffold
>
> **Investment:** 8 work packages, phased rollout
> **Risk:** Low - backward compatible, incremental delivery
>
> **Recommendation: APPROVE**

---

## 1. Executive Summary

<!-- MEMINIT_SECTION: executive_summary -->

<!-- AGENT: Write a 2-3 sentence summary. What is being built, for whom, and why now? Include quantified impact if possible. -->

### 1.1 TL;DR

**What's changing:** Meminit's template system evolves from a simple placeholder-replacement mechanism (v1) to a deterministic, agent-friendly contract (v2) with stable section identifiers (`<!-- MEMINIT_SECTION: id -->`), unified `document_types` configuration, embedded agent guidance prompts, and built-in fallback templates — shipped across 8 work packages as backward-compatible PRs.

**Why now:** Agentic orchestrators need predictable, parseable document scaffolds to reliably generate governed documentation. Today, agents must parse headings with regex, producing an estimated ~15-20% structural error rate (based on manual review of agent-generated documents across early adopter repos). Templates v2 eliminates this class of failure entirely.

**Impact on key personas:**

- **Human Authors**: Get pre-structured scaffolds with guidance prompts, reducing blank-page syndrome and structural drift (~30 min saved per document)
- **Agent Orchestrators**: Receive stable section IDs via JSON output, eliminating regex heuristics and reducing estimated error rate from ~15-20% to <2% (projected 90%+ reduction)
- **Repo Owners**: Configure document types with a single `document_types` block instead of two separate keys, achieving 50% config reduction while preserving full backward compatibility

### 1.2 Before vs After

<!-- MEMINIT_SECTION: before_vs_after -->

| Aspect                     | Before (Templates v1)                   | After (Templates v2)                                        |
| -------------------------- | --------------------------------------- | ----------------------------------------------------------- |
| **Section Identification** | Agents parse headings (brittle)         | Stable `<!-- MEMINIT_SECTION: id -->` markers               |
| **Template Discovery**     | Config-only or generic skeleton         | Config → Convention → Built-in → Skeleton                   |
| **Configuration**          | Split: `type_directories` + `templates` | Unified: `document_types` (optional) + legacy support       |
| **Agent Guidance**         | None                                    | Embedded `<!-- AGENT: ... -->` prompts                      |
| **JSON Output**            | V2 envelope exists, but no template provenance/sections | Includes `data.template.source`, `data.template.sections`, `data.template.content_preview` |
| **No-Config Experience**   | Generic skeleton                        | Type-specific built-in templates                            |
| **Interpolation Syntax**   | `{title}`, `<REPO>` (inconsistent)      | `{{title}}`, `{{repo_prefix}}` (preferred) + legacy support |

### 1.3 Key Deliverables

<!-- MEMINIT_SECTION: key_deliverables -->

1. **Template Contract Spec:** Formal definition of section markers, placeholders, and agent guidance blocks
2. **`document_types` Config Schema:** Optional unified configuration (backward compatible)
3. **Template Resolver Service:** Deterministic precedence chain (config → convention → built-in → skeleton)
4. **Built-in Templates:** ADR, PRD, FDD templates with section markers and agent guidance
5. **Enhanced JSON Output:** Orchestrator-friendly response with template provenance and section inventory

### 1.4 Value Proposition

<!-- MEMINIT_SECTION: value_proposition -->

<!-- AGENT: Quantify the value for each persona. Use concrete numbers where possible. -->

| Persona                | Before Templates v2                              | After Templates v2                         | Time Saved                                     |
| ---------------------- | ------------------------------------------------ | ------------------------------------------ | ---------------------------------------------- |
| **Human Author**       | Copy/paste from old docs, structural drift       | Pre-structured scaffold with guidance      | ~30 min per document (est.)                    |
| **Agent Orchestrator** | Heading regex parsing, ~15-20% error rate (est.) | Stable section IDs, <2% error rate (proj.) | ~80% reduction in format review cycles (proj.) |
| **Repo Owner**         | Two config keys to maintain per type             | Single `document_types` block              | 50% config reduction                           |
| **Tool Integrator**    | Fragile DOM parsing, section boundary errors     | Marker-based parsing, reliable boundaries  | ~90% reduction in parsing errors (proj.)       |

### 1.5 Success Definition

<!-- MEMINIT_SECTION: success_definition -->

Templates v2 succeeds when:

- An orchestrator can generate a PRD scaffold without repo config and receive meaningful structure (AC-8)
- An orchestrator can parse section boundaries without heading heuristics (AC-1)
- All existing repos continue working without config changes (AC-9)
- Unit + integration tests cover all resolution paths and interpolation syntaxes (100% coverage target)

### 1.6 Visual Architecture Diagram

```mermaid
graph TD
    A[User / Agent<br>meminit new TYPE 'Title'] --> B[Config Lookup<br>docops.config.yaml]
    B --> C{document_types<br>NEW}
    B --> D{type_dirs<br>LEGACY}
    B --> E{templates<br>LEGACY}

    C --> F[Template Resolution Chain]
    D --> F
    E --> F

    F --> G[1. CONFIG<br>document_types.template]
    F --> H[2. CONVENTION<br>type.tmpl / template-001-type]
    F --> I[3. BUILT-IN<br>Package assets]
    F --> J[4. SKELETON<br>Minimal scaffold]

    G -.->|Fallback| H
    H -.->|Fallback| I
    I -.->|Fallback| J

    G --> K[Output Generation<br>- Interpolation<br>- Metadata block<br>- Section markers<br>- Agent prompts]
    H --> K
    I --> K
    J --> K

    K --> L[JSON Response<br>success, data.template.source, data.template.sections]
```

### 1.7 Quick-Start Guide

#### For Human Authors

```bash
# Create a PRD with full scaffolding
meminit new PRD "My Feature" --owner "Platform Team"

# Create an ADR
meminit new ADR "Use PostgreSQL for persistence"
```

#### For Agent Orchestrators

```python
# Generate scaffold with full structure
result = subprocess.run(
    ["meminit", "new", "PRD", "Widget Platform", "--format", "json"],
    capture_output=True, text=True
)
env = json.loads(result.stdout)

# Sections are now in JSON!
sections = env.get("data", {}).get("template", {}).get("sections", [])
for section in sections:
    print(f"Section: {section['id']} at line {section['line']}")
```

#### For Repo Owners (Optional Migration)

Add to docops.config.yaml:

```yaml
document_types:
  PRD:
    directory: "10-prd"
    template: "docs/00-governance/templates/prd.template.md"
    description: "Product Requirements Document"
  ADR:
    directory: "45-adr"
    template: "docs/00-governance/templates/adr.template.md"
    description: "Architecture Decision Record"
```

---

## 2. Changelog

<!-- MEMINIT_SECTION: changelog -->

<!-- AGENT: Maintain a chronological changelog with version, date, and description of changes. Include migration notes for breaking changes. -->

| Version     | Date       | Changes                                                                                                                                                                                                                                                                                                                                                                                                                                                   | Migration Required |
| ----------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| **1.0**     | 2026-03-02 | Critical review pass: Fixed `fill_sections()` document corruption bug; corrected FR-3 tokenization (independent `<REPO>`/`<SEQ>` substitution); improved `_extract_sections()` heading detection; extracted inline ADR template body to reference; added cross-WP integration test (AC-16); retitled "Open Questions" to "Resolved Design Questions"; marked soft metrics as estimates; corrected parallelization claims; added per-WP rollback guidance. | None               |
| **0.9**     | 2026-03-02 | PRD enhancements: Replaced ASCII diagrams with native Mermaid.js visualizations for better orchestrator parsing and display; added Pydantic schemas for Agentic WPs; refined executive summary styling; strengthened error recovery workflows.                                                                                                                                                                                                            | None               |
| **0.8**     | 2026-03-02 | PRD enhancements: added Executive Summary box, Visual Architecture Diagram, Quick-Start Guide, Key Architectural Decisions section; added verification commands to all WPs; added cross-reference links between FRs/ACs/WPs; enhanced test fixtures table; updated status to "In Review"                                                                                                                                                                  | None               |
| **0.7**     | 2026-03-02 | Fixed factual inaccuracies against codebase; corrected FR-3 interpolation table; fixed TemplateInterpolator and get_template_for_type code samples; added edge-case tests; added orchestrator operational guidance (11.4); strengthened Executive Summary; consistency pass                                                                                                                                                                               | None               |
| **0.6**     | 2026-03-02 | Added section markers throughout; enhanced AGENT guidance; added Error Scenarios appendix; improved visual diagrams                                                                                                                                                                                                                                                                                                                                       | None               |
| **0.5**     | 2026-03-01 | Initial comprehensive draft with work packages                                                                                                                                                                                                                                                                                                                                                                                                            | None               |
| **0.1**     | 2026-02-20 | Concept document created                                                                                                                                                                                                                                                                                                                                                                                                                                  | None               |

**Notes for Future Versions:**

- Status will move to "Approved" when implementation is complete
- v2.0 will include structural linting (deferred feature)

---

## 3. Current State Analysis

<!-- MEMINIT_SECTION: current_state_analysis -->

<!-- AGENT: Describe the current implementation state. Include code snippets from actual implementation files. -->

### 3.1 What Exists Today

`meminit new` currently performs these steps (from `src/meminit/core/use_cases/new_document.py`):

```python
# Simplified flow from new_document.py
1. Load config from docops.config.yaml
2. Resolve directory from type_directories (or DEFAULT_TYPE_DIRECTORIES)
3. Load template from templates.<type> if configured
4. Apply string substitutions: {title}, {owner}, <REPO>, <SEQ>, <YYYY-MM-DD>
5. Generate YAML frontmatter
6. Write the document
```

**Key implementation anchors:**

| Component        | File Path                                                                           | Current Behavior                                                                              |
| ---------------- | ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Config parsing   | `src/meminit/core/services/repo_config.py`                                          | Reads `type_directories` and `templates` separately                                           |
| Template loading | `src/meminit/core/use_cases/new_document.py:_load_template()`                       | Reads file if configured; returns None otherwise                                              |
| Interpolation    | `src/meminit/core/use_cases/new_document.py:_apply_common_template_substitutions()` | String replace of `{}` and `<>` patterns                                                      |
| Metadata block   | `src/meminit/core/use_cases/new_document.py`                                        | `<!-- MEMINIT_METADATA_BLOCK -->` replaced inline via `str.replace()`; no deduplication logic |
| JSON output      | `src/meminit/core/services/output_contracts.py`                                     | Basic envelope; no template info or sections                                                  |

### 3.2 Current Template Examples

**Existing ADR template** (`docs/00-governance/templates/template-001-adr.md`):

```markdown
---
document_id: <REPO>-ADR-<SEQ>
type: ADR
title: <Decision Title>
status: Draft
template_type: adr-standard
template_version: 1.1
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** <REPO>-ADR-<SEQ>
> **Owner:** <Team or Person>
> ...

# <REPO>-ADR-<SEQ>: <Decision Title>

## 1. Context & Problem Statement

Describe the motivating problem, constraints, and forces.
...
```

**Existing PRD template** (`docs/00-governance/templates/template-001-prd.md`):

```markdown
# PRD: {title}

## Problem Statement

...
```

> **Note:** This is the _entire_ PRD template — only 6 lines. Compare with the ADR template above. This asymmetry is a primary motivator for built-in templates with full section scaffolding.

**Observed gaps:**

- No section markers (e.g., `<!-- MEMINIT_SECTION: context -->`)
- No agent guidance blocks
- Inconsistent placeholder syntax (`<REPO>` vs `{title}`)
- PRD template is minimal (most sections not defined)

### 3.3 What Works Well

<!-- MEMINIT_SECTION: current_strengths -->

| Strength                      | Description                                                     |
| ----------------------------- | --------------------------------------------------------------- |
| **Repo-controlled structure** | Repositories define templates and directory mappings            |
| **Safe by default**           | No code execution; pure string substitution                     |
| **Frontmatter merging**       | Template frontmatter can define template metadata               |
| **JSON envelope**             | All commands emit consistent v2 envelope (per MEMINIT-SPEC-004) |

### 3.4 Gaps for Agent-Orchestrated DocOps

<!-- MEMINIT_SECTION: current_gaps -->

| Gap                          | Impact                                         | Example Failure                                                                    |
| ---------------------------- | ---------------------------------------------- | ---------------------------------------------------------------------------------- |
| **No stable section IDs**    | Agents must infer structure from headings      | Agent generates "Problem Statement" but template expects "## 2. Problem Statement" |
| **Config-only discovery**    | No-config repos get generic skeleton           | New repo runs `meminit new ADR "X"` and gets minimal template                      |
| **Underspecified syntax**    | Placeholder vocabulary not documented          | Agent doesn't know about `{status}` or `<YYYY-MM-DD>`                              |
| **Ambiguous metadata block** | May duplicate if template includes placeholder | Final document has two metadata blocks                                             |
| **Split-brain config**       | `type_directories` + `templates` are separate  | Orchestrator must query two keys to understand a type                              |

---

## 4. Problem Statement

<!-- MEMINIT_SECTION: problem_statement -->

<!-- AGENT: Quantify the problem with data. State who is impacted and how. What is the current gap? -->

### 4.1 The Core Problem

Meminit provides excellent _envelope governance_ (document IDs, schema validation, directory structure) but lacks _body contract_ stability. Without a stable body contract:

> **Humans** copy/paste from old documents, causing structural drift over time.
>
> **Agents** hallucinate sections and headings, producing documents that fail review for format before content is evaluated.
>
> **Tooling** cannot rely on consistent section boundaries for parsing or validation.

### 4.2 Concrete Agentic Failure Scenario

```
AGENT: Generate an ADR for "Use Redis for caching"

# Current behavior (Templates v1):
1. Agent calls: meminit new ADR "Use Redis for caching" --format json
2. Agent receives path and basic metadata
3. Agent must read the file to understand structure
4. Agent parses headings with regex: r'^##\s+(\d+\.)?\s*(.+)$'
5. Agent generates content for each section
6. PROBLEM: Agent misinterprets "Context & Problem Statement" as two sections
7. PROBLEM: Agent doesn't know which sections are required vs optional
8. PROBLEM: If template has no sections (generic skeleton), agent invents structure

# Desired behavior (Templates v2):
1. Agent calls: meminit new ADR "Use Redis for caching" --format json
2. Agent receives JSON with section inventory (v2 envelope):
   {"data": {"template": {"sections": [
     {"id": "context", "heading": "## 1. Context & Problem Statement", "required": true},
     {"id": "decision_drivers", "heading": "## 2. Decision Drivers", "required": true}
   ]}}}
3. Agent fills each section by ID
4. Agent validates with meminit check --format json
5. Document passes format review on first attempt
```

### 4.3 Why This Matters Now

<!-- MEMINIT_SECTION: problem_urgency -->

As agentic orchestrators become primary authors of governed documentation, the template system must evolve from a human convenience to a machine contract. The Meminit roadmap (MEMINIT-STRAT-001) positions agent-first authoring as a near-term priority; Templates v2 is the prerequisite for every downstream agentic feature (structural linting, auto-fill, review bots). Without this investment, agentic workflows will:

- Produce higher review friction (format comments before content evaluation)
- Require more human intervention (manual fixes to hallucinated structure)
- Fail at scale (each agent re-implements brittle heading heuristics)
- Block downstream features that depend on stable section semantics

---

## 5. Goals, Non-Goals, and Success Metrics

<!-- MEMINIT_SECTION: goals_nongoals -->

### 5.1 Goals

<!-- MEMINIT_SECTION: goals -->

| ID      | Goal                                                                 | Measurable Outcome                                                          |
| ------- | -------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| **G-1** | Define a stable template contract for human and agent authoring      | Template spec with formal syntax for sections, placeholders, markers        |
| **G-2** | Make template resolution deterministic with a clear precedence chain | Resolution always follows: config → convention → built-in → skeleton        |
| **G-3** | Provide stable section IDs for orchestrators                         | `<!-- MEMINIT_SECTION: <id> -->` markers in all built-in templates          |
| **G-4** | Unify type configuration under `document_types` schema               | Optional `document_types` block with `directory`, `template`, `description` |
| **G-5** | Ship built-in fallback templates for common types                    | ADR, PRD, FDD templates included in package                                 |
| **G-6** | Ensure safe, non-executable template application                     | No code execution; path validation; string-only interpolation               |
| **G-7** | Provide orchestrator-friendly JSON output                            | `data.template.source`, section inventory, content preview                  |
| **G-8** | Maintain 100% backward compatibility                                 | All existing repos continue working without changes                         |

### 5.2 Non-Goals

<!-- MEMINIT_SECTION: nongoals -->

| ID       | Non-Goal                                               | Rationale                                                                         |
| -------- | ------------------------------------------------------ | --------------------------------------------------------------------------------- |
| **NG-1** | Structural linting in `meminit check`                  | Valuable future feature; separate complexity (validate sections exist, not empty) |
| **NG-2** | Full template language (conditionals, loops, includes) | Keep engine simple; complexity doesn't justify cost                               |
| **NG-3** | LLM/tool calls during template application             | Templates are static scaffolding; generation is orchestrator's job                |
| **NG-4** | Automatic Architext sync                               | Repos can align manually; auto-sync is separate project                           |
| **NG-5** | Template inheritance or composition                    | Keep templates flat; repo can copy/modify as needed                               |
| **NG-6** | Breaking changes to existing configs                   | All changes must be backward compatible                                           |
| **NG-7** | Template versioning/rollback                           | Repos manage templates; version control handles history                           |

### 5.3 Success Metrics

<!-- MEMINIT_SECTION: success_metrics -->

| Metric                              | Target                                                     | Measurement                                                 |
| ----------------------------------- | ---------------------------------------------------------- | ----------------------------------------------------------- |
| **Agent success rate**              | >95% of scaffold fills succeed without heading heuristics  | Orchestrator test suite generates 10 docs, measures success |
| **Review friction**                 | <10% of new docs have format-related review comments       | Sample of 20 PRs before/after rollout                       |
| **No-config adoption**              | 100% of common types (ADR/PRD/FDD) get meaningful scaffold | Fresh repo with no config runs `meminit new ADR/PRD/FDD`    |
| **Backward compatibility**          | 100% of existing repos continue working                    | Test suite with 5 real-world repo configs                   |
| **JSON output usability**           | Orchestrator can resolve template and sections in one call | Integration test with mock orchestrator                     |
| **Template resolution performance** | <100ms for typical repos                                   | Benchmark test                                              |

### 5.4 Key Architectural Decisions

| Decision                                  | Rationale                                                                                                                                                                                                                                                                         |
| ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Why HTML comments for section markers** | HTML comments (`<!-- -->`) are invisible in rendered Markdown, preserving visual cleanliness while providing machine-parseable identifiers. They don't interfere with Markdown processors or GitHub's preview.                                                                    |
| **Why four-tier resolution precedence**   | The chain (config → convention → built-in → skeleton) ensures: (1) repos retain full control via explicit config, (2) organic template discovery works without config, (3) meaningful defaults exist for common types, (4) the system never fails - skeleton is always available. |
| **Why `document_types` is optional**      | Backward compatibility requires supporting existing `type_directories` + `templates` configs indefinitely. Making `document_types` optional allows gradual migration without forcing users to change their working configs.                                                       |
| **Why two placeholder syntaxes**          | Legacy templates use `{title}` and `<REPO>` syntax. New templates should use `{{title}}` for clarity. Supporting both ensures existing repos continue working while enabling future templates to use the cleaner syntax.                                                          |

---

## 6. Personas and Primary Use Cases

<!-- MEMINIT_SECTION: personas -->

<!-- AGENT: Define primary users, their needs, pain points, and how this feature helps them. -->

### 6.1 Personas

| Persona                  | Primary Need                                  | Pain Point Today                             | Templates v2 Benefit                           |
| ------------------------ | --------------------------------------------- | -------------------------------------------- | ---------------------------------------------- |
| **Human Author**         | Avoid blank-page syndrome; follow house style | What sections go in a PRD?                   | Pre-structured outline with section guidance   |
| **Agent Orchestrator**   | Deterministically populate required sections  | Heading parsing is error-prone               | Stable section IDs + embedded prompts          |
| **Repo Owner/Architect** | Encode local governance and repo "shape"      | How do I add a custom doc type?              | `document_types` schema + convention discovery |
| **Tool Integrator**      | Parse consistent document structures          | Where does the "Decision" section start/end? | Section markers for reliable parsing           |

### 6.2 Primary Use Cases

<!-- MEMINIT_SECTION: use_cases -->

#### UC-1: Human Author Creates ADR

```bash
# User runs:
meminit new ADR "Use Redis for Caching" --owner "Platform Team"

# Meminit generates:
docs/45-adr/REPO-ADR-001-use-redis-for-caching.md
# With:
# - Stable sections (Context, Options, Decision, Consequences)
# - Section markers (<!-- MEMINIT_SECTION: context -->)
# - Agent guidance (<!-- AGENT: ... -->)
# - Interpolated placeholders ({{title}}, {{document_id}}, etc.)
```

#### UC-2: Agent Orchestrator Generates PRD

```python
# Orchestrator workflow:
result = subprocess.run(
    ["meminit", "new", "PRD", "Widget Platform", "--format", "json"],
    capture_output=True,
    text=True
)
data = json.loads(result.stdout)

# Orchestrator parses sections:
doc_path = Path(data["root"]) / data["data"]["path"]
sections = data.get("data", {}).get("template", {}).get("sections", [])
for section in sections:
    section_id = section["id"]
    content = generate_content(section_id, section["agent_prompt"])
    update_section(doc_path, section_id, content)

# Orchestrator validates:
check_result = subprocess.run(
    ["meminit", "check", str(doc_path), "--format", "json"],
    capture_output=True,
    text=True,
)
check_env = json.loads(check_result.stdout)
assert check_env["success"]
```

#### UC-3: Repo Owner Adds Custom Type

```yaml
# docops.config.yaml
document_types:
  MIGRATION:
    directory: "25-migrations"
    template: "docs/00-governance/templates/migration.template.md"
    description: "Database and data migration plan"
```

```bash
# Now users can run:
meminit new MIGRATION "User data to new schema"
# And agents discover it via:
meminit context --format json
```

---

## 7. Proposed Solution

<!-- MEMINIT_SECTION: proposed_solution -->

### 7.1 Core Concepts

<!-- MEMINIT_SECTION: core_concepts -->

| Term                  | Definition                                                                                                                       |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| **Content Archetype** | A reusable documentation concern (e.g., `problem_statement`, `risks`) with a stable ID and recommended defaults. See Appendix A. |
| **Document Type**     | The `type:` frontmatter value (e.g., `ADR`, `PRD`, `SPEC`), mapped to a directory and template.                                  |
| **Template Contract** | A Markdown body scaffold with stable headings/markers, placeholders, and optional agent guidance blocks.                         |
| **Template Source**   | Where a template was resolved from: `config`, `convention`, `builtin`, or `none` (skeleton).                                     |
| **Section Marker**    | `<!-- MEMINIT_SECTION: <archetype_id> -->` - stable identifier for a section.                                                    |
| **Agent Guidance**    | `<!-- AGENT: <prompt> -->` - embedded instruction for agentic authors.                                                           |

### 7.2 Content Archetype Model

<!-- MEMINIT_SECTION: archetype_model -->

```mermaid
graph TD
    subgraph "Content Archetypes (Stable IDs)"
        A1[problem_statement]
        A2[requirements_func]
        A3[risks]
        A4[acceptance_criteria]
    end

    subgraph "Document Types (Repo-defined composition)"
        D1[PRD = {problem_statement, requirements_func, risks, acceptance_criteria, ...}]
        D2[ADR = {context, options, decision, consequences, ...}]
    end

    subgraph "Repo Structure"
        R1[docs/10-prd/]
        R2[docs/45-adr/]
    end

    A1 --> D1
    A2 --> D1
    A3 --> D1
    A4 --> D1

    D1 --> R1
    D2 --> R2
```

### 7.3 Deterministic Template Resolution

<!-- MEMINIT_SECTION: template_resolution -->

```mermaid
flowchart TD
    Start[doc_type = 'PRD'] --> S1

    subgraph S1[1. CONFIG Highest Priority]
        C1[Check docops.config.yaml] --> C2[New: document_types.PRD.template]
        C1 --> C3[Legacy: templates.prd]
        C2 --> |Found| End1((Return template))
        C3 --> |Found| End1
    end

    S1 -.->|Not Found| S2

    subgraph S2[2. CONVENTION Medium Priority]
        V1[Check docs/00-governance/templates/prd.template.md]
        V2[Check docs/00-governance/templates/template-001-prd.md]
        V1 --> |Found| End2((Return template))
        V2 --> |Found| End2
    end

    S2 -.->|Not Found| S3

    subgraph S3[3. BUILT-IN Fallback]
        B1[Check package assets]
        B1 --> |Found| End3((Return template))
    end

    S3 -.->|Not Found| S4

    subgraph S4[4. SKELETON Last Resort]
        SK1[Generate minimal scaffold] --> End4((Return scaffold))
    end
```

### 7.4 Architext Compatibility (Informational)

<!-- MEMINIT_SECTION: architext_compat -->

When Meminit and Architext co-exist in a repo:

- **Section IDs SHOULD align:** Architext schemas and Meminit templates should use the same `archetype_id` values
- **Headings MAY drift:** Section IDs are stable; headings can change without breaking tools
- **Manual alignment:** Repos are responsible for keeping IDs in sync; no auto-sync in this PRD

---

## 8. Requirements

<!-- MEMINIT_SECTION: requirements -->

<!-- AGENT: List testable behaviors. Each requirement should be verifiable and have a unique ID. -->

### 8.1 Functional Requirements

#### FR-1: Template Resolution Precedence

Meminit MUST resolve template content for `meminit new` using the precedence chain in [Section 7.3](#73-deterministic-template-resolution) (config → convention → built-in → skeleton).

**Rationale:** Ensures deterministic behavior; allows repo overrides while providing useful defaults.

**Verification:** Unit test `test_template_resolution_precedence()` in `tests/core/services/test_template_resolution.py`.

#### FR-2: Deterministic, Safe Template Application

When applying a template, Meminit MUST:

1. Read the template as UTF-8.
2. Apply interpolation (FR-3).
3. Emit: **frontmatter → visible metadata block → template body**.

Template application MUST NOT execute code, import modules, or evaluate expressions.

**Rationale:** Security; reproducibility; cross-platform compatibility.

**Verification:** Unit test `test_template_application_no_code_execution()`.

#### FR-3: Interpolation Vocabulary

Meminit MUST support the following interpolation variables:

| Variable    | Legacy Syntax(es)                                | Preferred Syntax  | Description                         |
| ----------- | ------------------------------------------------ | ----------------- | ----------------------------------- |
| Title       | `{title}`, `<Decision Title>`, `<Feature Title>` | `{{title}}`       | Document title                      |
| Document ID | _(not a single v1 token — see note below)_       | `{{document_id}}` | Full document ID (new in v2)        |
| Owner       | `{owner}`, `<Team or Person>`                    | `{{owner}}`       | Document owner                      |
| Status      | `{status}`                                       | `{{status}}`      | Document status                     |
| Date        | `<YYYY-MM-DD>`                                   | `{{date}}`        | Current date (ISO 8601)             |
| Repo prefix | `<REPO>`, `<PROJECT>`                            | `{{repo_prefix}}` | Repository prefix                   |
| Sequence    | `<SEQ>`                                          | `{{seq}}`         | Document sequence number            |
| Type        | —                                                | `{{type}}`        | Document type                       |
| Area        | `{area}`                                         | `{{area}}`        | Document area                       |
| Description | `{description}`                                  | `{{description}}` | Document description (optional)     |
| Keywords    | `{keywords}`                                     | `{{keywords}}`    | Comma-separated keywords (optional) |
| Related IDs | `{related_ids}`                                  | `{{related_ids}}` | Comma-separated IDs (optional)      |

> **Critical implementation note:** In the current codebase (`_apply_common_template_substitutions()`), there is **no** single `{document_id}` v1 token. Instead, the document ID is composed by independently substituting `<REPO>`, the normalized type, and `<SEQ>` — which the interpolation engine must continue to handle as **three separate tokens** for backward compatibility. The preferred `{{document_id}}` syntax is **new in v2** and is a convenience alias that substitutes the fully-composed ID directly. Implementors MUST NOT replace the independent `<REPO>` / `<SEQ>` substitution logic — `{{document_id}}` is additive.

**Backward compatibility:** All legacy syntaxes MUST continue to work.

**New syntax:** `{{variable}}` is the preferred form for new templates.

**Unrecognized variables:** MUST be preserved verbatim in output.

**Rationale:** Backward compatibility; clear intent; graceful degradation.

**Verification:** Unit test `test_interpolation_all_syntaxes()`.

#### FR-4: Agent Prompt Blocks

Templates MUST preserve `<!-- AGENT: ... -->` HTML comments verbatim in output.

**Format:** `<!-- AGENT: <instruction text> -->`

**Placement:** SHOULD appear immediately after the section marker or heading.

**Rationale:** Provides embedded guidance for agentic authors without affecting rendering.

**Verification:** Unit test `test_agent_prompt_preservation()`.

#### FR-5: Stable Section IDs

Templates MUST support stable section identifiers using HTML comments.

**Normative marker format:** `<!-- MEMINIT_SECTION: <archetype_id> -->`

**Placement:** SHOULD appear immediately after the section heading it applies to.

**Archetype ID:** MUST be a valid identifier from Appendix A or a repo-defined extension.

**Example:**

```markdown
## 2. Problem Statement

<!-- MEMINIT_SECTION: problem_statement -->

<!-- AGENT: Quantify the problem with data. State who is impacted and how. -->

[Describe the problem.]
```

**Rationale:** Enables agents to identify sections without heading heuristics.

**Verification:** Unit test `test_section_marker_preservation()`.

#### FR-6: Unified `document_types` Config

`docops.config.yaml` MUST support an optional `document_types` block:

```yaml
document_types:
  <TYPE>:
    directory: "<path>" # required
    template: "<path>" # optional
    description: "<text>" # optional
```

**Precedence:** When `document_types.<TYPE>` exists, it MUST take precedence over legacy `type_directories` and `templates` for overlapping keys.

**Backward compatibility:** Existing configs using `type_directories` and `templates` MUST continue to work.

**Rationale:** Unified configuration; easier for agents to understand; optional migration path.

**Verification:** Unit test `test_document_types_config_precedence()`.

#### FR-7: Agent-Friendly JSON Output

When `--format json` is used with `meminit new`, the output MUST include:

```json
{
  "output_schema_version": "2.0",
  "success": true,
  "command": "new",
  "run_id": "00000000-0000-0000-0000-000000000000",
  "root": "/abs/path/to/repo",
  "data": {
    "type": "PRD",
    "title": "Widget Platform",
    "document_id": "REPO-PRD-001",
    "path": "docs/10-prd/prd-001-widget-platform.md",
    "template": {
      "applied": true,
      "source": "config",
      "path": "docs/00-governance/templates/prd.template.md",
      "content_preview": "# PRD: Widget Platform\\n\\n## 1. Executive Summary\\n...",
      "sections": [
        {
          "id": "executive_summary",
          "heading": "## 1. Executive Summary",
          "line": 42,
          "required": true,
          "agent_prompt": "Write a 2-3 sentence summary..."
        }
      ]
    }
  },
  "warnings": [],
  "violations": [],
  "advice": []
}
```

**Contract compatibility:** This extends the v2 envelope defined in MEMINIT-SPEC-004. The top-level envelope shape MUST remain unchanged; all template-specific details MUST be nested under `data.template`. The `warnings` array MUST contain Issue objects (`code`, `message`, `path`), not strings.

**Rationale:** Enables orchestrators to understand what was generated without reading the file.

**Verification:** Integration test `test_json_output_includes_template_info()`.

#### FR-8: Metadata Block Rule

Meminit MUST ensure the final document contains exactly one visible metadata block in blockquote form.

**Compatibility rules:**

1. **Template has marker + placeholder blockquote:**

   ```markdown
   <!-- MEMINIT_METADATA_BLOCK -->

   > **Document ID:** <REPO>-ADR-<SEQ>
   > **Owner:** <Team or Person>
   ```

   → Replace the blockquote with generated metadata; retain marker comment.

2. **Template has marker only:**

   ```markdown
   <!-- MEMINIT_METADATA_BLOCK -->
   ```

   → Insert generated metadata block immediately after marker.

3. **Template has no marker:**
   → Insert generated metadata block immediately after frontmatter.

**Rationale:** Prevents duplicate metadata blocks; supports future tooling.

**Verification:** Unit test `test_metadata_block_no_duplicates()`.

#### FR-9: Template Frontmatter Merging

When a template includes YAML frontmatter, Meminit MUST merge it with generated metadata.

**Precedence:** Generated metadata takes precedence for required fields:

- `document_id`, `type`, `title`, `status`, `owner`, `version`, `last_updated`, `docops_version`

**Template metadata fields:** Fields like `template_type` and `template_version` from template frontmatter MUST be preserved in the final document.

**Rationale:** Allows templates to define metadata without conflicting with generated values.

**Verification:** Unit test `test_frontmatter_merging()`.

#### FR-10: Path Traversal Protection

Template paths MUST be validated to ensure they cannot escape the repository root.

**Validation rules:**

- Absolute paths MUST be rejected
- Paths with `..` components MUST be resolved and validated
- Symlinks outside the repo MUST be rejected

**Rationale:** Security; prevents reading arbitrary files.

**Verification:** Unit test `test_path_traversal_rejected()`.

#### FR-11: Convention Discovery

When no template is configured, Meminit MUST attempt convention discovery:

1. Check `docs/00-governance/templates/<type>.template.md` (new convention)
2. Check `docs/00-governance/templates/template-001-<type>.md` (legacy convention)

**Case sensitivity:** Type lookup MUST be case-insensitive.

**Rationale:** Allows zero-config template customization; supports existing templates.

**Verification:** Unit test `test_convention_discovery()`.

### 8.2 Non-Functional Requirements

| ID        | Requirement                                                                    | Verification                    |
| --------- | ------------------------------------------------------------------------------ | ------------------------------- |
| **NFR-1** | **Determinism:** Same inputs + template → byte-identical output (except dates) | Unit test with template caching |
| **NFR-2** | **Security:** Template paths cannot escape repo root                           | Unit test with malicious paths  |
| **NFR-3** | **Performance:** Template resolution < 100ms for typical repos                 | Benchmark test                  |
| **NFR-4** | **UX:** Errors are actionable and machine-parseable in JSON mode               | Integration test                |
| **NFR-5** | **Compatibility:** 100% backward compatible with existing configs              | Test suite with real configs    |

---

## 9. Template Contract (Markdown Spec)

<!-- MEMINIT_SECTION: template_contract -->

<!-- AGENT: This section defines the formal template contract. Ensure all syntax examples are accurate and consistent. -->

### 9.1 Template File Locations

Templates are Markdown files. The following locations are supported, in order of precedence:

| Source                  | Path Pattern                                          | Example                                                 |
| ----------------------- | ----------------------------------------------------- | ------------------------------------------------------- |
| **Config (explicit)**   | Configured path                                       | `templates: {prd: "custom/path/prd.md"}`                |
| **Convention (new)**    | `docs/00-governance/templates/<type>.template.md`     | `prd.template.md`                                       |
| **Convention (legacy)** | `docs/00-governance/templates/template-001-<type>.md` | `template-001-prd.md`                                   |
| **Built-in**            | Package assets                                        | `src/meminit/core/assets/.../templates/prd.template.md` |

### 9.2 Template Structure

A template consists of three parts:

```
┌─────────────────────────────────────┐
│ 1. YAML Frontmatter (optional)      │
│    - template_type                   │
│    - template_version                │
│    - custom metadata fields          │
├─────────────────────────────────────┤
│ 2. Metadata Block Marker (optional) │
│    <!-- MEMINIT_METADATA_BLOCK -->  │
│    + optional placeholder blockquote│
├─────────────────────────────────────┤
│ 3. Document Body                    │
│    - Headings (## ... )             │
│    - Section markers                │
│    - Agent guidance blocks          │
│    - Placeholders                   │
└─────────────────────────────────────┘
```

### 9.3 Complete Canonical Template Example

```markdown
---
template_type: prd-standard
template_version: 2.0
docops_version: "2.0"
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** {{document_id}}
> **Owner:** {{owner}}
> **Status:** {{status}}
> **Version:** 0.1
> **Last Updated:** {{date}}
> **Type:** {{type}}

# PRD: {{title}}

## Table of Contents

<!-- MEMINIT_SECTION: toc -->

<!-- AGENT: Generate a table of contents with anchor links to all sections. -->

[Auto-generated or manual TOC]

---

## 1. Executive Summary

<!-- MEMINIT_SECTION: executive_summary -->

<!-- AGENT: Write a 2-3 sentence summary. What is being built, for whom, and why now? -->

[One paragraph summary.]

---

## 2. Problem Statement

<!-- MEMINIT_SECTION: problem_statement -->

<!-- AGENT: Quantify the problem with data. State who is impacted and how. What is the current gap? -->

[Describe the problem.]

### 2.1 Impact

<!-- MEMINIT_SECTION: problem_impact -->

<!-- AGENT: Who experiences this problem? How frequently? What is the cost of not solving it? -->

[Describe impact.]

---

## 3. Goals and Non-Goals

<!-- MEMINIT_SECTION: goals_nongoals -->

<!-- AGENT: List 3-5 specific, measurable goals. Explicitly state what is out of scope. -->

| ID  | Goal   | Success Metric |
| --- | ------ | -------------- |
| G-1 | [Goal] | [Metric]       |

### 3.1 Non-Goals

<!-- MEMINIT_SECTION: nongoals -->

| Non-Goal | Rationale                |
| -------- | ------------------------ |
| [X]      | [Why not doing this now] |

---

## 4. Functional Requirements

<!-- MEMINIT_SECTION: requirements_func -->

<!-- AGENT: List testable behaviors. Each requirement should be verifiable. -->

| ID   | Requirement   | Priority |
| ---- | ------------- | -------- |
| FR-1 | [Requirement] | P0/P1/P2 |

---

## 5. Acceptance Criteria

<!-- MEMINIT_SECTION: acceptance_criteria -->

<!-- AGENT: Define "done" for this feature. Each criterion must be testable. -->

| ID   | Criterion   | Verification    |
| ---- | ----------- | --------------- |
| AC-1 | [Criterion] | [How to verify] |

---

## 6. Risks and Mitigations

<!-- MEMINIT_SECTION: risks -->

<!-- AGENT: Identify technical, product, and operational risks. Include mitigations. -->

| Risk   | Impact       | Likelihood   | Mitigation   |
| ------ | ------------ | ------------ | ------------ |
| [Risk] | High/Med/Low | High/Med/Low | [Mitigation] |

---

## 7. Related Documents

<!-- MEMINIT_SECTION: related_docs -->

<!-- AGENT: Link to related specs, ADRs, PRDs by Document ID. -->

| Document ID | Title   | Relationship                          |
| ----------- | ------- | ------------------------------------- |
| [ID]        | [Title] | [Depends on/Related to/Superseded by] |
```

### 9.4 Minimal Template (Skeleton)

If no template is found, Meminit MUST fall back to a minimal skeleton body. Frontmatter is still generated normally (not interpolated from the skeleton).

```markdown
---
document_id: REPO-CUSTOM-001
type: CUSTOM
title: Custom Doc
status: Draft
version: "0.1"
last_updated: 2026-03-02
owner: __TBD__
docops_version: "2.0"
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** REPO-CUSTOM-001
> **Owner:** __TBD__
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2026-03-02
> **Type:** CUSTOM

# CUSTOM: Custom Doc

## Content

[Add your content here.]
```

### 9.5 Template Validation Rules

Templates MUST satisfy:

1. **Valid UTF-8 encoding**
2. **Optional YAML frontmatter** (must be valid YAML if present)
3. **Optional metadata block marker** (if present, must be `<!-- MEMINIT_METADATA_BLOCK -->`)
4. **Placeholders** use supported syntax (Section 9.3)
5. **Section markers** (if present) follow format `<!-- MEMINIT_SECTION: <id> -->`
6. **Agent guidance** (if present) follows format `<!-- AGENT: <text> -->`

Templates SHOULD:

1. Include section markers for all major sections
2. Include agent guidance for complex sections
3. Use `{{variable}}` syntax for new templates
4. Define `template_type` and `template_version` in frontmatter

---

## 10. Configuration Spec (docops.config.yaml)

<!-- MEMINIT_SECTION: config_spec -->

### 10.1 `document_types` Schema (Preferred)

```yaml
# Full example with all document types
document_types:
  ADR:
    directory: "45-adr"
    template: "docs/00-governance/templates/adr.template.md"
    description: "Architecture Decision Record"
  PRD:
    directory: "10-prd"
    template: "docs/00-governance/templates/prd.template.md"
    description: "Product Requirements Document"
  FDD:
    directory: "50-fdd"
    template: "docs/00-governance/templates/fdd.template.md"
    description: "Functional Design Document"
  SPEC:
    directory: "20-specs"
    # template is optional - will use convention/built-in
    description: "Technical Specification"
  MIGRATION:
    directory: "25-migrations"
    template: "docs/00-governance/templates/migration.template.md"
    description: "Data migration plan"
```

### 10.2 Legacy Compatibility

Existing configs remain valid:

```yaml
# Legacy config (still supported)
type_directories:
  ADR: "45-adr"
  PRD: "10-prd"
  SPEC: "20-specs"

templates:
  adr: "docs/00-governance/templates/template-001-adr.md"
  prd: "docs/00-governance/templates/template-001-prd.md"
  # spec will use convention discovery or built-in
```

### 10.3 Mixed Config (Migration Path)

```yaml
# Gradual migration: some types use new schema, others use legacy
document_types:
  PRD:
    directory: "10-prd"
    template: "docs/00-governance/templates/prd.template.md"
    description: "Product Requirements Document"

# Legacy still works for types not in document_types
type_directories:
  ADR: "45-adr"
  SPEC: "20-specs"

templates:
  adr: "docs/00-governance/templates/template-001-adr.md"
```

### 10.4 Resolution Rules

Given a `doc_type`, resolution follows:

```
1. If document_types.<TYPE> exists:
   - Use document_types.<TYPE>.directory if present
   - Use document_types.<TYPE>.template if present
   - Otherwise, fall through to step 2 for template

2. Else (no document_types or TYPE not in it):
   - Use type_directories.<TYPE> for directory
   - Use templates.<type> for template (if present)
   - Otherwise, fall through to step 3

3. Convention discovery:
   - Check docs/00-governance/templates/<type>.template.md
   - Check docs/00-governance/templates/template-001-<type>.md

4. Built-in fallback:
   - Check package templates (ADR, PRD, FDD)

5. Skeleton:
   - Use minimal template
```

---

## 11. Agent Orchestrator Integration Guide

<!-- MEMINIT_SECTION: orchestrator_guide -->

<!-- AGENT: This section is critical for orchestrator developers. Ensure all code examples are tested and accurate. -->

### 11.1 Recommended Orchestrator Flow

```python
import subprocess
import json
import re
from pathlib import Path

def create_governed_document(doc_type: str, title: str, content_map: dict) -> dict:
    """
    Create a governed document with agent-generated content.

    Args:
        doc_type: Document type (e.g., "PRD", "ADR")
        title: Document title
        content_map: Map of section_id -> generated content

    Returns:
        Result dict with path and validation status
    """
    # Step 1: Generate scaffold
    result = subprocess.run(
        ["meminit", "new", doc_type, title, "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    env = json.loads(result.stdout)

    if not env.get("success", False):
        return {"success": False, "error": env.get("error"), "warnings": env.get("warnings", [])}

    repo_root = Path(env["root"])
    doc_path = repo_root / env["data"]["path"]
    original_content = doc_path.read_text()

    # Step 2: Parse sections
    sections = parse_sections(original_content)

    # Step 3: Fill content
    updated_content = fill_sections(original_content, sections, content_map)

    # Step 4: Write updated document
    doc_path.write_text(updated_content)

    # Step 5: Validate
    check_result = subprocess.run(
        ["meminit", "check", str(doc_path), "--format", "json"],
        capture_output=True,
        text=True
    )
    check_env = json.loads(check_result.stdout)

    return {
        "success": True,
        "path": str(doc_path),
        "valid": bool(check_env.get("success", False)),
        "warnings": check_env.get("warnings", []),
        "violations": check_env.get("violations", []),
    }


def parse_sections(content: str) -> list[dict]:
    """
    Parse section markers from document content.

    Returns:
        List of {id, heading, line_number, content}
    """
    sections = []
    lines = content.splitlines()

    current_section = None
    current_heading = None
    current_content = []
    section_start_line = 0

    for i, line in enumerate(lines):
        # Check for section marker
        marker_match = re.match(
            r'<!--\s*MEMINIT_SECTION:\s*([a-z0-9_]+)\s*-->',
            line,
            flags=re.IGNORECASE,
        )
        if marker_match:
            # Save previous section
            if current_section:
                sections.append({
                    "id": current_section,
                    "heading": current_heading,
                    "line": section_start_line + 1,  # 1-based line number
                    "content": "\n".join(current_content).strip()
                })

            # Start new section
            current_section = marker_match.group(1).lower()
            current_heading = lines[i - 1] if i > 0 else "Unknown"
            section_start_line = max(i - 1, 0)
            current_content = []
        elif current_section:
            current_content.append(line)

    # Save last section
    if current_section:
        sections.append({
            "id": current_section,
            "heading": current_heading,
            "line": section_start_line + 1,  # 1-based line number
            "content": "\n".join(current_content).strip()
        })

    return sections


def fill_sections(content: str, sections: list[dict], content_map: dict) -> str:
    """
    Replace section content with generated content.

    Preserves:
    - All content outside targeted sections (including unfilled sections)
    - Section headings
    - Section markers
    - Agent guidance blocks

    Algorithm:
    1. Build a map of section_id -> (marker_line, next_boundary_line)
    2. Walk the document once, copying lines and replacing only
       sections that have entries in content_map.
    """
    lines = content.splitlines()

    # --- Phase 1: Build section boundary map ---
    marker_positions: dict[str, tuple[int, int]] = {}  # id -> (marker_line, next_boundary)
    marker_order: list[tuple[int, str]] = []  # (line_no, id) for ordering

    for i, line in enumerate(lines):
        match = re.match(
            r'<!--\s*MEMINIT_SECTION:\s*([a-z0-9_]+)\s*-->',
            line,
            flags=re.IGNORECASE,
        )
        if match:
            marker_order.append((i, match.group(1).lower()))

    # Compute each section's end boundary (next heading or next marker)
    for idx, (marker_line, section_id) in enumerate(marker_order):
        next_boundary = len(lines)  # default: end of document
        for j in range(marker_line + 1, len(lines)):
            if re.match(r"^#{1,6}\s", lines[j]) or "MEMINIT_SECTION:" in lines[j]:
                next_boundary = j
                # If this line is a marker, back up to include its heading
                if (
                    "MEMINIT_SECTION:" in lines[j]
                    and j > 0
                    and re.match(r"^#{1,6}\s", lines[j - 1])
                ):
                    next_boundary = j - 1
                break
        marker_positions[section_id] = (marker_line, next_boundary)

    # --- Phase 2: Rebuild document ---
    output_lines: list[str] = []
    skip_until: int | None = None

    for i, line in enumerate(lines):
        # If we're inside a replaced region, skip original lines
        if skip_until is not None and i < skip_until:
            continue
        skip_until = None

        # Check if this line is a section marker we need to fill
        match = re.match(
            r'<!--\s*MEMINIT_SECTION:\s*([a-z0-9_]+)\s*-->',
            line,
            flags=re.IGNORECASE,
        )
        if match and match.group(1).lower() in content_map:
            section_id = match.group(1).lower()
            marker_line, next_boundary = marker_positions[section_id]

            # Keep the marker line
            output_lines.append(line)

            # Extract and preserve agent guidance from original content
            agent_guidance = []
            for j in range(marker_line + 1, next_boundary):
                if "<!-- AGENT:" in lines[j]:
                    agent_guidance.append(lines[j])

            # Emit: blank line, guidance, blank line, new content, blank line
            output_lines.append("")
            for guidance in agent_guidance:
                output_lines.append(guidance)
            output_lines.append("")
            output_lines.append(content_map[section_id])
            output_lines.append("")

            # Skip original section content
            skip_until = next_boundary
        else:
            output_lines.append(line)

    return "\n".join(output_lines)
```

### 11.2 Pydantic Schemas for Orchestrators

For orchestrators using Python and LLM function calling (e.g., via OpenAI or Anthropic tool use), you can define strict Pydantic models to parse the `meminit new` output and structure your agent's generation task:

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class SectionMarker(BaseModel):
    id: str = Field(..., description="Stable section ID, e.g., 'executive_summary'")
    heading: str = Field(..., description="The markdown heading text")
    line: int = Field(..., description="Line number where the heading appears")
    required: bool = Field(True, description="Whether this section must be filled")
    agent_prompt: Optional[str] = Field(None, description="Optional agent guidance for this section")

class Issue(BaseModel):
    code: str
    message: str
    path: str
    line: Optional[int] = None
    severity: Optional[Literal["warning", "error"]] = None

class ErrorObject(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None

class TemplateInfo(BaseModel):
    applied: bool
    source: Literal["config", "convention", "builtin", "none"]
    path: Optional[str] = None
    content_preview: Optional[str] = None
    sections: List[SectionMarker] = Field(default_factory=list)

class NewData(BaseModel):
    type: str
    title: str
    document_id: str
    path: str
    template: Optional[TemplateInfo] = None

class MeminitNewEnvelope(BaseModel):
    output_schema_version: str
    success: bool
    command: Literal["new"]
    run_id: str
    root: str
    data: NewData
    warnings: List[Issue] = Field(default_factory=list)
    violations: List[dict] = Field(default_factory=list)
    advice: List[dict] = Field(default_factory=list)
    error: Optional[ErrorObject] = None
```

By feeding this schema to your agent framework, you ensure the LLM understands exactly which sections are available and required.

### 11.3 JSON Output Examples

#### Successful Document Creation

```json
{
  "output_schema_version": "2.0",
  "success": true,
  "command": "new",
  "run_id": "00000000-0000-0000-0000-000000000000",
  "root": "/abs/path/to/repo",
  "data": {
    "type": "PRD",
    "title": "Widget Platform",
    "document_id": "REPO-PRD-001",
    "path": "docs/10-prd/prd-001-widget-platform.md",
    "template": {
      "applied": true,
      "source": "convention",
      "path": "docs/00-governance/templates/prd.template.md",
      "sections": [
        {
          "id": "executive_summary",
          "heading": "## 1. Executive Summary",
          "line": 42,
          "required": true,
          "agent_prompt": "Write a 2-3 sentence summary..."
        },
        {
          "id": "problem_statement",
          "heading": "## 2. Problem Statement",
          "line": 52,
          "required": true,
          "agent_prompt": "Quantify the problem with data..."
        }
      ],
      "content_preview": "# PRD: Widget Platform\\n\\n## Table of Contents\\n\\n1. [Executive Summary](#1-executive-summary)\\n..."
    }
  },
  "warnings": [],
  "violations": [],
  "advice": []
}
```

#### No Template Found (Skeleton)

```json
{
  "output_schema_version": "2.0",
  "success": true,
  "command": "new",
  "run_id": "00000000-0000-0000-0000-000000000000",
  "root": "/abs/path/to/repo",
  "data": {
    "type": "CUSTOM",
    "title": "Custom Doc",
    "document_id": "REPO-CUSTOM-001",
    "path": "docs/99-custom/custom-001-custom-doc.md",
    "template": {
      "applied": false,
      "source": "none",
      "path": null,
      "sections": [],
      "content_preview": "# CUSTOM: Custom Doc\\n\\n## Content\\n\\n[Add your content here.]"
    }
  },
  "warnings": [
    {
      "code": "TEMPLATE_NOT_FOUND",
      "message": "No template found for type CUSTOM; using minimal skeleton",
      "path": "docops.config.yaml"
    }
  ],
  "violations": [],
  "advice": []
}
```

#### Error Response

```json
{
  "output_schema_version": "2.0",
  "success": false,
  "command": "new",
  "run_id": "00000000-0000-0000-0000-000000000000",
  "root": "/abs/path/to/repo",
  "data": {},
  "warnings": [],
  "violations": [],
  "advice": [],
  "error": {
    "code": "UNKNOWN_TYPE",
    "message": "Unknown document type: INVALID",
    "details": {
      "doc_type": "INVALID",
      "valid_types": ["ADR", "PRD", "SPEC", "FDD"]
    }
  }
}
```

### 11.4 Guardrails for Agents

| Rule                               | Description                                                |
| ---------------------------------- | ---------------------------------------------------------- |
| **Never invent sections**          | Only fill sections defined in the template                 |
| **Never reorder sections**         | Preserve template order                                    |
| **Preserve markers**               | Keep `<!-- MEMINIT_SECTION: ... -->` intact                |
| **Preserve guidance**              | Keep `<!-- AGENT: ... -->` blocks for future reference     |
| **Treat requirements as testable** | Every requirement/AC should be verifiable                  |
| **No secrets/PII**                 | Never insert credentials or personal data                  |
| **Use JSON output**                | Always use `--format json` for programmatic calls          |
| **Validate before commit**         | Run `meminit check` before considering document complete   |
| **Handle errors gracefully**       | Unknown types, missing templates → fail with clear message |

### 11.5 Operational Notes for Orchestrators

**stdout vs stderr:** When `--format json` is used, Meminit emits exactly one JSON object on **stdout**. All human-readable logs, progress messages, and diagnostic errors are routed to **stderr**. Orchestrators MUST parse only stdout; stderr may be logged for debugging but MUST NOT be parsed as JSON.

**Timeouts:** `meminit new` is expected to complete in <2 seconds for local repos. Orchestrators SHOULD set a timeout of **10 seconds** and treat longer execution as an error. `meminit check` may take longer for large repos; a **30-second** timeout is recommended.

**Idempotency:** In default (sequential ID) mode, `meminit new` is **not idempotent** — calling it twice with the same arguments creates two documents with different IDs. In deterministic mode (`meminit new ... --id REPO-TYPE-SEQ`), the command can be idempotent when the target file already exists and the generated content matches (it returns success without changing the file). Orchestrators MUST track created document paths and avoid duplicate calls; when retrying after an ambiguous failure (e.g., timeout), first check whether the expected path already exists.

**Error handling pattern:**

```python
import subprocess
import json
import sys

def safe_meminit_call(args: list[str], timeout: int = 10) -> dict:
    """Call meminit with error handling suitable for orchestrators.

    Note: TIMEOUT / NOT_INSTALLED / CLI_ERROR are orchestrator-level wrapper codes,
    not Meminit ErrorCode enum values.
    """
    try:
        result = subprocess.run(
            ["meminit"] + args + ["--format", "json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"success": False, "error": {"code": "TIMEOUT", "message": f"meminit timed out after {timeout}s"}}
    except FileNotFoundError:
        return {"success": False, "error": {"code": "NOT_INSTALLED", "message": "meminit CLI not found on PATH"}}

    if result.returncode != 0:
        # Try to parse structured error from stdout
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"success": False, "error": {"code": "CLI_ERROR", "message": result.stderr.strip()}}

    return json.loads(result.stdout)
```

**Exit codes:** Exit code semantics are governed by MEMINIT-PRD-003. Orchestrators SHOULD branch on the JSON envelope (`success` + `error.code`) rather than exit code alone.

---

## 12. Deliverable Implementation Plan (Agent-Executable)

<!-- MEMINIT_SECTION: implementation_plan -->

<!-- AGENT: This section provides an agent-executable implementation plan. Each work package should be self-contained and actionable. -->

This plan is written to be directly consumable as a work queue by an agentic orchestrator.

### 12.1 Definition of Done

Templates v2 is "done" when:

- [ ] `meminit new` deterministically produces scaffolds with stable section IDs for ADR, PRD, FDD (even without repo config)
- [ ] Legacy repos continue working with existing `templates` mappings and placeholder syntaxes
- [ ] `--format json` exposes template provenance and section inventory
- [ ] Unit and integration tests cover all resolution paths and interpolation syntaxes
- [ ] Built-in templates include section markers and agent guidance
- [ ] This PRD is updated to reflect final implementation

### 12.2 Work Packages (Suggested PR Boundaries)

| WP       | Deliverable                     | Key Files                                                                                                                                     | Implements FR(s)   | Estimated Complexity |
| -------- | ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ | -------------------- |
| **WP-1** | Config: `document_types` schema | `src/meminit/core/services/repo_config.py`, `tests/core/services/test_repo_config.py`                                                         | FR-6               | Medium               |
| **WP-2** | Template resolver service       | `src/meminit/core/services/template_resolver.py`, `tests/core/services/test_template_resolution.py`                                           | FR-1, FR-10, FR-11 | High                 |
| **WP-3** | Interpolation engine refactor   | `src/meminit/core/services/template_interpolation.py`, `tests/core/services/test_interpolation.py`                                            | FR-2, FR-3, FR-9   | Medium               |
| **WP-4** | Metadata block rule             | `src/meminit/core/use_cases/new_document.py`, `tests/core/use_cases/test_metadata_block.py`                                                   | FR-2, FR-8         | Medium               |
| **WP-5** | Built-in templates              | `src/meminit/core/assets/org_profiles/default/templates/*.md`, `tests/core/assets/test_builtin_templates.py`                                  | FR-4, FR-5         | Low                  |
| **WP-6** | JSON output enhancements        | `src/meminit/core/use_cases/new_document.py`, `src/meminit/core/services/output_contracts.py`, `tests/core/use_cases/test_new_json_output.py` | FR-7               | Medium               |
| **WP-7** | Update vendored templates       | `docs/00-governance/templates/*.md`                                                                                                           | FR-4, FR-5         | Low                  |
| **WP-8** | Docs and PRD update             | This PRD, README                                                                                                                              | —                  | Low                  |

### 12.3 Agent Checklist (Per WP)

For each work package:

1. **Read the implementation plan** for the WP
2. **Identify pre-conditions** (what must exist before starting)
3. **Implement the change** with minimal surface area
4. **Add/extend tests** covering success and failure modes
5. **Verify:** Run `meminit check --format json` and relevant tests
6. **Update documentation** if behavior changed

### 12.4 Detailed Work Packages

#### WP-1: Config Model - `document_types` Schema

**Pre-conditions:**

- `src/meminit/core/services/repo_config.py` exists with current `type_directories` and `templates` support
- Tests exist in `tests/core/services/test_repo_config.py`

**Implementation steps:**

1. **Extend `RepoConfig` dataclass** (`src/meminit/core/services/repo_config.py`):

```python
@dataclass(frozen=True)
class RepoConfig:
    # ... existing fields ...
    document_types: Dict[str, "DocumentTypeConfig"]  # New field

@dataclass(frozen=True)
class DocumentTypeConfig:
    directory: str
    template: Optional[str] = None
    description: Optional[str] = None
```

2. **Add parsing in `_build_namespace_config()`**:

```python
def _build_namespace_config(...) -> Optional[RepoConfig]:
    # ... existing code ...

    # Parse document_types
    document_types: Dict[str, DocumentTypeConfig] = {}
    raw_document_types = raw_namespace.get("document_types") or defaults.get("document_types")
    if isinstance(raw_document_types, Mapping):
        for k, v in raw_document_types.items():
            doc_type = _normalize_type_key(k)
            if not isinstance(v, Mapping):
                continue
            directory = v.get("directory")
            if not directory:
                continue  # directory is required
            directory_norm = _safe_repo_relative_path(root, directory)
            if not directory_norm:
                continue  # invalid path
            template_norm = _safe_repo_relative_path(root, v.get("template"))
            description = v.get("description") if isinstance(v.get("description"), str) else None
            document_types[doc_type] = DocumentTypeConfig(
                directory=directory_norm,
                template=template_norm,
                description=description
            )

    # ... rest of existing code ...
    return RepoConfig(
        # ... existing fields ...
        document_types=document_types,
    )
```

3. **Update `expected_subdir_for_type()`**:

```python
def expected_subdir_for_type(self, doc_type: str) -> Optional[str]:
    key = _normalize_type_key(doc_type)
    # Check document_types first
    if key in self.document_types:
        return self.document_types[key].directory
    # Fall back to type_directories
    return self.type_directories.get(key)
```

4. **Add `get_template_for_type()` method**:

```python
def get_template_for_type(self, doc_type: str) -> Optional[str]:
    """Return the configured template path for *doc_type*, or None.

    Precedence: ``document_types`` > ``templates`` (legacy).
    Uses ``_normalize_type_key`` for consistent case handling.
    """
    key = _normalize_type_key(doc_type)
    # Check document_types first (keys are already normalised)
    dt = self.document_types.get(key)
    if dt is not None:
        return dt.template
    # Fall back to legacy templates map (keyed lowercase)
    return self.templates.get(key.lower())
```

**Tests to add:**

```python
# tests/core/services/test_repo_config.py

def test_document_types_config_precedence():
    """document_types takes precedence over type_directories"""
    config = load_repo_config("fixtures/repo_with_document_types")
    assert config.expected_subdir_for_type("PRD") == "10-prd"
    assert config.expected_subdir_for_type("ADR") == "45-adr"

def test_document_types_partial():
    """Can mix document_types with legacy type_directories"""
    config = load_repo_config("fixtures/repo_mixed_config")
    # PRD from document_types
    assert config.expected_subdir_for_type("PRD") == "10-prd"
    # ADR from type_directories (legacy)
    assert config.expected_subdir_for_type("ADR") == "45-adr"

def test_document_types_template_resolution():
    """Template path from document_types is respected"""
    config = load_repo_config("fixtures/repo_with_document_types")
    template = config.get_template_for_type("PRD")
    assert template == "docs/00-governance/templates/prd.template.md"
```

**Verification:**

- Run existing tests: `pytest tests/core/services/test_repo_config.py`
- Test with actual config file in fixture directory

**Post-conditions:**

- `RepoConfig` has `document_types` field
- `document_types` config is parsed correctly
- Precedence: `document_types` > `type_directories` for directory resolution
- Precedence: `document_types` > `templates` for template resolution

---

#### WP-2: Template Resolver Service

**Pre-conditions:**

- `src/meminit/core/services/repo_config.py` supports `document_types` (from WP-1)
- `src/meminit/core/use_cases/new_document.py` has `_load_template()` method

**Implementation steps:**

1. **Create new service** `src/meminit/core/services/template_resolver.py`:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from meminit.core.services.repo_config import RepoConfig

@dataclass(frozen=True)
class TemplateResolution:
    """Result of template resolution."""
    source: str  # "config", "convention", "builtin", "none"
    path: Optional[Path]  # None if source is "none"
    content: Optional[str]  # None if not found

class TemplateResolver:
    """Resolves template content using precedence chain."""

    def __init__(self, repo_config: RepoConfig):
        self.config = repo_config
        self._repo_root = repo_config.root_dir

    def resolve(self, doc_type: str) -> TemplateResolution:
        """Resolve template for document type."""
        # 1. Config (explicit)
        config_template = self._resolve_from_config(doc_type)
        if config_template:
            return config_template

        # 2. Convention
        convention_template = self._resolve_from_convention(doc_type)
        if convention_template:
            return convention_template

        # 3. Built-in
        builtin_template = self._resolve_from_builtin(doc_type)
        if builtin_template:
            return builtin_template

        # 4. None (skeleton)
        return TemplateResolution(source="none", path=None, content=None)

    def _resolve_from_config(self, doc_type: str) -> Optional[TemplateResolution]:
        """Check config for explicit template path."""
        # Check document_types first
        template_path = self.config.get_template_for_type(doc_type)
        if template_path:
            full_path = self._repo_root / template_path
            if full_path.exists():
                return TemplateResolution(
                    source="config",
                    path=full_path,
                    content=full_path.read_text()
                )
        return None

    def _resolve_from_convention(self, doc_type: str) -> Optional[TemplateResolution]:
        """Check convention paths."""
        # Normalize type for path lookup
        type_key = doc_type.lower()

        # New convention: <type>.template.md
        new_path = self.config.docs_dir / "00-governance/templates" / f"{type_key}.template.md"
        if new_path.exists():
            return TemplateResolution(
                source="convention",
                path=new_path,
                content=new_path.read_text()
            )

        # Legacy convention: template-001-<type>.md
        legacy_path = self.config.docs_dir / "00-governance/templates" / f"template-001-{type_key}.md"
        if legacy_path.exists():
            return TemplateResolution(
                source="convention",
                path=legacy_path,
                content=legacy_path.read_text()
            )

        return None

    def _resolve_from_builtin(self, doc_type: str) -> Optional[TemplateResolution]:
        """Check built-in package templates."""
        # Implementation loads from package assets
        from importlib.resources import files

        type_key = doc_type.lower()
        try:
            # Try new convention first
            template_content = files("meminit.core.assets.org_profiles.default.templates").joinpath(
                f"{type_key}.template.md"
            ).read_text()
            return TemplateResolution(
                source="builtin",
                path=None,  # Built-in has no filesystem path
                content=template_content
            )
        except FileNotFoundError:
            # Try legacy convention
            try:
                template_content = files("meminit.core.assets.org_profiles.default.templates").joinpath(
                    f"template-001-{type_key}.md"
                ).read_text()
                return TemplateResolution(
                    source="builtin",
                    path=None,
                    content=template_content
                )
            except FileNotFoundError:
                return None
```

2. **Update `new_document.py`** to use `TemplateResolver`:

```python
from meminit.core.services.template_resolver import TemplateResolver

class NewDocumentUseCase:
    def _execute_internal_impl(self, params: NewDocumentParams, ...):
        # ... existing validation ...

        # Resolve template
        resolver = TemplateResolver(ns)
        resolution = resolver.resolve(normalized_type)

        # Load template content or use skeleton
        if resolution.content:
            template_content = resolution.content
            template_source = resolution.source
        else:
            template_content = self._get_skeleton_template(normalized_type)
            template_source = "none"

        # Apply template...
```

**Tests to add:**

```python
# tests/core/services/test_template_resolution.py

import pytest
from meminit.core.services.template_resolver import TemplateResolver

def test_resolution_precedence_config_first(tmp_path):
    """Config template takes precedence over convention."""
    # Setup: config template exists, convention template also exists
    # Assert: config template is used

def test_resolution_fallback_to_convention(tmp_path):
    """Convention template used when no config."""
    # Setup: no config, convention template exists
    # Assert: convention template is used

def test_resolution_fallback_to_builtin():
    """Built-in template used when no config or convention."""
    # Setup: no config, no convention
    # Assert: built-in template is used for ADR/PRD/FDD

def test_resolution_none_for_unknown_type():
    """Unknown type returns skeleton (no template)."""
    # Setup: no config, no convention, no built-in for CUSTOM type
    # Assert: source="none", content=None

def test_legacy_convention_supported(tmp_path):
    """Legacy template-001-<type>.md is discovered."""
    # Setup: legacy template exists
    # Assert: legacy template is used

def test_path_traversal_rejected(tmp_path):
    """Template paths with .. are rejected."""
    # Setup: config has ../../../etc/passwd as template path
    # Assert: path is rejected, falls back to next option
```

**Verification:**

- Run tests: `pytest tests/core/services/test_template_resolution.py`
- Test with real repo that has custom templates

**Post-conditions:**

- `TemplateResolver` service exists
- Resolution follows: config → convention → builtin → skeleton
- Path traversal is prevented
- Both legacy and new conventions are supported
- Convention discovery is namespace-scoped: `docs_dir` (derived from `RepoConfig.docs_root`) determines the template search path, so monorepo namespaces with distinct `docs_root` values will discover different convention templates

---

#### WP-3: Interpolation Engine Refactor

**Pre-conditions:**

- `src/meminit/core/use_cases/new_document.py` has `_apply_common_template_substitutions()` method
- Tests exist for current interpolation behavior

**Implementation steps:**

1. **Extract interpolation logic** to `src/meminit/core/services/template_interpolation.py`:

```python
import re
from datetime import date
from typing import Dict, Optional

class TemplateInterpolator:
    """Handles template placeholder interpolation."""

    # All supported patterns — preferred ({{…}}) listed before legacy ({…}, <…>)
    PATTERNS = [
        # Title
        (r'\{\{\s*title\s*\}\}', 'title'),           # Preferred
        (r'\{\s*title\s*\}', 'title'),               # Legacy
        (r'<Decision Title>', 'title'),              # Legacy (ADR)
        (r'<Feature Title>', 'title'),               # Legacy (FDD)
        # Document ID (new in v2 — NOT a legacy token; see FR-3 note)
        (r'\{\{\s*document_id\s*\}\}', 'document_id'),  # Preferred (new in v2)
        # NOTE: <REPO>, <TYPE>, <SEQ> are handled independently below
        # (repo_prefix, type, seq). There is NO single legacy composite
        # token for document_id. {{document_id}} is a v2 convenience alias.
        # Owner
        (r'\{\{\s*owner\s*\}\}', 'owner'),
        (r'\{\s*owner\s*\}', 'owner'),
        (r'<Team or Person>', 'owner'),              # Legacy (ADR)
        # Status
        (r'\{\{\s*status\s*\}\}', 'status'),
        (r'\{\s*status\s*\}', 'status'),
        # Date
        (r'\{\{\s*date\s*\}\}', 'date'),
        (r'<YYYY-MM-DD>', 'date'),                   # Legacy
        # Repo prefix
        (r'\{\{\s*repo_prefix\s*\}\}', 'repo_prefix'),
        (r'<REPO>', 'repo_prefix'),                  # Legacy
        (r'<PROJECT>', 'repo_prefix'),               # Legacy alias
        # Sequence
        (r'\{\{\s*seq\s*\}\}', 'seq'),
        (r'<SEQ>', 'seq'),                           # Legacy
        # Type
        (r'\{\{\s*type\s*\}\}', 'type'),
        # Area
        (r'\{\{\s*area\s*\}\}', 'area'),
        (r'\{\s*area\s*\}', 'area'),
        # Description (optional)
        (r'\{\{\s*description\s*\}\}', 'description'),
        (r'\{\s*description\s*\}', 'description'),
        # Keywords (optional)
        (r'\{\{\s*keywords\s*\}\}', 'keywords'),
        (r'\{\s*keywords\s*\}', 'keywords'),
        # Related IDs (optional)
        (r'\{\{\s*related_ids\s*\}\}', 'related_ids'),
        (r'\{\s*related_ids\s*\}', 'related_ids'),
    ]

    def __init__(self):
        # Compile patterns for efficiency
        self._compiled_patterns = [
            (re.compile(pattern), key)
            for pattern, key in self.PATTERNS
        ]

    def interpolate(
        self,
        template: str,
        title: str,
        document_id: str,
        owner: str,
        status: str,
        repo_prefix: str,
        seq: str,
        doc_type: str,
        area: Optional[str] = None,
        description: Optional[str] = None,
        keywords: Optional[str] = None,
        related_ids: Optional[str] = None,
    ) -> str:
        """Apply all interpolations to template content.

        Every compiled pattern is applied unconditionally so that
        templates mixing ``{{title}}`` and ``{title}`` are handled
        correctly (both syntaxes resolve to the same value).
        """
        substitutions: Dict[str, str] = {
            'title': title,
            'document_id': document_id,
            'owner': owner,
            'status': status,
            'date': date.today().isoformat(),
            'repo_prefix': repo_prefix,
            'seq': seq,
            'type': doc_type,
            'area': area or '',
            'description': description or '',
            'keywords': keywords or '',
            'related_ids': related_ids or '',
        }

        result = template

        # Apply EVERY pattern — do NOT skip duplicates.
        # A template may legitimately use both {{title}} and {title};
        # both must resolve to the same value.
        for pattern, key in self._compiled_patterns:
            value = substitutions.get(key, '')
            result = pattern.sub(value, result)

        return result
```

2. **Update `new_document.py`** to use `TemplateInterpolator`:

```python
from meminit.core.services.template_interpolation import TemplateInterpolator

class NewDocumentUseCase:
    def __init__(self, root_dir: str):
        # ... existing ...
        self._interpolator = TemplateInterpolator()

    def _execute_internal_impl(self, params: NewDocumentParams, ...):
        # ... existing validation ...

        # Apply interpolation
        template_body = self._interpolator.interpolate(
            template=template_content,
            title=params.title,
            document_id=document_id,
            owner=params.owner,
            status=params.status,
            repo_prefix=ns.repo_prefix,
            seq=seq,
            doc_type=normalized_type,
            area=params.area,
        )
```

**Tests to add:**

```python
# tests/core/services/test_interpolation.py

import pytest
from meminit.core.services.template_interpolation import TemplateInterpolator

def test_preferred_syntax():
    """{{variable}} syntax works."""
    interpolator = TemplateInterpolator()
    result = interpolator.interpolate(
        template="# {{title}}\n\nOwner: {{owner}}",
        title="Test Doc",
        document_id="REPO-PRD-001",
        owner="Test Owner",
        status="Draft",
        repo_prefix="REPO",
        seq="001",
        doc_type="PRD"
    )
    assert result == "# Test Doc\n\nOwner: Test Owner"

def test_legacy_brace_syntax():
    """Legacy {variable} syntax still works."""
    interpolator = TemplateInterpolator()
    result = interpolator.interpolate(
        template="# {title}\nID: {document_id}",
        title="Test Doc",
        document_id="REPO-PRD-001",
        owner="Test Owner",
        status="Draft",
        repo_prefix="REPO",
        seq="001",
        doc_type="PRD"
    )
    assert result == "# Test Doc\nID: REPO-PRD-001"

def test_legacy_angle_syntax():
    """Legacy <VAR> syntax still works."""
    interpolator = TemplateInterpolator()
    result = interpolator.interpolate(
        template="ID: <REPO>-<TYPE>-<SEQ>\nDate: <YYYY-MM-DD>",
        title="Test",
        document_id="REPO-PRD-001",
        owner="Owner",
        status="Draft",
        repo_prefix="REPO",
        seq="001",
        doc_type="PRD"
    )
    assert "REPO-PRD-001" in result
    assert result.count("REPO-PRD-001") == 1  # Not substituted multiple times

def test_unknown_variables_preserved():
    """Unknown {{variables}} are preserved verbatim."""
    interpolator = TemplateInterpolator()
    result = interpolator.interpolate(
        template="{{title}} {{unknown}} {{also_unknown}}",
        title="Test",
        document_id="REPO-PRD-001",
        owner="Owner",
        status="Draft",
        repo_prefix="REPO",
        seq="001",
        doc_type="PRD"
    )
    assert result == "Test {{unknown}} {{also_unknown}}"

def test_all_supported_variables():
    """All documented variables are interpolated."""
    # Test full set
```

**Verification:**

- Run tests: `pytest tests/core/services/test_interpolation.py`
- Verify existing template behavior is preserved

**Post-conditions:**

- `TemplateInterpolator` service exists
- All syntaxes work: `{{}}`, `{}`, `<>`
- Unknown variables are preserved
- No double-substitution issues

---

#### WP-4: Metadata Block Rule

**Pre-conditions:**

- `src/meminit/core/use_cases/new_document.py` generates metadata block
- Templates may have `<!-- MEMINIT_METADATA_BLOCK -->` marker

**Implementation steps:**

1. **Add metadata block processing** in `new_document.py`:

```python
def _process_template_metadata_block(self, template_content: str, generated_metadata: str) -> str:
    """
    Process template metadata block marker and placeholder.

    Rules:
    1. If marker + placeholder blockquote exists: replace blockquote
    2. If marker only: insert after marker
    3. If no marker: insert after frontmatter
    """
    lines = template_content.splitlines()

    # Find frontmatter end
    frontmatter_end = 0
    if lines and lines[0].startswith('---'):
        for i, line in enumerate(lines[1:], 1):
            if line == '---':
                frontmatter_end = i + 1
                break

    # Find metadata block marker
    marker_line = None
    for i, line in enumerate(lines):
        if '<!-- MEMINIT_METADATA_BLOCK -->' in line:
            marker_line = i
            break

    if marker_line is None:
        # No marker: insert after frontmatter
        lines.insert(frontmatter_end, generated_metadata)
        return '\n'.join(lines)

    # Marker exists: check for placeholder blockquote
    # Placeholder blockquote starts with "> " immediately after marker
    placeholder_start = None
    placeholder_end = None

    for i in range(marker_line + 1, len(lines)):
        if lines[i].startswith('> **'):
            placeholder_start = i
            # Find end of blockquote
            for j in range(i + 1, len(lines)):
                if not lines[j].startswith('>'):
                    placeholder_end = j
                    break
            break

    if placeholder_start is not None and placeholder_end is not None:
        # Replace placeholder blockquote
        result_lines = (
            lines[:placeholder_start] +
            [generated_metadata] +
            lines[placeholder_end:]
        )
        return '\n'.join(result_lines)
    else:
        # Insert after marker
        lines.insert(marker_line + 1, generated_metadata)
        return '\n'.join(lines)
```

2. **Integrate into template application**:

```python
def _apply_template(self, template_content: str, ...) -> str:
    # ... apply interpolation ...

    # Process metadata block
    generated_metadata_block = self._generate_metadata_block(...)
    template_content = self._process_template_metadata_block(
        template_content,
        generated_metadata_block
    )

    return template_content
```

**Tests to add:**

```python
# tests/core/use_cases/test_metadata_block.py

def test_metadata_block_with_marker_and_placeholder():
    """Marker + placeholder blockquote → replace blockquote."""
    template = '''---
---
<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** <REPO>-ADR-<SEQ>
> **Owner:** <Owner>

# Title
'''
    result = process_template(template, ...)
    assert result.count('> **Document ID:**') == 1  # No duplicates

def test_metadata_block_with_marker_only():
    """Marker only → insert after marker."""
    template = '''---
---
<!-- MEMINIT_METADATA_BLOCK -->

# Title
'''
    result = process_template(template, ...)
    assert '> **Document ID:**' in result

def test_metadata_block_no_marker():
    """No marker → insert after frontmatter."""
    template = '''---
---

# Title
'''
    result = process_template(template, ...)
    assert '> **Document ID:**' in result

def test_no_duplicate_metadata_blocks():
    """Final document never has duplicate metadata blocks."""
    # Various template configurations
    assert result.count('> **Document ID:**') == 1
```

**Verification:**

- Run tests: `pytest tests/core/use_cases/test_metadata_block.py`
- Test with existing templates

**Post-conditions:**

- Exactly one metadata block in final document
- Marker + placeholder → replace placeholder
- Marker only → insert after marker
- No marker → insert after frontmatter

---

#### WP-5: Built-in Templates

**Pre-conditions:**

- `TemplateResolver` can load built-in templates
- Package assets directory exists at `src/meminit/core/assets/org_profiles/default/templates/`

**Implementation steps:**

1. **Create built-in templates** in `src/meminit/core/assets/org_profiles/default/templates/`:

```bash
src/meminit/core/assets/org_profiles/default/templates/
├── adr.template.md
├── prd.template.md
└── fdd.template.md
```

2. **Create ADR template** (`adr.template.md`) — The complete ADR template body is defined in [Section 9.3](#93-complete-canonical-template-example) (for PRD) and the archetype inventory in [Appendix A](#21-appendix-a-canonical-content-inventory-archetypes). The ADR template MUST include:

   | Contract Element          | Required Sections (archetype IDs)                                                                                                                                                                                                                                    |
   | ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
   | **Frontmatter**           | `template_type: adr-standard`, `template_version: 2.0`                                                                                                                                                                                                               |
   | **Metadata block**        | `<!-- MEMINIT_METADATA_BLOCK -->` with placeholder blockquote                                                                                                                                                                                                        |
   | **Sections with markers** | `context`, `forces`, `decision_drivers`, `options`, `option_a`–`option_c`, `decision`, `consequences`, `consequences_positive`, `consequences_negative`, `consequences_followup`, `impl_notes`, `validation`, `alternatives_rejected`, `supersession`, `agent_notes` |
   | **Agent guidance**        | `<!-- AGENT: ... -->` block after each section marker                                                                                                                                                                                                                |

   > Implementors: See the existing `template-001-adr.md` in `src/meminit/core/assets/org_profiles/default/templates/` for the v1 baseline. The v2 template adds section markers and agent guidance to this existing structure.

3. **Create PRD template** (`prd.template.md`) — Use the canonical example from [Section 9.3](#93-complete-canonical-template-example)

4. **Create FDD template** (`fdd.template.md`) — Similar structure with appropriate sections from Appendix A

**Tests to add:**

```python
# tests/core/assets/test_builtin_templates.py

def test_builtin_adr_template_has_section_markers():
    """Built-in ADR template includes section markers."""
    resolver = TemplateResolver(config)
    resolution = resolver.resolve("ADR")
    assert resolution.source == "builtin"
    assert "<!-- MEMINIT_SECTION:" in resolution.content

def test_builtin_prd_template_has_section_markers():
    """Built-in PRD template includes section markers."""
    # Similar test

def test_builtin_fdd_template_has_section_markers():
    """Built-in FDD template includes section markers."""
    # Similar test

def test_builtin_templates_have_agent_guidance():
    """Built-in templates include AGENT guidance blocks."""
    # Check for <!-- AGENT: ... --> in each template
```

**Verification:**

```bash
# WP-5 Verification
pytest tests/core/assets/test_builtin_templates.py -v
# Test no-config repo gets built-in
cd /tmp && rm -rf test_repo && mkdir test_repo && cd test_repo && \
  meminit new ADR "Test" --format json | jq '.data.template.source'
# Should output: "builtin"
```

- Run tests: `pytest tests/core/assets/test_builtin_templates.py`
- Test no-config repo: `meminit new ADR "Test" --format json`
- Verify `data.template.source` is `"builtin"` for ADR/PRD/FDD
- Verify section markers present in generated documents

**Post-conditions:**

- ADR, PRD, FDD templates exist in package assets
- All templates have section markers
- All templates have agent guidance
- Templates are discovered by resolver

---

#### WP-6: JSON Output Enhancements

**Pre-conditions:**

- `src/meminit/core/use_cases/new_document.py` returns JSON via `output_contracts.py`
- `TemplateResolver` tracks template source

**Implementation steps:**

1. **Update `NewDocumentResult`** in `entities.py`:

```python
@dataclass(frozen=True)
class NewDocumentResult:
    success: bool
    # ... existing fields ...
    template_source: Optional[str] = None  # "config", "convention", "builtin", "none"
    template_path: Optional[str] = None
    sections: List[Dict[str, Any]] = field(default_factory=list)
```

2. **Add section parsing** to `new_document.py`:

```python
def _extract_sections(self, content: str) -> List[Dict[str, Any]]:
    """Extract section information from document content.

    Handles the common pattern where a blank line separates
    the heading from its section marker:

        ## 2. Problem Statement
                                     <-- blank line
        <!-- MEMINIT_SECTION: problem_statement -->
    """
    sections = []
    lines = content.splitlines()
    last_heading = None
    last_heading_line = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Track the most recent heading (## or ###)
        if stripped.startswith('##'):
            last_heading = stripped
            last_heading_line = i
            continue

        # Check for section marker
        marker_match = re.match(
            r'<!--\s*MEMINIT_SECTION:\s*(\w+)\s*-->', stripped
        )
        if marker_match:
            section_id = marker_match.group(1)
            sections.append({
                "id": section_id,
                "heading": last_heading or "Unknown",
                "line": last_heading_line,
                "required": True  # For now, all sections are required
            })

    return sections
```

3. **Update JSON output** to include new fields:

```python
def _execute_internal_impl(self, params: NewDocumentParams, ...):
    # ... existing logic ...

    # Extract sections
    sections = self._extract_sections(final_content)

    return NewDocumentResult(
        success=True,
        doc_type=params.doc_type,
        path=target_path,
        template_source=resolution.source,
        template_path=str(resolution.path) if resolution.path else None,
        sections=sections,
        # ... other fields ...
    )
```

4. **Update JSON formatting for `command: new`** to include template details inside the v2 envelope (`output_schema_version: 2.0`) per MEMINIT-SPEC-004.

**Contract shape (high-level):**

```python
# Envelope is unchanged; we extend `data` (command payload).
data["template"] = {
    "applied": True,
    "source": "config|convention|builtin|none",
    "path": "docs/00-governance/templates/prd.template.md" or None,
    "content_preview": "...",
    "sections": [
        {"id": "executive_summary", "heading": "## 1. Executive Summary", "line": 42, "required": True, "agent_prompt": "..."},
    ],
}
```

**Tests to add:**

```python
# tests/core/use_cases/test_new_json_output.py

def test_json_output_includes_template_source(tmp_path):
    """JSON output includes data.template.source field."""
    result = run_new_document_json(tmp_path, "PRD", "Test")
    assert result["data"]["template"]["source"] in ["config", "convention", "builtin", "none"]

def test_json_output_includes_sections(tmp_path):
    """JSON output includes sections array."""
    result = run_new_document_json(tmp_path, "PRD", "Test")
    sections = result["data"]["template"]["sections"]
    assert len(sections) > 0
    assert "id" in sections[0]
    assert "heading" in sections[0]

def test_json_output_includes_content_preview(tmp_path):
    """JSON output includes content_preview."""
    result = run_new_document_json(tmp_path, "PRD", "Test")
    assert len(result["data"]["template"]["content_preview"]) <= 500

def test_json_output_template_source_builtin(tmp_path):
    """No-config repo gets builtin template."""
    # Fresh repo with no templates
    result = run_new_document_json(tmp_path, "PRD", "Test")
    assert result["data"]["template"]["source"] == "builtin"
```

**Verification:**

```bash
# WP-6 Verification
pytest tests/core/use_cases/test_new_json_output.py -v
# Test JSON output manually
meminit new PRD "Widget Platform" --format json | jq '.data.template.source, .data.template.sections[0], .data.template.content_preview'
```

- Run tests: `pytest tests/core/use_cases/test_new_json_output.py`
- Test JSON output manually: `meminit new PRD "Test" --format json`
- Verify `data.template.source` exists and has correct value
- Verify `sections` array contains id, heading, line fields
- Verify `content_preview` is present and <= 500 chars

**Post-conditions:**

- JSON includes `data.template.source`
- JSON includes `data.template.sections` with id, heading, line
- JSON includes `data.template.content_preview`
- JSON schema is documented

---

#### WP-7: Update Vendored Templates

**Pre-conditions:**

- Built-in templates exist (from WP-5)
- Vendored templates exist in `docs/00-governance/templates/`

**Implementation steps:**

1. **Update `template-001-adr.md`** to match built-in template:
   - Add section markers to all major sections
   - Add agent guidance blocks
   - Convert placeholders to `{{}}` syntax (optional, can keep legacy)

2. **Update `template-001-prd.md`** to match built-in template:
   - Add comprehensive sections
   - Add section markers
   - Add agent guidance blocks

3. **Update `template-001-fdd.md`** to match built-in template:
   - Add section markers
   - Add agent guidance blocks

4. **Add `.template.md` variants** (new convention):
   - Copy updated templates to `adr.template.md`, `prd.template.md`, `fdd.template.md`
   - This allows repos to use either convention

**Verification:**

```bash
# WP-7 Verification
# Test convention discovery works
meminit new ADR "Convention Test" --format json | jq '.data.template.source'
# Should output: "convention"

# Verify both conventions work
meminit new PRD "Legacy Test" --format json | jq '.data.template.source'
# Should output: "convention"

# Check markers present
meminit new ADR "Marker Test" --format json | jq -r '.content_preview' | grep -c "MEMINIT_SECTION"
# Should be > 0
```

- Run: `meminit check` to verify PRD compliance
- Test: `meminit new ADR "Test"` generates document with section markers
- Test: `meminit new PRD "Test"` generates document with comprehensive structure
- Verify both legacy (`template-001-*.md`) and new (`*.template.md`) conventions work

**Post-conditions:**

- Vendored templates match built-in templates
- Both legacy and new conventions work
- All templates have section markers
- All templates have agent guidance

---

#### WP-8: Documentation and PRD Update

**Pre-conditions:**

- All implementation work is complete
- All tests pass

**Implementation steps:**

1. **Update this PRD** with final implementation details:
   - Confirm all sections are accurate
   - Update version to "1.0"
   - Update status to "Approved" if approved

2. **Update README** or user docs:
   - Document template configuration options
   - Document placeholder syntaxes
   - Provide template examples

3. **Add migration guide** (if needed):
   - How to update from legacy to new config
   - How to add custom templates

4. **Update `meminit context` output** to include template info:
   - For each document type, show template source
   - Show template path if configured

**Verification:**

```bash
# WP-8 Verification
# Final integration test
pytest tests/ -v --tb=short

# Verify meminit context includes template info
meminit context --format json | jq '.document_types'

# Verify this PRD is in review status
grep "status:" docs/10-prd/prd-006-document-templates.md
# Should output: "status: In Review"
```

- Run: `meminit check` to verify PRD compliance
- Run full test suite: `pytest tests/ -v`
- Verify `meminit context --format json` shows template info
- Review docs for clarity

**Post-conditions:**

- Documentation is up to date
- This PRD is marked "Approved" or "In Review"
- Users understand how to use Templates v2

---

### 12.5 Work Package Dependencies

```mermaid
graph TD
    WP1[WP-1: document_types config] --> WP2[WP-2: template resolver]
    WP1 --> WP3[WP-3: interpolation]
    WP1 --> WP4[WP-4: metadata block]

    WP2 --> WP5[WP-5: built-in templates]
    WP3 --> WP5
    WP4 --> WP5

    WP5 --> WP6[WP-6: JSON output]
    WP6 --> WP7[WP-7: vendored templates]
    WP6 --> WP8[WP-8: docs update]
```

**Recommended execution order:** WP-1 → WP-2 → WP-3 → WP-4 → WP-5 → WP-6 → WP-7 → WP-8

**Parallelization opportunities:**

- WP-3, WP-4 can be done in parallel after WP-1
- WP-5 template authoring (file creation) can begin in parallel, but its integration tests require WP-2 (`TemplateResolver`). Use mock resolver if parallelizing.
- WP-7 can be done in parallel with WP-6

**Rollback guidance (per WP):**

If a WP introduces failing tests or breaks backward compatibility:

| WP   | If it fails, revert...                                                                          |
| ---- | ----------------------------------------------------------------------------------------------- |
| WP-1 | `repo_config.py` changes only; existing `type_directories` / `templates` behavior is unaffected |
| WP-2 | `template_resolver.py` (new file); restore `_load_template()` in `new_document.py`              |
| WP-3 | `template_interpolation.py` (new file); restore `_apply_common_template_substitutions()`        |
| WP-4 | `_process_template_metadata_block()` in `new_document.py`; revert to existing inline logic      |
| WP-5 | Delete new template files from `src/meminit/core/assets/org_profiles/default/templates/`        |
| WP-6 | Revert `NewDocumentResult` and `output_contracts.py` changes; JSON output returns to v1 shape   |
| WP-7 | Revert updated files in `docs/00-governance/templates/`; existing templates restored via git    |
| WP-8 | Documentation-only; no code rollback needed                                                     |

---

## 13. Acceptance Criteria

<!-- MEMINIT_SECTION: acceptance_criteria -->

<!-- AGENT: Define "done" for this feature. Each criterion must be testable and linked to requirements. -->

| ID        | Criterion                                                                       | Verification Command                                                                                   | Related FRs | Related WP(s) |
| --------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ----------- | ------------- |
| **AC-1**  | `meminit new ADR "X"` produces scaffold with stable section IDs                 | `pytest tests/core/services/test_template_resolution.py::test_resolution_precedence -v`                | FR-5        | WP-5          |
| **AC-2**  | Legacy `{title}` and `<REPO>` placeholders interpolate correctly                | `pytest tests/core/services/test_interpolation.py::test_legacy_brace_syntax -v`                        | FR-3        | WP-3          |
| **AC-3**  | New `{{title}}` placeholder syntax works                                        | `pytest tests/core/services/test_interpolation.py::test_preferred_syntax -v`                           | FR-3        | WP-3          |
| **AC-4**  | Exactly one visible metadata block in final document                            | `pytest tests/core/use_cases/test_metadata_block.py::test_no_duplicate_metadata_blocks -v`             | FR-8        | WP-4          |
| **AC-5**  | Template discovery follows precedence: config → convention → builtin → skeleton | `pytest tests/core/services/test_template_resolution.py::test_resolution_precedence_config_first -v`   | FR-1        | WP-2          |
| **AC-6**  | `--format json` includes `data.template.source` and `data.template.sections`   | `pytest tests/core/use_cases/test_new_json_output.py::test_json_output_includes_template_source -v`    | FR-7        | WP-6          |
| **AC-7**  | Path traversal via template path is rejected safely                             | `pytest tests/core/services/test_template_resolution.py::test_path_traversal_rejected -v`              | FR-10       | WP-2          |
| **AC-8**  | `meminit new PRD "X"` without config produces meaningful scaffold               | `pytest tests/core/assets/test_builtin_templates.py::test_builtin_prd_template_has_section_markers -v` | FR-1, FR-5  | WP-2, WP-5    |
| **AC-9**  | `document_types` config takes precedence over legacy config                     | `pytest tests/core/services/test_repo_config.py::test_document_types_config_precedence -v`             | FR-6        | WP-1          |
| **AC-10** | `<!-- AGENT: ... -->` blocks preserved in output                                | `pytest tests/core/services/test_interpolation.py::test_agent_prompt_preservation -v`                  | FR-4        | WP-5          |
| **AC-11** | Template frontmatter merged with generated metadata                             | `pytest tests/core/services/test_interpolation.py::test_frontmatter_merging -v`                        | FR-9        | WP-3          |
| **AC-12** | Both legacy and new template file conventions supported                         | `pytest tests/core/services/test_template_resolution.py::test_legacy_convention_supported -v`          | FR-11       | WP-2          |
| **AC-13** | JSON output section inventory matches document content                          | `pytest tests/core/use_cases/test_new_json_output.py::test_json_output_includes_sections -v`           | FR-7        | WP-6          |
| **AC-14** | Unknown `{{variables}}` preserved verbatim                                      | `pytest tests/core/services/test_interpolation.py::test_unknown_variables_preserved -v`                | FR-3        | WP-3          |
| **AC-15** | Built-in templates for ADR, PRD, FDD include section markers                    | `pytest tests/core/assets/test_builtin_templates.py -v`                                                | FR-5        | WP-5          |
| **AC-16** | Full end-to-end flow: config → resolve → interpolate → metadata → JSON output   | `pytest tests/integration/test_templates_v2_e2e.py -v`                                                 | FR-1–FR-11  | WP-1–WP-6     |

---

## 14. Test Plan

<!-- MEMINIT_SECTION: test_plan -->

<!-- AGENT: Define comprehensive test coverage. Include unit tests, integration tests, and test fixtures. -->

### 14.1 Unit Tests

| Test Area                | Key Tests                                                                                                   |
| ------------------------ | ----------------------------------------------------------------------------------------------------------- |
| **Config parsing**       | `test_document_types_parsing`, `test_legacy_compat`, `test_mixed_config`                                    |
| **Template resolution**  | `test_precedence_config`, `test_precedence_convention`, `test_precedence_builtin`, `test_fallback_skeleton` |
| **Interpolation**        | `test_all_syntaxes`, `test_unknown_preserved`, `test_no_double_sub`                                         |
| **Metadata block**       | `test_marker_with_placeholder`, `test_marker_only`, `test_no_marker`, `test_no_duplicates`                  |
| **Section markers**      | `test_marker_preservation`, `test_section_extraction`                                                       |
| **Path security**        | `test_path_traversal_rejected`, `test_symlink_rejected`                                                     |
| **Frontmatter merging**  | `test_template_frontmatter_preserved`, `test_generated_overrides`                                           |
| **Convention discovery** | `test_new_convention`, `test_legacy_convention`                                                             |

### 14.2 Integration Tests

| Test                           | Description                                                 |
| ------------------------------ | ----------------------------------------------------------- |
| **CLI JSON output**            | `meminit new ... --format json` returns all required fields |
| **No-config repo**             | Fresh repo produces meaningful scaffolds                    |
| **Configured repo**            | Config overrides built-ins deterministically                |
| **Legacy templates**           | Old templates with `{title}` still work                     |
| **Mixed config**               | `document_types` + legacy config coexist                    |
| **Convention discovery**       | Templates found in `docs/00-governance/templates/`          |
| **Cross-WP full flow (AC-16)** | Config → resolve → interpolate → metadata → JSON output     |
| **Dry-run mode**               | `--dry-run` doesn't write files, shows output               |
| **Generated docs pass check**  | New docs pass `meminit check`                               |

### 14.3 Test Fixtures

| Fixture                     | Location                                            | Contents                                       | Used By    |
| --------------------------- | --------------------------------------------------- | ---------------------------------------------- | ---------- |
| `repo_with_document_types/` | `tests/fixtures/repo_with_document_types/`          | Config with `document_types` block             | WP-1       |
| `repo_with_legacy_config/`  | `tests/fixtures/repo_with_legacy_config/`           | Config with `type_directories` + `templates`   | WP-1       |
| `repo_mixed_config/`        | `tests/fixtures/repo_mixed_config/`                 | Mixed `document_types` + legacy                | WP-1       |
| `repo_with_templates/`      | `tests/fixtures/repo_with_templates/`               | Templates in convention paths                  | WP-2       |
| `repo_empty/`               | `tests/fixtures/repo_empty/`                        | No config, no templates (tests built-ins)      | WP-5, WP-6 |
| `template_legacy.md`        | `tests/fixtures/templates/template_legacy.md`       | Old template with `{title}` placeholders       | WP-3       |
| `template_new.md`           | `tests/fixtures/templates/template_new.md`          | New template with `{{title}}` + markers        | WP-3, WP-4 |
| `template_mixed_syntax.md`  | `tests/fixtures/templates/template_mixed_syntax.md` | Template with both `{title}` and `{{owner}}`   | WP-3       |
| `template_with_markers.md`  | `tests/fixtures/templates/template_with_markers.md` | Template with section markers and AGENT blocks | WP-4, WP-6 |

### 14.4 Edge-Case and Boundary Tests

| Test Case                             | Description                                             | Expected Outcome                                          |
| ------------------------------------- | ------------------------------------------------------- | --------------------------------------------------------- |
| **Unicode/emoji in title**            | `meminit new PRD "🚀 Ünïcödé Plàtform" --format json`   | Title preserved verbatim in frontmatter and body          |
| **Very long title (500+ chars)**      | Title exceeding typical filename limits                 | Filename truncated safely; title preserved in frontmatter |
| **Mixed legacy + preferred syntax**   | Template contains both `{title}` and `{{owner}}`        | Both syntaxes interpolated correctly                      |
| **Empty template body**               | Template file exists but has only frontmatter, no body  | Document created with frontmatter only; no crash          |
| **Malformed YAML in template**        | Template frontmatter has invalid YAML (unclosed quotes) | Graceful error; no partial file written                   |
| **Template with unknown variables**   | Template contains `{{custom_var}}` not in vocabulary    | Variable preserved verbatim in output                     |
| **Nested section markers**            | Template contains markers inside code fences            | Code-fenced markers treated as content, not parsed        |
| **Duplicate section IDs in template** | Two sections share the same `MEMINIT_SECTION` id        | Warning emitted; first occurrence used                    |
| **Path traversal in template path**   | Config points to `../../etc/passwd`                     | Rejected with security error                              |
| **Concurrent writes**                 | Two `meminit new` calls with same type + sequence       | Second call fails or increments sequence; no data loss    |
| **Empty repo prefix**                 | Config has `repo_prefix: ""`                            | Document ID still valid; no leading hyphen                |

---

## 15. Rollout and Migration

<!-- MEMINIT_SECTION: rollout_migration -->

### 15.1 Rollout Strategy

| Phase                           | Deliverables                                                   | Compatibility            |
| ------------------------------- | -------------------------------------------------------------- | ------------------------ |
| **Phase 1: Foundation**         | `{{}}` interpolation, convention discovery, built-in templates | 100% backward compatible |
| **Phase 2: Unified Config**     | `document_types` schema, `meminit context` updates             | 100% backward compatible |
| **Phase 3: Enhanced Templates** | Section markers, agent guidance in all templates               | 100% backward compatible |
| **Phase 4: Polish**             | Updated docs, deprecation warnings (if any)                    | 100% backward compatible |

**No breaking changes are planned.**

### 15.2 Migration Guide for Repo Owners

#### Option A: Stay on Legacy Config (No Action Required)

Your existing config continues to work:

```yaml
type_directories:
  ADR: "45-adr"
  PRD: "10-prd"

templates:
  adr: "docs/00-governance/templates/template-001-adr.md"
  prd: "docs/00-governance/templates/template-001-prd.md"
```

#### Option B: Migrate to `document_types` (Optional)

**Before:**

```yaml
type_directories:
  ADR: "45-adr"
  PRD: "10-prd"

templates:
  adr: "docs/00-governance/templates/template-001-adr.md"
  prd: "docs/00-governance/templates/template-001-prd.md"
```

**After:**

```yaml
document_types:
  ADR:
    directory: "45-adr"
    template: "docs/00-governance/templates/template-001-adr.md"
    description: "Architecture Decision Record"
  PRD:
    directory: "10-prd"
    template: "docs/00-governance/templates/template-001-prd.md"
    description: "Product Requirements Document"
```

**Benefits of migration:**

- Unified configuration per document type
- `description` field for better `meminit context` output
- Future-proof for additional per-type options

#### Option C: Enhance Your Templates

**Add section markers:**

```markdown
## 2. Problem Statement

<!-- MEMINIT_SECTION: problem_statement -->

<!-- AGENT: Quantify the problem with data. -->
```

**Benefits:**

- Agents can fill sections without heading heuristics
- Consistent structure across documents

### 15.3 Verification

After any changes, verify:

```bash
# Check configuration
meminit doctor

# Test template resolution
meminit new ADR "Test" --dry-run

# Validate generated docs
meminit check docs/
```

---

## 16. Security and Safety

<!-- MEMINIT_SECTION: security_safety -->

### 16.1 Security Considerations

| Threat                   | Mitigation                                                          |
| ------------------------ | ------------------------------------------------------------------- |
| **Path traversal**       | Template paths validated as repo-relative; `..` components resolved |
| **Symlink escapes**      | Symlinks outside repo root are rejected                             |
| **Code execution**       | Templates are static text; no eval/exec                             |
| **Template injection**   | User-provided templates not supported (repo-controlled only)        |
| **Secrets in templates** | Warning in docs; agents instructed to avoid secrets                 |

### 16.2 Safety Guidelines for Agents

1. **Never insert secrets:** Do not include credentials, API keys, or tokens in documents
2. **Never insert PII:** Do not include personal data unless explicitly required
3. **Treat all requirements as testable:** Every FR/AC should be verifiable
4. **Preserve structure:** Never reorder or invent sections
5. **Validate output:** Always run `meminit check` before completing

---

## 17. Risks and Mitigations

<!-- MEMINIT_SECTION: risks -->

<!-- AGENT: Identify technical, product, and operational risks. Include mitigations. -->

| Risk                                                 | Impact | Likelihood | Mitigation                                                                                                     |
| ---------------------------------------------------- | ------ | ---------- | -------------------------------------------------------------------------------------------------------------- |
| **Template contract becomes "yet another standard"** | High   | Medium     | Treat templates as versioned artifacts (`template_type`/`template_version`); keep compatibility rules explicit |
| **Orchestrators ignore section markers**             | Medium | Medium     | Expose section inventory in JSON; future: structural linting in `meminit check`                                |
| **Added config complexity**                          | Medium | Low        | Keep `document_types` optional; legacy config supported indefinitely                                           |
| **Built-in templates become opinionated**            | Low    | Medium     | Keep built-ins minimal; encourage repo overrides                                                               |
| **Performance regression**                           | Low    | Low        | Template resolution is I/O-bound; caching can be added if needed                                               |

---

## 18. Resolved Design Questions

<!-- MEMINIT_SECTION: resolved_questions -->

<!-- AGENT: These questions were raised during design and have been resolved. They are preserved here for rationale traceability. -->

| #   | Question                                                                             | Decision             | Rationale                                                                                                                                                                                                    |
| --- | ------------------------------------------------------------------------------------ | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | Should section IDs be enforced during `meminit check` (structural linting)?          | Agents only, for now | Enforcement adds complexity; defer to future scope (NG-1). Agents use section IDs for filling; linting is a separate feature.                                                                                |
| 2   | Should Meminit expose `meminit template resolve <TYPE> --format json` for debugging? | Deferred             | `meminit context` can be extended to surface template info (see WP-8). A dedicated command is premature.                                                                                                     |
| 3   | Should template frontmatter be restricted to "template metadata" keys only?          | No restriction       | Templates can define arbitrary frontmatter. Only required fields (`document_id`, `type`, `title`, `status`, `owner`, `version`, `last_updated`, `docops_version`) are overridden by generated values (FR-9). |
| 4   | Should section markers include an explicit order field?                              | No                   | Order is implied by document position. An explicit field adds maintenance burden with no clear benefit.                                                                                                      |

---

## 19. Future Scope (Deferred)

<!-- MEMINIT_SECTION: future_scope -->

| Item                                      | Notes                                                                              |
| ----------------------------------------- | ---------------------------------------------------------------------------------- |
| **Structural linting in `meminit check`** | Validate required sections exist and are non-empty; detect missing markers         |
| **OrgConfig template inheritance**        | Share templates across repos with controlled overrides                             |
| **Architext auto-sync**                   | Generate/validate section IDs across both systems                                  |
| **Template listing command**              | `meminit template list` or `meminit template resolve <TYPE>` for diagnostics       |
| **Template caching**                      | Cache resolved templates for performance in large repos                            |
| **Section-level validation**              | Validate section content against rules (e.g., "must have at least 3 requirements") |

---

## 20. Related Documents

<!-- MEMINIT_SECTION: related_docs -->

<!-- AGENT: Link to related specs, ADRs, PRDs by Document ID. -->

| Document ID                                                             | Title                                   | Relationship                                               |
| ----------------------------------------------------------------------- | --------------------------------------- | ---------------------------------------------------------- |
| [MEMINIT-PRD-002](prd-002-new-file-function.md)                         | Enhanced Document Factory (meminit new) | Defines `meminit new`; templates are a critical sub-system |
| [MEMINIT-PRD-003](prd-003-agent-interface-v1.md)                        | Agent Interface v1                      | Defines JSON envelope contract; templates add fields       |
| [MEMINIT-PRD-004](prd-004-brownfield-adoption-hardening.md)             | Brownfield Adoption Hardening           | Templates reduce heuristic guessing for migrations         |
| [MEMINIT-PLAN-003](../05-planning/plan-003-roadmap.md)                  | Project Roadmap                         | Templates are a roadmap item                               |
| [MEMINIT-STRAT-001](../02-strategy/strat-001-project-meminit-vision.md) | Project Meminit Vision                  | Templates support "standardization at creation time"       |
| [MEMINIT-GOV-003](../00-governance/gov-003-security-practices.md)       | Security Practices                      | Agents must follow security guidelines                     |

---

## 21. Appendix A: Canonical Content Inventory (Archetypes)

<!-- MEMINIT_SECTION: appendix_archetypes -->

<!-- AGENT: This appendix defines the stable content archetype IDs that can be used across templates. -->

This inventory defines stable IDs that templates and agents can share.

| ID                      | Default Heading               | Common Types   | Notes                              |
| ----------------------- | ----------------------------- | -------------- | ---------------------------------- |
| `executive_summary`     | Executive Summary             | PRD, FDD       | Time-constrained overview          |
| `toc`                   | Table of Contents             | All            | Auto-generated or manual           |
| `problem_statement`     | Problem Statement             | PRD, FDD       | What is broken and for whom        |
| `problem_impact`        | Impact                        | PRD, FDD       | Who is impacted, how badly         |
| `value_proposition`     | Value Proposition             | PRD            | Value framing and trade-offs       |
| `personas`              | Personas & Pain Points        | PRD            | Primary users and friction         |
| `scope`                 | Scope & Feature Overview      | PRD, FDD       | In/out of scope boundaries         |
| `goals_nongoals`        | Goals and Non-Goals           | PRD, ADR, FDD  | Explicit boundaries                |
| `nongoals`              | Non-Goals                     | PRD, ADR, FDD  | Explicitly out of scope            |
| `requirements_func`     | Functional Requirements       | PRD, SPEC      | Testable behaviors                 |
| `requirements_nonfunc`  | Non-Functional Requirements   | PRD, SPEC, FDD | Performance/security/accessibility |
| `acceptance_criteria`   | Acceptance Criteria           | PRD, FDD, TASK | Definition of done (testable)      |
| `context`               | Context & Problem Statement   | ADR            | Forces and constraints             |
| `forces`                | Forces and Constraints        | ADR            | Decision drivers                   |
| `decision_drivers`      | Decision Drivers              | ADR            | Criteria for evaluation            |
| `options`               | Options Considered            | ADR            | Alternatives with pros/cons        |
| `option_a`              | Option A                      | ADR            | Specific option details            |
| `option_b`              | Option B                      | ADR            | Specific option details            |
| `option_c`              | Option C                      | ADR            | Specific option details            |
| `decision`              | Decision Outcome              | ADR            | Chosen option + rationale          |
| `consequences`          | Consequences                  | ADR            | Trade-offs and follow-ups          |
| `consequences_positive` | Positive                      | ADR            | Benefits                           |
| `consequences_negative` | Negative / Trade-offs         | ADR            | Downsides                          |
| `consequences_followup` | Follow-up Actions             | ADR            | Required work                      |
| `impl_notes`            | Implementation Notes          | TASK, ADR, FDD | Engineering guidance               |
| `validation`            | Validation & Compliance       | ADR, FDD       | Testing and validation             |
| `alternatives_rejected` | Alternatives Rejected         | ADR            | Rejected options                   |
| `supersession`          | Supersession                  | ADR            | Supersedes / Superseded by         |
| `agent_notes`           | Notes for Agents              | ADR            | Future agent reference             |
| `architecture`          | Architecture                  | FDD, SPEC      | Components, flows, diagrams        |
| `interfaces`            | Interfaces                    | FDD, SPEC      | APIs/events/schemas/contracts      |
| `operational`           | Operational Concerns          | FDD, GUIDE     | SLIs/SLOs, rollout, monitoring     |
| `quality`               | Quality & Testing             | FDD            | Test strategy and constraints      |
| `risks`                 | Risks & Mitigations           | PRD, FDD, ADR  | Risk table with mitigations        |
| `dependencies`          | Dependencies                  | TASK, PRD      | Blockers and prerequisites         |
| `related_docs`          | Related Documents             | All            | Cross-links by Document ID         |
| `changelog`             | Changelog                     | PRD, ADR       | Version history                    |
| `appendix_archetypes`   | Appendix: Content Archetypes  | PRD            | This appendix                      |
| `appendix_traceability` | Appendix: Traceability Matrix | PRD            | Requirements traceability          |
| `appendix_errors`       | Appendix: Error Scenarios     | PRD            | Error handling guide               |
| `appendix_fixtures`     | Appendix: Test Fixtures       | PRD            | Test fixture specification         |

---

## 22. Appendix B: Requirements Traceability Matrix

<!-- MEMINIT_SECTION: appendix_traceability -->

<!-- AGENT: Maintain traceability between requirements, work packages, and acceptance criteria. -->

| FR                                           | WP(s)      | AC(s)             | Status  |
| -------------------------------------------- | ---------- | ----------------- | ------- |
| **FR-1: Template Resolution Precedence**     | WP-2       | AC-5, AC-8        | Pending |
| **FR-2: Deterministic Template Application** | WP-3, WP-4 | AC-4              | Pending |
| **FR-3: Interpolation Vocabulary**           | WP-3       | AC-2, AC-3, AC-14 | Pending |
| **FR-4: Agent Prompt Blocks**                | WP-5       | AC-10             | Pending |
| **FR-5: Stable Section IDs**                 | WP-5       | AC-1, AC-15       | Pending |
| **FR-6: Unified document_types Config**      | WP-1       | AC-9              | Pending |
| **FR-7: Agent-Friendly JSON Output**         | WP-6       | AC-6, AC-13       | Pending |
| **FR-8: Metadata Block Rule**                | WP-4       | AC-4              | Pending |
| **FR-9: Template Frontmatter Merging**       | WP-3       | AC-11             | Pending |
| **FR-10: Path Traversal Protection**         | WP-2       | AC-7              | Pending |
| **FR-11: Convention Discovery**              | WP-2       | AC-12             | Pending |

| AC        | FR(s)      | WP(s)      | Test                                              |
| --------- | ---------- | ---------- | ------------------------------------------------- |
| **AC-1**  | FR-5       | WP-5       | `test_builtin_adr_template_has_section_markers()` |
| **AC-2**  | FR-3       | WP-3       | `test_legacy_brace_syntax()`                      |
| **AC-3**  | FR-3       | WP-3       | `test_preferred_syntax()`                         |
| **AC-4**  | FR-2, FR-8 | WP-4       | `test_no_duplicate_metadata_blocks()`             |
| **AC-5**  | FR-1       | WP-2       | `test_resolution_precedence()`                    |
| **AC-6**  | FR-7       | WP-6       | `test_json_output_includes_template_source()`     |
| **AC-7**  | FR-10      | WP-2       | `test_path_traversal_rejected()`                  |
| **AC-8**  | FR-1, FR-5 | WP-2, WP-5 | `test_no_config_repo_gets_builtin_template()`     |
| **AC-9**  | FR-6       | WP-1       | `test_document_types_config_precedence()`         |
| **AC-10** | FR-4       | WP-5       | `test_agent_prompt_preservation()`                |
| **AC-11** | FR-9       | WP-3       | `test_frontmatter_merging()`                      |
| **AC-12** | FR-11      | WP-2       | `test_convention_discovery()`                     |
| **AC-13** | FR-7       | WP-6       | `test_json_sections_match_document()`             |
| **AC-14** | FR-3       | WP-3       | `test_unknown_variables_preserved()`              |
| **AC-15** | FR-5       | WP-5       | `test_all_builtin_templates_have_markers()`       |
| **AC-16** | FR-1–FR-11 | WP-1–WP-6  | `test_templates_v2_full_flow_e2e()`               |

---

## 23. Appendix C: Error Scenarios and Recovery

<!-- MEMINIT_SECTION: appendix_errors -->

<!-- AGENT: Define specific error scenarios with recovery guidance for orchestrators. -->

This appendix provides detailed error scenarios and recovery strategies for agent orchestrators.

### C.1 Error Taxonomy

```mermaid
mindmap
  root((Errors))
    Operational Errors
      Config / Namespace
        CONFIG_MISSING
        UNKNOWN_NAMESPACE
      Document Factory (new)
        UNKNOWN_TYPE
        INVALID_ID_FORMAT
        DUPLICATE_ID
        FILE_EXISTS
        INVALID_STATUS
      Path Safety
        PATH_ESCAPE
      Templates
        TEMPLATE_NOT_FOUND
      System / Unexpected
        UNKNOWN_ERROR
    Compliance Violations
      Found by meminit check
```

### C.2 Error Scenarios

#### E-1: Unknown Document Type

**Scenario:** Orchestrator requests document type not defined in config

```json
{
  "output_schema_version": "2.0",
  "success": false,
  "command": "new",
  "run_id": "00000000-0000-0000-0000-000000000000",
  "root": "/abs/path/to/repo",
  "data": {},
  "warnings": [],
  "violations": [],
  "advice": [],
  "error": {
    "code": "UNKNOWN_TYPE",
    "message": "Unknown document type: INVALID",
    "details": {
      "doc_type": "INVALID",
      "suggestion": "Run 'meminit context --format json' to see valid types"
    }
  }
}
```

**Recovery:**

1. Call `meminit context --format json` to discover valid types
2. Use one of the valid types OR
3. Ask repo owner to add custom type to `docops.config.yaml`

#### E-2: Template Path Traversal

**Scenario:** Configured template path attempts directory escape

```json
{
  "output_schema_version": "2.0",
  "success": false,
  "command": "new",
  "run_id": "00000000-0000-0000-0000-000000000000",
  "root": "/abs/path/to/repo",
  "data": {},
  "warnings": [],
  "violations": [],
  "advice": [],
  "error": {
    "code": "PATH_ESCAPE",
    "message": "Template path escapes repository root",
    "details": {
      "template_path": "../../../etc/passwd",
      "resolved_path": "/etc/passwd"
    }
  }
}
```

**Recovery:**

1. Fix template path in `docops.config.yaml` to be repo-relative
2. Remove `..` components from path
3. Avoid absolute paths; use repo-relative paths only

#### E-3: Template Not Found (Fallback Used)

**Scenario:** Configured template doesn't exist, but fallback available

```json
{
  "output_schema_version": "2.0",
  "success": true,
  "command": "new",
  "run_id": "00000000-0000-0000-0000-000000000000",
  "root": "/abs/path/to/repo",
  "data": {
    "type": "PRD",
    "document_id": "REPO-PRD-001",
    "path": "docs/10-prd/prd-001-example.md",
    "template": {
      "applied": true,
      "source": "builtin",
      "path": null,
      "sections": [],
      "content_preview": "# PRD: Example\\n..."
    }
  },
  "warnings": [
    {
      "code": "TEMPLATE_NOT_FOUND",
      "message": "Configured template not found: docs/00-governance/templates/custom-prd.md; using built-in template",
      "path": "docs/00-governance/templates/custom-prd.md"
    }
  ],
  "violations": [],
  "advice": []
}
```

**Recovery:**

1. No action required - fallback succeeded
2. Optionally fix template path or create missing template

#### E-4: No Template Available

**Scenario:** Unknown type with no built-in template

```json
{
  "output_schema_version": "2.0",
  "success": true,
  "command": "new",
  "run_id": "00000000-0000-0000-0000-000000000000",
  "root": "/abs/path/to/repo",
  "data": {
    "type": "CUSTOM",
    "document_id": "REPO-CUSTOM-001",
    "path": "docs/99-custom/custom-001-custom-doc.md",
    "template": {
      "applied": false,
      "source": "none",
      "path": null,
      "sections": [],
      "content_preview": "# CUSTOM: Custom Doc\\n\\n## Content\\n\\n[Add your content here.]"
    }
  },
  "warnings": [
    {
      "code": "TEMPLATE_NOT_FOUND",
      "message": "No template found for type CUSTOM; using minimal skeleton",
      "path": "docops.config.yaml"
    }
  ],
  "violations": [],
  "advice": []
}
```

**Recovery:**

1. Create custom template in `docs/00-governance/templates/custom.template.md`
2. Or add template to config: `templates: {custom: "path/to/template.md"}`
3. Or proceed with skeleton if structure not important

#### E-5: Metadata Block Duplicate

**Scenario:** Template has placeholder that creates duplicate metadata

**Before Fix:**

```markdown
> **Document ID:** <REPO>-ADR-<SEQ>
> ...
> **Document ID:** REPO-ADR-001 # Duplicate!
```

**Recovery (automatic):**

- WP-4 implementation handles this automatically
- No orchestrator action needed

#### E-6: Invalid Placeholder Syntax

**Scenario:** Template uses unrecognized placeholder

```markdown
# {{unknown_placeholder}}
```

**Result:**

- Placeholder preserved verbatim in output
- No error raised
- Document created successfully

**Recovery:**

1. No action required if placeholder is intentional
2. Or update template to use valid placeholders

### C.3 Recovery Decision Tree

```mermaid
graph TD
    Start((meminit new returns error)) --> E1{Is error.code == 'UNKNOWN_TYPE'?}

    E1 -->|YES| E1_1[Call meminit context] --> E1_2[Use valid type from context]
    E1 -->|NO| E2{Is error.code == 'PATH_ESCAPE'?}

    E2 -->|YES| E2_1[Fix config template path] --> E2_2[Remove .. components]
    E2 -->|NO| E3{Is error.code == 'TEMPLATE_NOT_FOUND'?}

    E3 -->|YES| E3_1{Check if fallback succeeded}
    E3_1 -->|YES| E3_2[Continue warning only]
    E3_1 -->|NO| E3_3[Create template or use skeleton]

    E3 -->|NO| E4[All other errors: Report to user/retry]
```

---

## 24. Appendix D: Test Fixtures Specification

<!-- MEMINIT_SECTION: appendix_fixtures -->

<!-- AGENT: Define concrete test fixtures for implementation and testing. -->

This appendix specifies concrete test fixtures for validating the template system.

### D.1 Fixture: repo_with_document_types

**Location:** `tests/fixtures/repo_with_document_types/`

**docops.config.yaml:**

```yaml
repo_prefix: TEST
docops_version: "2.0"
document_types:
  ADR:
    directory: "45-adr"
    template: "docs/00-governance/templates/adr.template.md"
    description: "Architecture Decision Record"
  PRD:
    directory: "10-prd"
    template: "docs/00-governance/templates/prd.template.md"
    description: "Product Requirements Document"
```

**Expected Behavior:**

- `expected_subdir_for_type("PRD")` → `"10-prd"`
- `get_template_for_type("ADR")` → `"docs/00-governance/templates/adr.template.md"`

### D.2 Fixture: repo_with_legacy_config

**Location:** `tests/fixtures/repo_with_legacy_config/`

**docops.config.yaml:**

```yaml
repo_prefix: LEGACY
docops_version: "2.0"
type_directories:
  ADR: "45-adr"
  PRD: "10-prd"

templates:
  adr: "docs/00-governance/templates/template-001-adr.md"
  prd: "docs/00-governance/templates/template-001-prd.md"
```

**Expected Behavior:**

- Legacy config parses correctly
- All existing tests pass

### D.3 Fixture: repo_mixed_config

**Location:** `tests/fixtures/repo_mixed_config/`

**docops.config.yaml:**

```yaml
repo_prefix: MIXED
docops_version: "2.0"

# New schema for PRD
document_types:
  PRD:
    directory: "10-prd"
    template: "docs/00-governance/templates/prd.template.md"

# Legacy for ADR
type_directories:
  ADR: "45-adr"

templates:
  adr: "docs/00-governance/templates/template-001-adr.md"
```

**Expected Behavior:**

- PRD uses document_types (new schema)
- ADR uses legacy config
- No conflicts

### D.4 Fixture: template_legacy

**Location:** `tests/fixtures/templates/template_legacy.md`

**Content:**

```markdown
---
template_type: legacy-test
template_version: 1.0
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** <REPO>-TST-<SEQ>
> **Owner:** <Owner>

# {title}

## Problem Statement

{problem_description}

Date: <YYYY-MM-DD>
```

**Expected Behavior:**

- `{title}`, `<REPO>`, `<SEQ>`, `<YYYY-MM-DD>` all interpolate correctly
- Legacy syntax preserved for backward compatibility

### D.5 Fixture: template_new

**Location:** `tests/fixtures/templates/template_new.md`

**Content:**

```markdown
---
template_type: new-standard
template_version: 2.0
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** {{document_id}}
> **Owner:** {{owner}}
> **Status:** {{status}}

# {{title}}

## Executive Summary

<!-- MEMINIT_SECTION: executive_summary -->

<!-- AGENT: Write a 2-3 sentence summary -->

[Summary here]

## Problem Statement

<!-- MEMINIT_SECTION: problem_statement -->

<!-- AGENT: Describe the problem -->

[Problem here]
```

**Expected Behavior:**

- `{{variable}}` syntax works
- Section markers preserved
- AGENT comments preserved

### D.6 Fixture: repo_empty

**Location:** `tests/fixtures/repo_empty/`

**Structure:**

```
repo_empty/
└── docs/
    └── .gitkeep
```

**No docops.config.yaml**

**Expected Behavior:**

- Uses DEFAULT_TYPE_DIRECTORIES
- Uses built-in templates
- Skeleton for unknown types

### D.7 Fixture: template_with_markers

**Location:** `tests/fixtures/templates/with_markers.md`

**Content:**

```markdown
---
template_type: marker-test
---

## Section A

<!-- MEMINIT_SECTION: section_a -->

Content A

## Section B

<!-- MEMINIT_SECTION: section_b -->

<!-- AGENT: Guidance for section B -->

Content B

## Section C

<!-- MEMINIT_SECTION: section_c -->

Content C
```

**Expected JSON Output:**

```json
{
  "sections": [
    {
      "id": "section_a",
      "heading": "## Section A",
      "line": 8,
      "required": true
    },
    {
      "id": "section_b",
      "heading": "## Section B",
      "line": 12,
      "required": true
    },
    {
      "id": "section_c",
      "heading": "## Section C",
      "line": 18,
      "required": true
    }
  ]
}
```

### D.8 Fixture: template_metadata_variants

**Location:** `tests/fixtures/templates/metadata_variants/`

**variant_marker_placeholder.md:**

```markdown
---
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** <REPO>-TST-<SEQ>
> **Owner:** Placeholder

# Title
```

**variant_marker_only.md:**

```markdown
---
---

<!-- MEMINIT_METADATA_BLOCK -->

# Title
```

**variant_no_marker.md:**

```markdown
---
---

# Title
```

**Expected Behavior:**

- All variants produce exactly one metadata block
- No duplicates

---

**Document Status:** In Review | **Version:** 1.0-rc3 | **Last Updated:** 2026-03-02

<!-- MEMINIT_SECTION: document_end -->

<!-- AGENT: End of document. Ensure all sections have been filled and cross-references are valid. -->
