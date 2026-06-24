# Domain Docs

How engineering skills should consume this repo's domain documentation when
exploring the codebase.

## Before exploring, read these

- `CONTEXT.md` at the repo root, or
- `CONTEXT-MAP.md` at the repo root if it exists, then each relevant
  context-specific `CONTEXT.md`
- `docs/adr/` for decisions that touch the area being changed

If any of these files do not exist, proceed silently. Do not treat their
absence as an immediate defect.

## Vocabulary discipline

Use the terms defined in `CONTEXT.md` when naming concepts in code, docs,
issues, tests, or refactor proposals.

If a needed concept is missing from the glossary, either:

- reconsider whether you are inventing language the project does not use, or
- note the gap for documentation work instead of silently drifting vocabulary

## ADR conflicts

If a proposed change contradicts an existing ADR, surface the conflict
explicitly rather than silently overriding it.
