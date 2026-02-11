---
document_id: ORG-GOV-002
owner: DocOps Working Group
status: Draft
version: 2.0
last_updated: 2025-12-15
title: Metadata Schema v2.0
type: GOV
docops_version: 2.0
---

<!-- MEMINIT_METADATA_BLOCK -->
> **Document ID:** ORG-GOV-002  
> **Owner:** DocOps Working Group  
> **Status:** Draft  
> **Version:** 2.0  
> **Last Updated:** 2025-12-15  
> **Type:** GOV

# Metadata Schema v2.0

This document defines the schema for the YAML frontmatter of all governed documents.

## 1. Core Fields (Required)

| Field | Type | Description | Validation Rule |
| :--- | :--- | :--- | :--- |
| `document_id` | String | Unique Identifier | Regex: `^[A-Z]{3,10}-[A-Z]{3,10}-\d{3}$` |
| `type` | String | Document Type | Must match Constitution types (e.g. `GOV`, `PRD`, `GUIDE`). |
| `title` | String | Human-readable title | Non-empty string. |
| `status` | String | Lifecycle state | Enum: `Draft`, `In Review`, `Approved`, `Superseded`. |
| `version` | String | Semantic Version | Regex: `^\d+\.\d+$` |
| `last_updated` | Date | Last modification date | ISO 8601 (`YYYY-MM-DD`). Tooling accepts unquoted YAML dates and normalizes for schema checks. |
| `owner` | String | Responsible party | Non-empty string. |
| `docops_version` | String | Constitution Version | e.g. `2.0` |

## 2. Context Fields (Recommended)

| Field | Type | Description | Validation Rule |
| :--- | :--- | :--- | :--- |
| `area` | String | Functional Domain | Must match `docops.config.yaml` areas. |
| `description` | String | Summary | Free text. |
| `template_type` | String | Template Identifier | e.g. `adr-minimal` |
| `template_version` | String | Template Version | e.g. `1.0` |
| `keywords` | List[Str] | Knowledge Graph Topics | Must match `docops.config.yaml` keywords (if strict). |
| `tags` | List[Str] | Loose grouping | Free text. |
| `superseded_by`| String | ID of replacement doc | Must be a valid Document ID. |
| `related_ids` | List[Str] | Explicit links | Must be valid Document IDs. |

## 3. Mapping to Standards

To ensure interoperability, we map our fields to standard vocabularies:

| Field Name | Schema.org (`CreativeWork`) | Dublin Core |
| :--- | :--- | :--- |
| `title` | `name` | `title` |
| `description` | `description` | `description` |
| `owner` | `creator` / `maintainer` | `creator` |
| `last_updated` | `dateModified` | `date` |
| `document_id` | `identifier` | `identifier` |
| `keywords` | `keywords` | `subject` |
| `version` | `version` | `hasVersion` |

## 4. JSON Schema Representation

The authoritative JSON Schema lives at `docs/00-governance/metadata.schema.json`. Current version:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://meminit.io/schemas/metadata.schema.json",
  "title": "Meminit Governed Document Frontmatter",
  "type": "object",
  "required": [
    "document_id",
    "type",
    "title",
    "status",
    "version",
    "last_updated",
    "owner",
    "docops_version"
  ],
  "properties": {
    "document_id": {
      "type": "string",
      "pattern": "^[A-Z]{3,10}-[A-Z]{3,10}-\\d{3}$"
    },
    "type": { "type": "string" },
    "title": { "type": "string" },
    "status": {
      "type": "string",
      "enum": ["Draft", "In Review", "Approved", "Superseded"]
    },
    "version": { "type": "string", "pattern": "^\\d+\\.\\d+$" },
    "last_updated": { "type": "string", "format": "date" },
    "owner": { "type": "string" },
    "docops_version": { "type": "string" },
    "area": { "type": "string" },
    "description": { "type": "string" },
    "template_type": { "type": "string" },
    "template_version": { "type": "string" },
    "keywords": { "type": "array", "items": { "type": "string" } },
    "tags": { "type": "array", "items": { "type": "string" } },
    "superseded_by": {
      "type": "string",
      "pattern": "^[A-Z]{3,10}-[A-Z]{3,10}-\\d{3}$"
    },
    "related_ids": {
      "type": "array",
      "items": {
        "type": "string",
        "pattern": "^[A-Z]{3,10}-[A-Z]{3,10}-\\d{3}$"
      }
    }
  },
  "additionalProperties": false
}
```
