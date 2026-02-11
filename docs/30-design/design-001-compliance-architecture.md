---
document_id: MEMINIT-DESIGN-001
owner: Architecture Team
approvers: GitCmurf
status: Draft
version: 0.1
last_updated: 2025-11-20
title: Compliance Checker Architecture
type: DESIGN
docops_version: 2.0
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-DESIGN-001
> **Owner:** Architecture Team
> **Approvers:** GitCmurf
> **Status:** Draft
> **Version:** 0.1
> **Type:** DESIGN

# Compliance Checker Architecture

## 1. Architectural Style

We adopt **Clean Architecture** organized by **DCI (Data, Context, Interaction)** principles to ensure separation of concerns, testability, and clarity of intent.

## 2. Layers

### 2.1 Entities (Data)

_Located in: `src/meminit/core/domain/`_
Anemic data structures representing the core concepts. They have no dependencies.

- `Document`: Represents a parsed markdown file (path, frontmatter, body).
- `Frontmatter`: Typed representation of YAML metadata.
- `Violation`: Represents a compliance error (file, line, message, severity).
- `RepoConfig`: Represents `docops.config.yaml`.

### 2.2 Use Cases (Contexts)

_Located in: `src/meminit/core/use_cases/`_
Orchestrators that define "what the system does". They wire up Data and Interactions.

- `CheckRepositoryContext`: Scans a directory, parses docs, runs validators, aggregates violations.
- `CheckDocumentContext`: Validates a single document against all rules.

### 2.3 Interactions (Roles/Services)

_Located in: `src/meminit/core/services/`_
Pure logic that operates on Entities.

- `IdValidator`: Regex and uniqueness checks.
- `SchemaValidator`: JSON Schema/Pydantic validation.
- `LinkResolver`: Parses markdown links and verifies targets.

### 2.4 Interface Adapters

_Located in: `src/meminit/adapters/`_

- `CLI`: Click/Typer entry points. Converts CLI args to Context inputs; formats Context outputs (Violations) to Console/JSON.
- `PreCommit`: Wrapper for pre-commit hook execution.
- `FileSystemScanner`: Traverses directories and returns file paths (Adapter).

## 3. Data Flow

1.  **CLI** invokes `CheckRepositoryContext`.
2.  **Context** calls `FileSystemScanner` to get file paths.
3.  **Context** loop:
    - Load `Document` entity.
    - Invoke `SchemaValidator` (Interaction).
    - Invoke `IdValidator` (Interaction).
    - Invoke `LinkResolver` (Interaction).
    - Collect `Violation` entities.
4.  **Context** returns list of `Violation`s.
5.  **CLI** formats and exits.

## 4. DCI Mapping

- **Data:** `Document`, `Frontmatter`, `Violation`
- **Context:** `CheckRepositoryContext`
- **Interaction:** `SchemaValidator.validate()`, `IdValidator.validate()`, `LinkResolver.resolve()` (Pure Services).
