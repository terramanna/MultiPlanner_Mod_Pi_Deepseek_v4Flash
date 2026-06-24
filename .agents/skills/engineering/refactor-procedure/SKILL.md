---
name: refactor-procedure
description: Enforces a branch-first, one-change-at-a-time refactoring workflow with tests, docs, commits, push, merge, and no squash. Use when the user mentions refactor procedure, branch workflow, commit discipline, no squash, keep main up to date, small changes, or module size limits.
---

# Refactor Procedure

Canonical repo workflow lives in `docs/agents/git-workflow.md`. Follow that file
when present; this skill mirrors it for portability.

Use this workflow for refactors and hardening work. Bias to stopping and asking before
violating it.

## Hard rules

- Start from up-to-date `main`: fetch, switch main, merge `origin/main`.
- Never start new work on dirty `main`.
- Create a named branch before edits.
- Finish one branch before starting next branch.
- Max 3 cohesive changes per branch.
- Prefer 1 change per branch when risk is non-trivial.
- No squash commits.
- Do not rewrite pushed history unless user explicitly asks.
- Do not mix unrelated dirty files into a commit.
- Keep modules roughly <= 600 lines. If a module would grow past that, split or stop.

## Change loop

For each branch:

1. State branch goal and intended files.
2. Run baseline check when practical.
3. Make one cohesive change.
4. Run focused tests and lint/type checks for touched area.
5. Update docs/domain glossary/ADR when terms or architecture change.
6. Commit only related files.
7. Repeat steps 3-6 for at most 3 changes.
8. Push branch.
9. Merge back with normal merge or fast-forward only. Never squash.
10. Push `main`.
11. Start next branch from updated `main`.

## Dirty worktree guard

Before staging:

- Show `git status --short`.
- Stage explicit paths only.
- If unrelated dirty files exist, leave them unstaged and mention them.
- If unrelated changes block switching/merging, ask user whether to commit, stash, or stop.

## Commit rules

- Commit message names intent, not mechanics.
- Each commit must compile or have a clear note if impossible.
- Each commit should include tests/docs needed to understand that change.
- Generated logs, build outputs, local DB files, and dist folders stay out unless user asks.

## Merge rules

- Acceptable: `git merge branch-name` or fast-forward merge.
- Acceptable: PR merge commit preserving commits.
- Forbidden: squash merge.
- Forbidden: interactive rebase for cleanup after push unless user asks.

## Module size rule

When editing a module near 600 lines:

- Prefer extracting a deep module with a small interface.
- Move repeated behaviour behind the new module.
- Keep protocol-specific adapters thin.
- Add or update tests at the new module interface.
