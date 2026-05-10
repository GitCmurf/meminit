---
document_id: MEMINIT-LOG-001
type: LOG
title: Phase 5 External Testbed Evidence
status: Draft
version: "0.2"
last_updated: 2026-05-10
owner: GitCmurf
docops_version: "2.0"
area: AGENT
description: "Operator-attested evidence template for Phase 5 NDJSON streaming and incremental cache validation in an external testbed repository."
keywords:
  - phase-5
  - streaming
  - cache
  - external-testbed
related_ids:
  - MEMINIT-PLAN-014
  - MEMINIT-PLAN-015
  - MEMINIT-RUNBOOK-006
---

# LOG: Phase 5 External Testbed Evidence

## Status

This document is an evidence template. It is not closure evidence until a
human operator completes the attestation fields and records sanitized results.

## Operator Attestation

| Field | Value |
| ----- | ----- |
| Operator | Pending |
| Attestation date | Pending |
| Meminit version or commit | Pending |
| External repository class | Pending |
| Release owner reviewer | Pending |
| Evidence status | Pending operator run |

Operator statement:

> Pending. The operator must confirm that the commands below were run against
> an external non-PII testbed repository and that the recorded summary is
> sanitized for public commit.

## Required Commands

Run these commands from the external testbed repository root:

```bash
meminit scan --format ndjson
meminit context --deep --format ndjson
meminit index --format ndjson
meminit index --format json        # cold or initial cache population
meminit index --format json        # warm-cache reuse check
meminit index --rebuild-cache --format json
meminit index --explain-cache --format json
```

## Sanitized Result Summary

| Step | Command | Exit status | Sanitized evidence |
| ---- | ------- | ----------- | ------------------ |
| 1 | `meminit scan --format ndjson` | Pending | Pending |
| 2 | `meminit context --deep --format ndjson` | Pending | Pending |
| 3 | `meminit index --format ndjson` | Pending | Pending |
| 4 | `meminit index --format json` | Pending | Pending |
| 5 | `meminit index --format json` | Pending | Pending |
| 6 | `meminit index --rebuild-cache --format json` | Pending | Pending |
| 7 | `meminit index --explain-cache --format json` | Pending | Pending |

## Evidence Capture Checklist

For every NDJSON command, record:

- `stream_schema_version` from the header or first record.
- terminal record type: `summary` or `error`.
- whether every stdout line parsed as one complete JSON object.
- item counts by `kind`.
- warning, violation, and advice counts.

For JSON index commands, record:

- `output_schema_version`.
- `success`.
- node and edge counts.
- warning, violation, and advice counts.
- whether the second JSON run reported warm-cache reuse or an unchanged
  incremental plan.

For cache explanation, record:

- cache mode or manifest status.
- whether a manifest was present.
- warning count and any sanitized `CACHE_*` code.

## Evidence Requirements

- Do not record repository names, absolute paths, secrets, customer data,
  proprietary file names, or proprietary document content.
- Record counts, schema versions, warning counts, cache mode, and whether every
  stdout line parsed as JSON.
- Record any non-zero exit status with sanitized error code and category only.
- Leave this document in Draft until a release owner confirms the evidence is
  suitable for public history.

## Follow-Up Debt

| Item | Status | Notes |
| ---- | ------ | ----- |
| External command execution | Pending | Operator action required. |
| Secret and PII review | Pending | Required before TD-004 can close. |
| Release-owner sign-off | Pending | Required before TD-004 can close. |

## Version History

| Version | Date | Author | Changes |
| ------- | ---- | ------ | ------- |
| 0.1 | 2026-05-09 | Codex | Initial operator-attested Phase 5 external testbed evidence template. |
| 0.2 | 2026-05-10 | Codex | Aligned the required command list and capture checklist with MEMINIT-RUNBOOK-006, including warm-cache and rebuild-cache evidence. |
