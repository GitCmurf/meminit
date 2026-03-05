---
document_id: MEMINIT-SPEC-007
type: SPEC
title: Templates v2 Specification
status: Draft
version: 0.1
last_updated: 2026-03-04
owner: Product Team
docops_version: 2.0
area: CORE
description: "Normative specification for Meminit Templates v2 system including resolution chain, interpolation syntax, section markers, and validation rules."
keywords:
  - template
  - interpolation
  - section
  - marker
  - agent
related_ids:
  - MEMINIT-PRD-006
  - MEMINIT-SPEC-004
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-SPEC-007
> **Owner:** Product Team
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2026-03-04
> **Type:** SPEC
> **Area:** CORE

# SPEC: Templates v2

## 1. Purpose

This document defines the normative specification for Meminit Templates v2, including the template resolution precedence chain, interpolation syntax, section marker format, agent prompt extraction, and security validation rules.

Plain English: This is the single source of truth for how templates work in Meminit v2.

## 2. Scope

In scope:

- Template resolution precedence chain (config → convention → builtin → skeleton)
- `{{variable}}` interpolation syntax (legacy syntax rejection)
- `<!-- MEMINIT_SECTION: id -->` marker format
- `<!-- AGENT: ... -->` prompt format
- Template file validation (security, encoding, size)
- Code-fence-aware marker detection

Out of scope:

- Template content authoring guidelines (covered by governance docs)
- Legacy v1 template behavior

## 3. Template Resolution Precedence Chain

Templates are resolved in a deterministic 4-step chain. The first match wins.

### 3.1 Resolution Order

| Priority | Source     | Description                                                  |
| -------- | ---------- | ------------------------------------------------------------ |
| 1        | Config     | Explicit `template` path in `document_types.<type>.template` |
| 2        | Convention | `<docs_root>/00-governance/templates/<type>.template.md`     |
| 3        | Built-in   | Package assets (ADR, PRD, FDD)                               |
| 4        | None       | Minimal skeleton template                                    |

### 3.2 Source Values

The `data.template.source` field in JSON output uses these exact string values:

- `"config"` — Template from `document_types.<type>.template` config
- `"convention"` — Template from `<docs_root>/00-governance/templates/`
- `"builtin"` — Template from package assets
- `"none"` — No template found (skeleton used)

### 3.3 Config Resolution

Config templates are specified in `docops.config.yaml`:

```yaml
document_types:
  PRD:
    directory: "10-prd"
    template: "docs/templates/custom-prd.template.md"
```

Path is relative to repository root. Must resolve within repo bounds.

### 3.4 Convention Resolution

Convention templates use this pattern:

```text
<docs_root>/00-governance/templates/<type>.template.md
```

Where `<type>` is the lowercased, normalized document type (e.g., `adr`, `prd`, `fdd`).

### 3.5 Built-in Resolution

Built-in templates are packaged with Meminit:

- `adr.template.md` — Architecture Decision Record
- `prd.template.md` — Product Requirements Document
- `fdd.template.md` Functional Design Document

### 3.6 Skeleton Template

When no template is found, a minimal skeleton is used:

```markdown
---
document_id: {{document_id}}
type: {{type}}
title: {{title}}
status: {{status}}
last_updated: {{date}}
owner: {{owner}}
docops_version: 2.0
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** {{document_id}}
> **Owner:** {{owner}}
> **Status:** {{status}}
> **Type:** {{type}}

# {{title}}

<!-- MEMINIT_SECTION: content -->

## Content
```

## 4. Interpolation Syntax

Templates use **only** double-brace `{{variable}}` syntax. Legacy syntax is rejected.

### 4.1 Supported Variables

| Variable          | Type   | Description              | Example                                          |
| ----------------- | ------ | ------------------------ | ------------------------------------------------ |
| `{{title}}`       | string | Document title           | `{{title}}` → "My Feature"                       |
| `{{document_id}}` | string | Full document ID         | `{{document_id}}` → "REPO-PRD-001"               |
| `{{owner}}`       | string | Document owner           | `{{owner}}` → "Team A"                           |
| `{{status}}`      | string | Document status          | `{{status}}` → "Draft"                           |
| `{{date}}`        | string | Current date (ISO 8601)  | `{{date}}` → "2026-03-04"                        |
| `{{repo_prefix}}` | string | Repository prefix        | `{{repo_prefix}}` → "REPO"                       |
| `{{seq}}`         | string | Sequence number          | `{{seq}}` → "001"                                |
| `{{type}}`        | string | Document type            | `{{type}}` → "PRD"                               |
| `{{area}}`        | string | Document area            | `{{area}}` → "Engineering"                       |
| `{{description}}` | string | Document description     | `{{description}}` → "A feature"                  |
| `{{keywords}}`    | string | Comma-separated keywords | `{{keywords}}` → "api, cli"                      |
| `{{related_ids}}` | string | Comma-separated IDs      | `{{related_ids}}` → "REPO-ADR-001, REPO-ADR-002" |

