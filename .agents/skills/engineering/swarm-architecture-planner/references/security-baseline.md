# Security Baseline

Apply before splitting work. Increase depth for enterprise, agent tooling, external APIs,
payments, credentials, user files, or public network exposure.

## Threat Model

Capture:
- assets: secrets, user data, payment data, business data, source code, model prompts
- actors: user, admin, service, agent, provider, attacker, compromised dependency
- trust boundaries: browser/server, local/LAN/cloud, plugin/provider, OAuth/API key, DB/filesystem
- abuse cases: credential theft, prompt/data exfiltration, privilege escalation, quota abuse, file overwrite, SSRF, XSS/CSRF, injection, replay

## Required Controls

- Secrets: store in OS keyring or encrypted local store; never in repo, logs, URLs, browser autocomplete, screenshots, or diagnostic bundles.
- Auth: separate local app auth from upstream provider auth. Do not overload one token field for multiple trust domains.
- Authorization: every privileged action needs explicit authorization check, not only UI hiding.
- Input validation: validate at boundary; reject unknown dangerous protocol fields until reviewed.
- Output handling: escape UI output; redact logs and errors.
- Network: default loopback for local tools; public/LAN bind requires explicit opt-in and warning.
- Dependencies: prefer existing dependencies; new deps need purpose, license check, maintenance signal, and attack surface review.
- Persistence: migrations additive where possible; rollback or recovery path for destructive changes.
- Telemetry: no secrets, raw prompts, credentials, hidden reasoning, private files, or auth headers.
- Agent execution: fail closed on missing capability; sandbox tools; do not let agents write arbitrary paths without policy.

## Security Acceptance Criteria

Every plan should say:
- what secrets exist and where they live
- what data may be logged
- what data must never be logged
- what auth boundary protects each API/command
- how least privilege is enforced
- how diagnostic export redacts sensitive values
- how disabled/failed provider states are handled
- how user can recover from bad config

## Review Gates

Block merge when:
- a secret can enter git, DB logs, browser storage, telemetry, or error output
- auth and upstream credentials share ambiguous names or paths
- unauthenticated LAN/public access exists by default
- input schema accepts arbitrary provider/tool fields without review
- tests depend on real credentials for normal CI
- feature cannot be disabled after release
