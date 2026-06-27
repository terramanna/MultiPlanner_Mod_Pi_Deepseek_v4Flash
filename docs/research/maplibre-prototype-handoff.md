# MapLibre Prototype Handoff

This note folds the temporary MapLibre handoff into the repository so the
prototype state is not trapped in `%TEMP%`.

Reviewed against the live repository state on 2026-06-27.

## Summary

- Current shared checkout: `H:\VSC_Projects\Coding_Projects\MultiPlanner`
- Current shared checkout branch: `fix/prototype-provider-retry`
- Current shared checkout status:
  - modified: `apps/web/src/leaflet-prototype.js`
  - untracked: `docs/agents/codex-provider-handoff.md`
  - untracked: `test.md`
- Isolated worktree: `H:\VSC_Projects\Coding_Projects\MultiPlanner-maplibre-worktree`
- Worktree branch name: `prototype/maplibre-nrw-slice`

## Reviewed Handoff Accuracy

The temporary handoff was materially correct about:

- the intent: compare MapLibre GL JS with the current Leaflet/Cesium approach
- the isolation strategy: use a separate worktree instead of polluting the
  shared checkout
- the prototype scope: NRW-focused, small-slice, 2D renderer spike
- the run URL shape:
  - `http://127.0.0.1:5185/?renderer=maplibre`
  - `http://127.0.0.1:5185/?renderer=maplibre&variant=corridor`
  - `http://127.0.0.1:5185/?renderer=maplibre&variant=area`
  - `http://127.0.0.1:5185/?renderer=maplibre&variant=point`
- the backend URL: `http://127.0.0.1:8000`
- the prototype files present in the worktree

One important correction is required:

- `prototype/maplibre-nrw-slice` is not a clean branch containing only the
  MapLibre spike. The worktree currently holds the MapLibre changes as
  uncommitted modifications and untracked files, while the branch tip itself
  points at unrelated provider work.

That means the temporary handoff is useful for behavior and file inventory, but
it is not sufficient as a merge plan by itself.

## Prototype Delta In The Isolated Worktree

The worktree currently contains these MapLibre-specific changes:

- modified: `apps/web/package.json`
- modified: `apps/web/package-lock.json`
- modified: `apps/web/src/bootstrap.js`
- untracked: `apps/web/src/maplibre-prototype.js`
- untracked: `apps/web/src/maplibre-prototype-shell.js`
- untracked: `apps/web/src/maplibre-prototype-style.js`
- untracked: `apps/web/src/maplibre-prototype.css`

The current shared checkout does not contain any of these changes.

### What The Prototype Does

- adds `?renderer=maplibre` routing in `apps/web/src/bootstrap.js`
- adds `maplibre-gl` to `apps/web/package.json`
- renders a MapLibre-based NRW-only 2D shell
- supports three prototype modes:
  - corridor
  - area
  - point
- reuses `leaflet-subset-request.js`
- reuses shared formatting and geometry helpers from
  `leaflet-prototype-utils.js`
- exposes these base layers:
  - OpenStreetMap raster
  - NRW DOP WMS
  - NRW DTK WMS
  - NRW hillshade WMS

### Current Constraints

- provider scope is hard-coded to `geobasis-nrw`
- coverage geometry is a coarse hard-coded NRW polygon approximation
- drawing/editing is much narrower than the Leaflet prototype
- no MapLibre-specific tests were added to the shared checkout test suite
- the main prototype file is already substantial at about 409 lines, so further
  expansion should split logic instead of growing that file

## Safe Continuation Path

Do not merge `prototype/maplibre-nrw-slice` directly into the shared checkout.

Use this sequence instead:

1. Start from the current target base branch in a fresh worktree.
2. Copy only the MapLibre delta listed above.
3. Reconcile those files against any concurrent `leaflet-prototype.js` or
   provider work first.
4. Commit the spike as its own clean branch.
5. Run frontend verification again before any review.

This is necessary because the current worktree branch history is polluted with
unrelated committed changes and does not isolate the renderer spike cleanly.

## Verification State From The Temporary Handoff

The temporary handoff reported the following commands passed in the isolated
worktree frontend:

```powershell
npm test
npm run build
```

This repository note records that claim, but it does not re-assert it as fresh
verification for 2026-06-27.

## Rework Needed If The Spike Becomes Product Work

- extract renderer-neutral selection and subset-request state
- rename or replace `leaflet-subset-request.js` with renderer-neutral naming
- choose a real MapLibre drawing/editing solution instead of the narrow spike
- replace the approximate NRW overlay with geometry-driven provider coverage
- decide whether MapLibre is an auxiliary 2D view or a long-term supported
  renderer
- add MapLibre-focused tests for routing, geometry conversion, and subset
  request behavior

## Recommendation

Treat the current MapLibre implementation as a renderer spike, not a branch
ready for merge. The immediate next useful step is to restage it onto a clean
branch before any broader architecture work happens.
