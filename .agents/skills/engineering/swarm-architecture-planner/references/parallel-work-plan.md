# Parallel Work Plan

Use this to convert architecture into swarm-safe lanes.

## Dependency Classes

- Contract-first: must land before broad parallel work.
- Independent lane: can run now with fake adapters or fixtures.
- Wiring lane: waits for at least one contract and one implementation lane.
- Integration lane: waits for merge wave.
- Certification lane: waits for telemetry/evals/test data.

## Lane Shape

Each lane needs:
- owner area and files likely touched
- contract it consumes
- files it must not touch
- feature flag or config gate
- fake adapter/fixture plan
- tests it owns
- docs it owns
- merge prerequisites
- rollback/disable path

## File Ownership

Use this pattern:

| Area | Owner lane | Shared? | Rules |
| --- | --- | --- | --- |
| Domain types | Contract lane | Yes | Additive only unless reviewed |
| API app/router | Wiring lane | Yes | Route registration only |
| Provider adapter | Provider lane | No | One adapter per lane |
| Dashboard panel | UI lane | No | No router logic |
| DB schema | Contract lane | Yes | Additive migration first |

Avoid:
- many lanes editing `app.py`
- dashboard lanes changing routing internals
- provider lanes changing DB schema
- docs lanes changing code
- "common utils" as dumping ground

## Merge Waves

1. Contracts and flags
2. Independent implementations behind flags
3. Wiring and dashboard/API surface
4. Integration tests and telemetry
5. Docs/onboarding
6. Certification/default enablement

Do not enable by default until wave 4 or later passes.

## Serial Dependency Report

Always list:
- true blockers
- artificial blockers that can be removed by fake adapters or feature flags
- shared-file collision risks
- schema/API migrations that freeze other lanes
- branches that must rebase after a merge wave

## Parallelism Check

A plan is swarm-ready when:
- at least 60 percent of lanes can start after contracts land
- no more than one lane owns each non-shared file
- all shared files have a gatekeeper
- every lane has local tests independent of live services
- every incomplete behavior is behind a flag
