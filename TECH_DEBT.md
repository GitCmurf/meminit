# Technical Debt Register

This file tracks known technical debt items that were identified during code
review but deliberately deferred from the current implementation phase.
Each entry includes a remediation sketch so a future contributor can pick
it up without re-discovering the context.

Items are ordered by priority (highest first). When picking up an item,
create a dedicated branch, update this file to mark it in-progress, and
link the resulting PR.

---

## TD-001 — `_ns_cache` produces wrong results for multi-namespace repos with overlapping `docs_dir`

**Priority:** Medium
**Origin:** Gemini + Macroscope code review (PR-V)
**Status:** Open

**Description:**
The per-parent-directory namespace cache in `index_repository.py:912-929`
caches `_SENTINEL_NONE` when a file belongs to a different namespace than
the one currently being iterated. If the same directory contains files
from multiple namespaces (overlapping `docs_dir`), files belonging to the
other namespace are permanently skipped. The single-namespace fast path
(`single_ns` at line 917) bypasses this cache entirely, so single-namespace
repos are unaffected.

**Impact:**
Multi-namespace repos with overlapping `docs_dir` configurations will
silently miss files in the index. Current deployments use single-namespace
or non-overlapping configurations, so no production impact today.

**Remediation sketch:**
Replace the flat `_ns_cache[parent_key] = owner|_SENTINEL_NONE` with a
per-parent map keyed by `(parent_key, namespace)` or remove the cache
entirely for multi-namespace repos and rely on `namespace_for_path()`
per-file (slower but correct).

**References:**
- `src/meminit/core/use_cases/index_repository.py:912-929`
- `src/meminit/core/services/repo_config.py` (`namespace_for_path`)

---

## TD-002 — Unused `known_ids` parameter in `_is_dep_resolved`

**Priority:** Low
**Origin:** Greptile code review (PR-V)
**Status:** Open

**Description:**
`_is_dep_resolved(dep_id, state, known_ids)` accepts `known_ids` but
never reads it. A dependency that exists in the index (`known_ids`) but
not in `project-state.yaml` is unconditionally treated as unresolved.
This is the intended semantics (a dependency must have an explicit state
entry with `impl_state: Done` to count as resolved), but the unused
parameter misleads future maintainers into thinking `known_ids` participates
in the resolution logic.

**Impact:**
No functional impact. Maintenance confusion risk.

**Remediation sketch:**
Remove `known_ids` from `_is_dep_resolved`, `_is_ready`, and
`_open_blockers_for` signatures. Update `compute_derived_fields` to not
pass it through. Update all callers and tests.

**References:**
- `src/meminit/core/services/state_derived.py:48-53`
- `src/meminit/core/services/state_derived.py:60-73`
- `src/meminit/core/services/state_derived.py:76-90`

---

## TD-003 — O(N^2) complexity in `compute_derived_fields`

**Priority:** Low
**Origin:** Gemini code review (PR-V); pre-existing
**Status:** Open

**Description:**
`_unblocks_for` performs a full scan of `state.entries` for every entry,
producing O(N^2) total work in `compute_derived_fields`. For repos with
hundreds of state entries this becomes measurable.

**Impact:**
Performance degrades quadratically with state entry count. Acceptable at
current scale (<100 entries). The 500-doc benchmark budget (30s) already
accounts for this.

**Remediation sketch:**
Build an inverse adjacency map once at the start of
`compute_derived_fields`: for each entry, record which other entries
reference it in `depends_on`/`blocked_by`. Then `_unblocks_for` becomes
a constant-time lookup. Total complexity drops to O(N).

**References:**
- `src/meminit/core/services/state_derived.py:100-113` (`_unblocks_for`)
- `src/meminit/core/services/state_derived.py:122-137` (`compute_derived_fields`)

---

## TD-004 — Inconsistent `E_` prefix on `STATE_*` error codes

**Priority:** Low
**Origin:** CodeRabbit nitpick (PR-V)
**Status:** Open

**Description:**
The `ErrorCode` enum mixes `E_STATE_YAML_MALFORMED` / `E_STATE_SCHEMA_VIOLATION`
(with `E_` prefix) alongside `STATE_INVALID_PRIORITY`,
`STATE_FIELD_TOO_LONG`, etc. (without prefix). The convention is
inconsistent. Renaming would be a cross-cutting change affecting
SPEC-006, PLAN-013, FDD-013, all tests, CLI error messages, and
`ERROR_EXPLANATIONS`.

**Impact:**
No functional impact. Cosmetic inconsistency in the public error code
contract.

**Remediation sketch:**
Choose one convention (preferably keeping the `STATE_` prefix without `E_`
since the majority of codes already use it). Rename the two `E_STATE_*`
codes, update all references in docs and code, add migration notes to
SPEC-006 changelog.

**References:**
- `src/meminit/core/services/error_codes.py:59-70`
- `docs/20-specs/spec-006-errorcode-enum.md`

---

## TD-005 — `get_state_file_rel_path` silently returns default on missing config

**Priority:** Low
**Origin:** Greptile code review (PR-V)
**Status:** Open

**Description:**
`get_state_file_rel_path` catches all exceptions from `load_repo_config`
and returns the hardcoded fallback `"docs/01-indices/project-state.yaml"`.
This means code paths that call this function without first checking
config validity will silently operate against a default path. All `state *`
CLI commands already call `validate_initialized()` before reaching this
function, so the fail-fast happens earlier. However, `meminit doctor` and
`meminit index` may reach this function with missing config and silently
use the default.

**Impact:**
`meminit doctor` on an uninitialized repo will try to read from the
default path instead of reporting a config error. Low severity since
doctor's purpose is diagnostics.

**Remediation sketch:**
Split into two functions: `get_state_file_rel_path` (current, with
fallback) and `get_state_file_rel_path_strict` (raises `CONFIG_MISSING`
on failure). Use the strict variant in `index_repository.py` and keep
the fallback for `doctor`.

**References:**
- `src/meminit/core/services/project_state.py:41-50`
- `src/meminit/core/use_cases/doctor_repository.py`
