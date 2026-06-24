# Output Templates

Use these shapes in final plans, PRDs, or issue briefs.

## Architecture Plan

```markdown
## App Type And Risk

- Type:
- Risk class:
- Security posture:

## Protected Kernel

- Domain types:
- Auth/secrets:
- DB/schema:
- API contracts:
- Events/telemetry:
- Config:
- UI/design system:

## Contracts To Define First

| Contract | Owner | Consumers | Test |
| --- | --- | --- | --- |

## Parallel Work Lanes

| Lane | Can start | Owns | Must not touch | Tests | Flag |
| --- | --- | --- | --- | --- | --- |

## Serial Dependencies

| Dependency | Why serial | How to reduce |
| --- | --- | --- |

## File Ownership

| Path/area | Owner | Shared rules |
| --- | --- | --- |

## Security Baseline

- Secrets:
- Auth boundaries:
- Data not logged:
- Threats:
- Required controls:

## Test Strategy

- Contract tests:
- Unit tests:
- Integration tests:
- Security tests:
- E2E/manual tests:

## Merge Waves

1. Contracts and flags
2. Independent lanes
3. Wiring
4. Integration and telemetry
5. Docs/onboarding
6. Certification/default enablement

## Issues Ready For Agents

1. Title:
   - Scope:
   - Files:
   - Out of scope:
   - Tests:
   - Acceptance:
```

## Issue Brief

```markdown
## Goal

## Scope

## Contracts Consumed

## Files Likely Touched

## Files Not To Touch

## Security Notes

## Tests

## Acceptance Criteria

## Merge Dependencies
```

## Review Checklist

```markdown
- [ ] Security baseline applied
- [ ] Contracts defined before implementation
- [ ] Protected kernel identified
- [ ] No central-file pileup
- [ ] Module size rule stated
- [ ] Feature flags for incomplete work
- [ ] Fake adapters/fixtures available
- [ ] Merge waves explicit
- [ ] Tests assigned per lane
- [ ] App-type requirements included
```
