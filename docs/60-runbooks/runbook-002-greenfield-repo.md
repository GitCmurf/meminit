---
document_id: MEMINIT-RUNBOOK-002
type: RUNBOOK
docops_version: "2.0"
last_updated: "2025-12-31"
status: Draft
title: Greenfield Repository Setup
owner: GitCmurf
version: "0.2"
---

# Runbook: Greenfield Repository Setup

## Goal

Initialize a new, empty repository with the standard DocOps structure and tooling.

## Prerequisites

- `meminit` CLI installed (or available via pip).
- Empty or clean git repository.

## Steps

### 1. Initialize Structure

Run the following command at the repo root:

```bash
meminit init
```

This creates:

- `docs/` directory tree.
- `AGENTS.md` (Rules for AI).
- `docops.config.yaml` (Local configuration).

### 2. Configure Agents

Open `AGENTS.md` and review the "Agentic Coding Rules". Commit this file immediately—it is the instruction manual for your AI colleagues.

### 3. Create First Document

Create your first Architecture Decision Record (ADR) to record the repo's purpose:

```bash
meminit new ADR "Repository Purpose and Stack"
```

This generates `docs/45-adr/adr-001-repository-purpose-and-stack.md`. Edit it to fill in the context.

### 4. Commit

```bash
git add .
git commit -m "chore: Initialize DocOps structure"
```
