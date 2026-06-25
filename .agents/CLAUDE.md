# Repo-local Claude instructions

Use `.agents/skills/` as the primary repo-local skill tree for this repository.

Prefer repo-local skills over global/default skills when the local skill is
more specific to the repository workflow or domain.

Before using a repo-local skill, check `.agents/pitfalls.md` for known
regressions, redo notes, and cross-contamination warnings tied to that skill.

Do not create parallel project skill trees under `.claude/skills/` or
`.codex/skills/`; keep the shared repository skill set in `.agents/skills/`
to avoid drift.