### 4.2 Variable Normalization

- Empty values become empty strings (not `"None"` or missing)
- Whitespace is stripped from values
- Lists (`keywords`, `related_ids`) are joined with `", "`

### 4.3 Legacy Syntax Rejection

Legacy placeholder syntax raises `INVALID_TEMPLATE_PLACEHOLDER` error:

| Legacy Syntax      | Correct Syntax    |
| ------------------ | ----------------- |
| `{title}`          | `{{title}}`       |
| `{status}`         | `{{status}}`      |
| `{owner}`          | `{{owner}}`       |
| `{area}`           | `{{area}}`        |
| `{description}`    | `{{description}}` |
| `{keywords}`       | `{{keywords}}`    |
| `{related_ids}`    | `{{related_ids}}` |
| `<REPO>`           | `{{repo_prefix}}` |
| `<PROJECT>`        | `{{repo_prefix}}` |
| `<SEQ>`            | `{{seq}}`         |
| `<YYYY-MM-DD>`     | `{{date}}`        |
| `<Decision Title>` | `{{title}}`       |
| `<Feature Title>`  | `{{title}}`       |
| `<Team or Person>` | `{{owner}}`       |
| `<AREA>`           | `{{area}}`        |

### 4.4 Unknown Variables

Unknown `{{variable}}` placeholders raise `UNKNOWN_TEMPLATE_VARIABLE` error.

Example:

```markdown
{{unknown_var}}
```

Error response:

```json
{
  "code": "UNKNOWN_TEMPLATE_VARIABLE",
  "message": "Unknown template variables: unknown_var",
  "details": {
    "unknown_variables": ["unknown_var"],
    "known_variables": ["title", "document_id", ...]
  }
}
```

## 5. Section Markers

Section markers provide stable, agent-orchestratable document structure.

### 5.1 Marker Format

```markdown
<!-- MEMINIT_SECTION: <id> -->
```

Where `<id>` is a section identifier matching `[a-zA-Z0-9_-]+`.

### 5.2 Marker Placement

Markers are placed **before** the section heading:

```markdown
<!-- MEMINIT_SECTION: context -->

## Context
```

### 5.3 Section Object Fields

Each parsed section includes:

| Field                | Type           | Description                                  |
| -------------------- | -------------- | -------------------------------------------- |
| `id`                 | string         | Section identifier                           |
| `heading`            | string         | Section heading text (including `#` markers) |
| `line`               | integer        | Line number of heading                       |
| `marker_line`        | integer        | Line number of marker                        |
| `content_start_line` | integer        | Line number of first content line            |
| `content_end_line`   | integer        | Line number of last content line             |
| `required`           | boolean        | Whether section is required                  |
| `agent_prompt`       | string \| null | Agent guidance prompt                        |

### 5.4 Section Boundaries

Section content spans from the line **after** the marker to the line **before** the next marker (or end of file).

### 5.5 Code Fence Protection

Markers inside code fences are **ignored**:

````markdown
<!-- MEMINIT_SECTION: real -->

## Real Section

```markdown
<!-- MEMINIT_SECTION: fake -->

## Fake Section (inside code fence, ignored)
```

<!-- MEMINIT_SECTION: another -->

## Another Section
````

In this example:

- `real` section is parsed
- `fake` section is ignored (inside code fence)
- `another` section is parsed

### 5.6 Duplicate Detection

Duplicate section IDs raise `DUPLICATE_SECTION_ID` error:

```markdown
<!-- MEMINIT_SECTION: title -->

## Title 1

<!-- MEMINIT_SECTION: title -->

## Title 2
```

Error response:

```json
{
  "code": "DUPLICATE_SECTION_ID",
  "message": "Duplicate section ID: title",
  "details": {
    "section_id": "title",
    "line": 7
  }
}
```

## 6. Agent Prompts

Agent prompts provide guidance for AI agents filling out template sections.

### 6.1 Prompt Format

```markdown
<!-- AGENT: <guidance text> -->
```

### 6.2 Prompt Placement

Prompts are placed **after** the section marker and **before** the heading:

```markdown
<!-- MEMINIT_SECTION: context -->
<!-- AGENT: Describe the problem or opportunity that motivated this decision. -->

## Context
```

### 6.3 Multiple Prompts

Multiple `<!-- AGENT: ... -->` markers are combined with newlines:

