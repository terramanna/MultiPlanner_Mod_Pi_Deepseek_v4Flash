# App Type Requirements

Use this file to scale rigor to the app being planned. Security remains required for all
types; scope and ceremony change.

## Enterprise SaaS

Add:
- tenant isolation
- RBAC/ABAC
- audit logs
- admin actions and impersonation policy
- data retention and deletion
- SSO/OAuth/SAML boundaries if relevant
- migrations with rollback strategy
- observability: logs, metrics, traces, health checks
- compliance hooks: export, legal hold, data residency where relevant
- rate limiting and abuse controls
- incident response and feature kill switches

Parallelization guidance:
- Contract lane first: auth model, tenancy model, DB migration contract, API schemas.
- Independent lanes by bounded context: billing, users, reports, integrations, dashboard.
- Security reviewer lane should inspect all contract and auth changes before merge.

## Local Single-User App

Add:
- simple onboarding
- local config and secret storage
- backup/restore
- crash recovery
- clear restart/update path
- no cloud dependency unless explicit
- easy diagnostics export without secrets

Parallelization guidance:
- Split into setup, core workflow, persistence, UI, diagnostics, packaging.
- Keep config formats stable early so lanes do not collide.

## Game

Add:
- deterministic rules/state model
- input handling
- save/load
- asset pipeline
- performance budget
- animation/audio boundaries
- difficulty/progression model
- accessibility controls

Parallelization guidance:
- Contract lane first: game state, event loop, asset manifest, save schema.
- Independent lanes: rules, UI/HUD, assets, audio, levels, persistence, tests.

## Agent Tool Or AI Workflow App

Add:
- protocol fidelity
- prompt/input redaction
- tool permission boundaries
- sandboxing
- token/cost accounting
- request/response provenance
- replay/trace view
- model/provider health
- fail-closed routing
- eval/certification gates

Parallelization guidance:
- Contract lane first: normalized request/response, usage ledger, security policy, adapter interface.
- Independent lanes: provider adapters, client adapters, observability, onboarding, evals, routing policy.

## Data App

Add:
- schema evolution
- data provenance
- validation rules
- import/export contracts
- replayability
- idempotent jobs
- privacy classification
- sampling and aggregation policy

Parallelization guidance:
- Contract lane first: schema, validation, ingestion events, export format.
- Independent lanes: importers, transforms, UI views, analytics jobs, diagnostics.

## Public Consumer App

Add:
- account recovery
- abuse controls
- privacy policy support
- analytics consent
- mobile/responsive UX
- support tooling
- safe defaults

Parallelization guidance:
- Contract lane first: user/account model, privacy boundaries, API errors, design system.
- Independent lanes: onboarding, core use cases, notifications, support, settings.
