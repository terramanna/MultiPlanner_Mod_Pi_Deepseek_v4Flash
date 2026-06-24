# Git Workflow

Canonical workflow for agents and human-assisted changes in this repository.

## Hard rules

- Start from up-to-date `main`.
- Never start new work on dirty `main`.
- Create a named branch before edits when branch workflow is in use.
- Keep each branch focused and small.
- Do not mix unrelated dirty files into a commit.
- Do not rewrite pushed history unless explicitly requested.
- Do not use destructive Git commands without explicit approval.
- Keep every commit attributable under `docs/COMMIT_AUDIT.md`.
- Respect the file-size guardrail enforced by `scripts/check_file_size_policy.py`.

## Branch loop

1. State the branch goal and intended files.
2. Check current status before staging or merging.
3. Make one cohesive change.
4. Run focused tests, lint, type checks, and `git diff --check` as applicable.
5. Run repo guardrails for touched areas when applicable.
6. Update docs, glossary, or ADRs when terms or architecture change.
7. Commit only related files.
8. Push the branch.
9. Merge back without squash unless explicitly directed otherwise.

## Dirty worktree guard

- Show `git status --short` before staging.
- Stage explicit paths only.
- Leave logs, caches, build output, local databases, and secrets unstaged.
- Keep unrelated user changes untouched.

A clean working tree is not permission to rewrite work outside the task.