```markdown
<!-- MEMINIT_SECTION: context -->
<!-- AGENT: Describe the problem or opportunity. -->
<!-- AGENT: Include relevant context and constraints. -->
<!-- AGENT: Reference related decisions. -->

## Context
```

Combined prompt:

```text
Describe the problem or opportunity.
Include relevant context and constraints.
Reference related decisions.
```

### 6.4 Prompt Exclusion

Agent prompts are **not** included in `initial_content` (for agent filling), but are preserved in the final document.

## 7. Template File Validation

Templates are validated for security and correctness.

### 7.1 File Extension

Template files **must** have `.md` extension.

Example: `prd.template.md` ✓ | `prd.template.txt` ✗

### 7.2 File Size

Template files **must not** exceed 256 KiB (262,144 bytes).

Larger templates raise `INVALID_TEMPLATE_FILE` error.

### 7.3 File Encoding

Template files **must** be valid UTF-8.

### 7.4 Symlink Rejection

Template files **must not** be symbolic links.

Symlinked templates raise `INVALID_TEMPLATE_FILE` error.

### 7.5 Path Containment

Convention templates **must** resolve within `<docs_root>/00-governance/templates/`.

Config templates **must** resolve within the repository root.

Path traversal attempts (e.g., `../../../etc/passwd`) are rejected.

### 7.6 Template Path Naming

Template files **should** use the `*.template.md` naming convention:

- `adr.template.md`
- `prd.template.md`
- `fdd.template.md`

Legacy `template-001-*.md` naming is deprecated.

## 8. JSON Output (Templates v2)

When `--format json` is used with `meminit new`, the response includes Templates v2 fields.

### 8.1 Top-Level Fields

| Field                   | Type           | Description                      |
| ----------------------- | -------------- | -------------------------------- |
| `data.rendered_content` | string \| null | Full rendered document content   |
| `data.content_sha256`   | string \| null | SHA-256 hash of rendered content |
| `data.template`         | object \| null | Template provenance object       |

### 8.2 Template Object

| Field             | Type           | Description                                                      |
| ----------------- | -------------- | ---------------------------------------------------------------- |
| `applied`         | boolean        | Whether a template was applied                                   |
| `source`          | string         | Template source: "config" \| "convention" \| "builtin" \| "none" |
| `path`            | string \| null | Path to template file (relative to repo root)                    |
| `content_preview` | string         | First 200 characters of template content                         |
| `sections`        | array          | Parsed section markers (see §5.3)                                |

### 8.3 Example Output

```json
{
  "output_schema_version": "2.0",
  "success": true,
  "command": "new",
  "run_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "root": "/repo",
  "data": {
    "document_id": "REPO-PRD-001",
    "path": "docs/10-prd/prd-001-my-feature.md",
    "type": "PRD",
    "title": "My Feature",
    "rendered_content": "# My Feature\n\n...",
    "content_sha256": "a1b2c3d4e5f6...",
    "template": {
      "applied": true,
      "source": "convention",
      "path": "docs/00-governance/templates/prd.template.md",
      "content_preview": "# PRD: {{title}}\n\n<!-- MEMINIT_SECTION: context -->",
      "sections": [
        {
          "id": "context",
          "heading": "## Context",
          "line": 15,
          "marker_line": 13,
          "content_start_line": 16,
          "content_end_line": 42,
          "required": true,
          "agent_prompt": "Describe the problem or opportunity..."
        }
      ]
    }
  },
  "warnings": [],
  "violations": [],
  "advice": []
}
```

## 9. Error Codes (Templates v2)

| Code                           | Description                                |
| ------------------------------ | ------------------------------------------ |
| `INVALID_TEMPLATE_PLACEHOLDER` | Legacy placeholder syntax detected         |
| `UNKNOWN_TEMPLATE_VARIABLE`    | Unknown `{{variable}}` placeholder         |
| `INVALID_TEMPLATE_FILE`        | Template validation failure                |
| `DUPLICATE_SECTION_ID`         | Duplicate section ID in template           |
| `AMBIGUOUS_SECTION_BOUNDARY`   | Ambiguous section boundary                 |
| `LEGACY_CONFIG_UNSUPPORTED`    | Legacy `type_directories`/`templates` keys |

See MEMINIT-SPEC-006 for complete error code inventory.

## 10. Compliance Checklist

1. Templates use only `{{variable}}` interpolation syntax
2. Section markers follow `<!-- MEMINIT_SECTION: id -->` format
3. Agent prompts follow `<!-- AGENT: ... -->` format
4. Template files are validated (size, encoding, symlink, path)
5. Code fence protection is applied to marker detection
6. Duplicate section IDs are detected and rejected
7. JSON output includes template provenance information

Plain English: If these are true, Templates v2 is implemented correctly.
