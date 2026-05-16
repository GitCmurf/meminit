---
document_id: MEMINIT-LOG-001
type: LOG
title: Phase 5 External Testbed Evidence
status: Draft
version: "0.3"
last_updated: 2026-05-17
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
| Operator | Human operator |
| Attestation date | 2026-05-17 |
| Meminit version or commit | 0.2.0 |
| Meminit binary path | /home/cmf/code/Meminit/.venv/bin/meminit |
| External repository class | External non-PII application repo |
| Release owner reviewer | Pending |
| Evidence status | Sanitized evidence captured; release-owner sign-off pending |

Operator statement:

> The operator confirms that the commands below were run against an external
> non-PII testbed repository using the workspace binary at
> `/home/cmf/code/Meminit/.venv/bin/meminit`, and that the recorded summary
> below is sanitized for public commit.

## Required Commands

Run these commands from the external testbed repository root:

```bash
cd /path/to/external-testbed-repo
MEMINIT_BIN=/home/cmf/code/Meminit/.venv/bin/meminit

printf 'using meminit binary: %s\n' "$(readlink -f "$MEMINIT_BIN")"
"$MEMINIT_BIN" --version
"$MEMINIT_BIN" scan --format ndjson
"$MEMINIT_BIN" context --deep --format ndjson
"$MEMINIT_BIN" index --format ndjson
"$MEMINIT_BIN" index --format json        # cold or initial cache population
"$MEMINIT_BIN" index --format json        # warm-cache reuse check
"$MEMINIT_BIN" index --rebuild-cache --format json
"$MEMINIT_BIN" index --explain-cache --format json
```

## Sanitized Result Summary

| Step | Command | Exit status | Sanitized evidence |
| ---- | ------- | ----------- | ------------------ |
| 1 | `meminit scan --format ndjson` | 0 | NDJSON schema `1.0`; 65 `file` items; 0 warnings; 0 violations; 0 advice. |
| 2 | `meminit context --deep --format ndjson` | 0 | NDJSON schema `1.0`; 62 documents; 18 document types; 4 namespaces; 0 warnings; 0 violations. |
| 3 | `meminit index --format ndjson` | 0 | NDJSON schema `1.0`; 62 nodes; 15 edges; 0 warnings; 0 violations; 2 advisory asymmetry notes. |
| 4 | `meminit index --format json` | 0 | JSON schema `3.0`; success `true`; 62 nodes; 15 edges; incremental cache populated. |
| 5 | `meminit index --format json` | 0 | JSON schema `3.0`; success `true`; 62 nodes; 15 edges; warm-cache reuse confirmed on the second run. |
| 6 | `meminit index --rebuild-cache --format json` | 0 | JSON schema `3.0`; success `true`; full rebuild; 62 nodes; 15 edges; 2 advisory asymmetry notes. |
| 7 | `meminit index --explain-cache --format json` | 0 | JSON schema `3.0`; cache manifest present at `.meminit/cache/index/manifest.json`; `exists: true`; 0 warnings; 0 violations. |

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

For provenance, record:

- the absolute `meminit` binary path used for the run.
- the `Meminit version or commit` field from the workspace checkout.
- whether `meminit --version` from the workspace binary and `meminit --version`
  from `PATH` differed. In this run, the package version matched; the proof of
  provenance is the resolved binary path above.

For cache explanation, record:

- cache mode or manifest status.
- whether a manifest was present.
- warning count and any sanitized `CACHE_*` code.

## Evidence Requirements

- Do not record external repository names or absolute paths, secrets, customer
  data, proprietary file names, or proprietary document content.
- Record counts, schema versions, warning counts, cache mode, and whether every
  stdout line parsed as JSON.
- Record any non-zero exit status with sanitized error code and category only.
- Leave this document in Draft until a release owner confirms the evidence is
  suitable for public history.

## Follow-Up Debt

| Item | Status | Notes |
| ---- | ------ | ----- |
| External command execution | Completed | Sanitized operator run captured in the evidence table above. |
| Secret and PII review | Completed | No secrets, PII, or proprietary repo content were recorded in the committed evidence. |
| Release-owner sign-off | Pending | Required before TD-004 can close. |

## Version History

| Version | Date | Author | Changes |
| ------- | ---- | ------ | ------- |
| 0.1 | 2026-05-09 | Codex | Initial operator-attested Phase 5 external testbed evidence template. |
| 0.2 | 2026-05-10 | Codex | Aligned the required command list and capture checklist with MEMINIT-RUNBOOK-006, including warm-cache and rebuild-cache evidence. |
| 0.3 | 2026-05-17 | Codex | Recorded the sanitized external testbed run results, provenance fields, and follow-up status pending release-owner sign-off. |
