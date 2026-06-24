# Contributing

## Before coding

1. Fill out `CONTEXT.md` for the derived project.
2. Replace placeholder repository metadata in `AGENTS.md` and `.github/ISSUE_TEMPLATE/config.yml`.
3. Configure `config/commit-actors.json`.
4. Install hooks with `scripts/install_git_hooks.ps1` on Windows or `scripts/install_git_hooks.sh` on Linux/macOS.

## Change workflow

1. Create a focused branch from `main`.
2. Keep commits coherent and attributable under `docs/COMMIT_AUDIT.md`.
3. Run relevant checks before review.
4. Merge through a reviewable pull request unless the operator explicitly directs another workflow.

## Quality bar

- Keep changes scoped.
- Add tests for public behavior and edge cases.
- Prefer small files and clear boundaries over incidental complexity.
