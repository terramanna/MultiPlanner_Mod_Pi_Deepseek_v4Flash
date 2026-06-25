# Deprecated Skills

Bucket: no longer used.

Before using any deprecated skill, check `.agents/pitfalls.md` for known regressions or cross-contamination tied to that skill.

- [design-an-interface](./design-an-interface/SKILL.md): Generate multiple radically different interface designs for a module using parallel sub-agents. Use when user wants to design an API, explore interface options, compare module shapes, or mentions "design it twice".
- [qa](./qa/SKILL.md): Interactive QA session where user reports bugs or issues conversationally, and the agent files GitHub issues. Explores the codebase in the background for context and domain language. Use when user wants to report bugs, do QA, file issues conversationally, or mentions "QA session".
- [request-refactor-plan](./request-refactor-plan/SKILL.md): Create a detailed refactor plan with tiny commits via user interview, then file it as a GitHub issue. Use when user wants to plan a refactor, create a refactoring RFC, or break a refactor into safe incremental steps.
- [ubiquitous-language](./ubiquitous-language/SKILL.md): Extract a DDD-style ubiquitous language glossary from the current conversation, flagging ambiguities and proposing canonical terms. Saves to UBIQUITOUS_LANGUAGE.md. Use when user wants to define domain terms, build a glossary, harden terminology, create a ubiquitous language, or mentions "domain model" or "DDD".
