---
document_id: MEMINIT-GOV-003
owner: Security Team
approvers: GitCmurf
status: Draft
version: 0.2
last_updated: 2025-12-15
title: Public Repository Security Practices
type: GOV
docops_version: 2.0
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-GOV-003
> **Owner:** Security Team
> **Approvers:** GitCmurf
> **Status:** Draft
> **Version:** 0.2
> **Type:** Governance

# Public Repository Security Practices

## Overview

This document serves as the **Pre-Flight Checklist** for making the Meminit repository public. It is designed to prevent the accidental exposure of secrets, private drafts, and "embarrassing" artifacts (like raw AI chat logs or stream-of-consciousness notes).

**Golden Rule:** If you wouldn't put it on a billboard, don't put it in a public repo.

---

## 1. The "Clean History" Principle

Git remembers everything. Deleting a file in a new commit does **not** remove it from history. If you accidentally commit a secret or a private rant, you must rewrite history (e.g., `git filter-repo`) before pushing.

**Action:**

- Run `git log --stat` and scan the filenames. Do you see `temp_notes.txt` or `api_keys.json` in the past?
- If yes, **STOP**. Do not push. Scrub the history first.

---

## 2. Pre-Push Hygiene Checklist

### 2.1 Secrets & Credentials

- [ ] **Scan for Keys:** Run `gitleaks detect --source . --config .gitleaks.toml --verbose` or use pre-commit hook.
- [ ] **Check Configs:** Ensure no real credentials are in `config.yaml` or `setup.py`. Use environment variables instead.
- [ ] **Verify .gitignore:** Confirm `.env`, `.venv`, `secrets/`,
  `.meminit/cache/`, and `.meminit.lock` are ignored.

### 2.2 "Embarrassing" Artifacts

- [ ] **Chat Logs:** Raw AI transcripts (like `chat-transcript-*.txt`) are often messy and redundant.
  - _Recommendation:_ Move them to a private archive or delete them. Only keep **summarized** insights (like `Strategic_Review.md`).
- [ ] **Drafts:** Check for files named `temp`, `draft`, `notes`, `scratch`.
  - _Recommendation:_ Delete them or move them to a `WIP/` folder that is gitignored.
- [ ] **Comments:** Scan code for `TODO: fix security hole` or `Hack: remove before release`.

### 2.3 PII (Personally Identifiable Information)

- [ ] **User Data:** Ensure no real names, emails, or phone numbers are in test fixtures.
- [ ] **Internal URLs:** Check for links to private Jira tickets or internal wikis that shouldn't be exposed.

---

## 3. Ongoing Practices (Post-Public)

- **Atomic Commits:** Keep commits focused. Easier to revert if something goes wrong.
- **No "WIP" Commits to Main:** Use feature branches. Squash "fix typo" commits before merging.
- **Automated Scanning:** Implemented via gitleaks in pre-commit and CI. See `.gitleaks.toml` for configuration.

### 3.1 Secret Scanning Implementation

**Tool:** gitleaks (https://github.com/gitleaks/gitleaks)

**Pre-commit hook:**

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

The gitleaks hook in `.pre-commit-config.yaml` scans for:

- Generic API keys (`api_key`, `apikey`, `api_secret`, etc.)
- AWS access keys
- GitHub Personal Access Tokens
- GitLab Personal Access Tokens
- Slack tokens
- Password assignments in code

**CI enforcement:**
The `ci.yml` workflow runs gitleaks on every push and PR. It uses the official `gitleaks/gitleaks-action@v2`.

**Local installation (optional):**
For local scanning without pre-commit, install gitleaks:

```bash
# macOS
brew install gitleaks

# Linux
curl -s https://api.github.com/repos/gitleaks/gitleaks/releases/latest | \
  grep "browser_download_url.*linux_amd64" | head -1 | cut -d '"' -f 4 | \
  xargs wget -O /usr/local/bin/gitleaks && chmod +x /usr/local/bin/gitleaks

# Run scan
gitleaks detect --source . --config .gitleaks.toml --verbose
```

**False positives:**
The `.gitleaks.toml` config excludes build artifacts, caches, and virtual environments. If you encounter a false positive:

1. Verify it's not a real secret
2. Add an exception to `.gitleaks.toml` under `[allowlist]`
3. Commit the config change with rationale in commit message

**Meminit runtime state:**
`.meminit/cache/` and `.meminit.lock` are local runtime artifacts. Do not
commit them and do not add their hashes to scanner baselines. Rebuild the cache
with `meminit index` or `meminit index --rebuild-cache` when needed. Commit only
intentional deterministic `.meminit` files, such as an org-profile lock file or
project index artifact when the project explicitly owns it.

---

## 4. Incident Response

If you _do_ push a secret:

1. **Rotate the secret immediately.** Consider it compromised.
2. **Rewrite history** to remove the file (if you want to clean up).
3. **Do not just delete the file** in a new commit; the secret is still in the history.
