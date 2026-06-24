---
name: swarm-architecture-planner
description: Design an application or major feature for implementation by multiple agents in parallel. Use when the user asks for agent swarm planning, maximum parallel development, minimum serial dependencies, contract-first architecture, implementation lanes, file ownership, merge waves, security-first scope, enterprise vs local/game/app differences, or wants a PRD/issues plan shaped for multiple coding agents.
---

# Swarm Architecture Planner

Design for parallel agent execution without hidden coupling. Optimize for: security first,
contract-first boundaries, small modules, clear ownership, additive changes, test seams, and
merge waves that keep main green.

## Core Workflow

1. Establish app type and risk class.
   - If unclear, ask at most 3 sharp questions. If a `grillme` or `/grill-with-docs` skill is available, use it; otherwise run a short grill-me interview yourself.
   - Read `references/app-types.md` for app-type-specific requirements.

2. Define protected shared kernel.
   - Domain types, auth/secrets, DB schema/migrations, public API contracts, event schema, config loader, routing/decision contracts, and shared UI design tokens are protected.
   - Require explicit review for kernel changes. Most agents should work outside it.

3. Write contracts before work lanes.
   - API endpoints, schemas, events, DB migrations, config keys, plugin interfaces, UI component contracts, error taxonomy, and security/redaction rules.
   - Prefer additive contracts until integration is stable.

4. Split work into vertical slices.
   - Each lane should own user-visible behavior plus tests/docs.
   - Avoid layer-only lanes like "backend" or "frontend" unless building a contract foundation.
   - Assign one owner per file or module area.

5. Limit serial dependencies.
   - Identify blockers, shared files, merge order, and branches that must wait.
   - Use feature flags and fake adapters so agents can finish without live keys, network, or another branch.
   - Read `references/parallel-work-plan.md` for output structure.

6. Apply security baseline.
   - Security is non-negotiable. Threat model before task split.
   - Read `references/security-baseline.md` whenever auth, secrets, data, network, payments, user files, enterprise use, agent execution, or external APIs are involved.

7. Enforce engineering conventions.
   - Follow repo style and existing patterns.
   - Target modules under 600 lines. At 600-700 lines, require justification and split plan. Above 700 lines, treat as architecture smell unless generated, declarative schema, or unavoidable framework glue.
   - Public contracts need tests. Shared helpers need focused unit tests. User workflows need integration tests.

8. Produce outputs.
   - Architecture map
   - Protected kernel
   - Contract list
   - Parallel work lanes
   - Serial dependency list
   - File ownership map
   - Security baseline
   - Test strategy
   - Merge-wave plan
   - Issues-ready task breakdown
   - Read `references/output-templates.md` when writing final artifacts.

## Skill Chaining

- Use `to-prd` after architecture is accepted and should become a product spec.
- Use `to-issues` after PRD/scope is accepted and should become agent tickets.
- Use `improve-codebase-architecture` when applying this plan to an existing repo.
- Use `refactor-procedure` when changes alter existing architecture.
- Use `review` before merge waves or when checking agent branches.
- Use `tdd` for high-risk slices or bug-prone core behavior.

## Hard Rules

- Do not let every lane edit one central file.
- Do not hide cross-lane coupling in shared utility modules.
- Do not let incomplete features run by default.
- Do not invent security shortcuts for demo speed.
- Do not log secrets, OAuth tokens, raw credentials, hidden reasoning, or private user data.
- Do not create agent roles or orchestration semantics unless the app owns that domain.
- Do not optimize for maximum agents if merge risk rises faster than delivery speed.
