# Contributing to Meminit

Thanks for helping shape Meminit. This guide keeps contributions consistent,
safe, and aligned with our DocOps-first approach.

## Ground Rules

- Follow the [Code of Conduct](CODE_OF_CONDUCT.md).
- No secrets or private drafts in git; run the pre-push hygiene checklist in
  `MEMINIT-GOV-003` at `docs/00-governance/gov-003-security-practices.md`.
- Documentation is a first-class citizen: every change that affects behavior
  or decisions must update the relevant doc (metadata block included).

## Where to Start

1. Read the project overview in `README.md` and the vision doc at
   `docs/02-strategy/strat-001-project-meminit-vision.md`.
2. Check open issues or file a new one (bug or enhancement) before starting
   significant work.
3. Create a branch from `master` using a clear name like
   `feature/<short-description>` or `fix/<short-description>`.

## Reporting Bugs

- Use the bug template when available.
- Provide repro steps, expected vs. actual behavior, environment details, and
  any logs (redacted of secrets/PII).

## Suggesting Enhancements

- Describe the problem first, then the proposed solution and alternatives you
  considered.
- Include why it matters to Meminit’s goals (governance, automation, agentic
  collaboration).

## Development Workflow

1. Fork/clone and set up per `README.md` (Python venv, Node tooling if needed).
2. Make focused commits; keep PRs small and purposeful.
3. Update docs alongside code. Governed docs must include YAML frontmatter that
   matches `docs/00-governance/metadata.schema.json` and display the metadata
   block per the Constitution.
4. Add or update tests under `tests/` for new behavior or bug fixes.
5. Run lint/format tools that apply to your changes (e.g., `ruff`, `eslint`,
   `prettier`, `black`).
6. Run the pre-push hygiene checklist (secrets scan, `.gitignore` audit,
   history check) before opening a PR.

## Pull Request Checklist

- [ ] Tests added/updated and passing.
- [ ] Documentation updated (including metadata and links).
- [ ] Lint/format applied.
- [ ] No secrets, private drafts, or AI transcripts in the diff/history.
- [ ] PR description states scope, testing done, and any follow-up tasks.

## Style Guides

- **Python**: PEP 8; prefer type hints; keep functions small and clear.
- **TypeScript/JS**: Use the repo ESLint/Prettier settings once present; favor
  explicit types and narrow exports.
- **Docs**: Follow `docs/00-governance/org-gov-001-constitution.md` and
  `docs/00-governance/gov-001-document-standards.md` for structure and
  metadata. Write in the active voice and keep sections scannable.

## Communication

- Be respectful and constructive; assume good intent.
- If something is unclear, open an issue or draft PR early for feedback.
