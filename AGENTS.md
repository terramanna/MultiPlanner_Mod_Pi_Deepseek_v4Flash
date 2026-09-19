# AGENTS.md

Project-wide instructions for every coding agent.

## Repository identity

- Repository: `terramanna/MultiPlanner_Mod_Pi_Deepseek_v4Flash`
- Canonical remote: `https://github.com/terramanna/MultiPlanner_Mod_Pi_Deepseek_v4Flash.git`
- Upstream repo: `https://github.com/terramanna/MultiPlanner.git`
- Primary branch: `main`
- Issue tracker: GitHub Issues

Keep all work scoped to this repository unless the operator explicitly asks to inspect another checkout.

## Source of truth

- `CONTEXT.md`: domain terms, project boundaries, and business rules.
- `docs/ARCHITECTURE.md`: system shape, module boundaries, and local-vs-hosted evolution.
- `docs/ROADMAP.md`: phased delivery plan and first-build cutline.
- `docs/research/legacy-source-map.md`: map of useful research from the legacy `multi_planner` repository.
- `docs/agents/git-workflow.md`: branch, verification, and merge rules.
- `docs/agents/issue-tracker.md`: issue workflow.
- `docs/agents/domain.md`: how to consume context docs and ADRs.
- `docs/agents/triage-labels.md`: canonical triage vocabulary.
- `docs/COMMIT_AUDIT.md`: actor identities and commit provenance.
- `.agents/skills/`: repo-local skill set shared across coding agents.
- `.agents/pitfalls.md`: append-only log of skill regressions, anti-patterns, and recovery notes.

## Repo-local skills

Use the repo-local skill tree in `.agents/skills/` as the primary shared skill
set for this repository. The imported layout currently includes:

- `engineering/`
- `productivity/`
- `misc/`
- `personal/`
- `in-progress/`
- `deprecated/`

When a repo-local skill and a global/default skill overlap, prefer the
repo-local skill if it is more specific to this repository or workflow.

Before running a skill, check `.agents/pitfalls.md` for known regressions or
cross-contamination notes tied to that skill.

Do not create parallel project skill trees under `.claude/skills/` or
`.codex/skills/`; keep the shared repository skill set in `.agents/skills/`
to avoid drift.

## Engineering rules

- Prefer designs that reduce cognitive load, change amplification, hidden dependencies, and temporal coupling.
- Keep related invariants and behaviour together; add module boundaries only when they hide more complexity than they add.
- Design interfaces around caller needs, not hidden storage or execution details.
- Document contracts, invariants, and rationale rather than narrating code.
- Test public behaviour and isolated edge cases.
- Measure before performance optimisation and hide it behind a stable interface.

## Hard limits

- **Complexity is the primary reviewability gate.** No function may exceed
  cyclomatic complexity 10, enforced for Python by ruff `C901` (`ruff.toml`) and
  for JS by eslint's `complexity` rule (`apps/web/eslint.config.js`). A genuinely
  irreducible function may carry a documented escape hatch — `# noqa: C901` in
  Python, `// eslint-disable-next-line complexity` in JS. This is the metric that
  actually predicts review difficulty; the line caps below are coarse backstops.
- No source file may exceed 600 lines (hard fail).
- No function may exceed 50 lines (hard fail). Functions are measured in *logical*
  lines: blank and comment-only lines are excluded (plus the docstring for
  Python), so documenting a function never pushes it over budget.
- A pre-warning fires across the last 20% of either line budget (480 lines / 40
  function lines). It prints "approaching budget" but does not block, so you can
  split early instead of discovering you are over budget at commit time.
- Enforcement: CI runs `scripts/check_file_size_policy.py --all`, `ruff check .`,
  and (in `apps/web`) `npx eslint .` on every push; ruff and eslint are installed
  inline, not pinned as project dependencies. The size check also runs as a local
  pre-commit hook only after you install it with `scripts/install_git_hooks.ps1`
  (or `.sh`); a fresh clone has no hook until then.
- If a change would exceed a hard limit, split the work before committing instead
  of asking for an exception.

## Commit audit identity

Every commit must follow `docs/COMMIT_AUDIT.md`. Update `config/commit-actors.json` before installing hooks. The supplied hook rejects a missing `Actor:` trailer, an unknown actor, or an actor that does not match the Git author.
