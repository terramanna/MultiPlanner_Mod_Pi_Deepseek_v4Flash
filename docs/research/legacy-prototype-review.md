# Legacy Prototype Review

This note captures what the legacy `multi_planner` repository already proves,
what should be reused, and what should stay as reference only.

## Summary

The legacy repository is useful as a direction finder, not as a drop-in base.

- the frontend prototype is the strongest asset
- the backend code is mostly scaffold-level
- the domain model draft contains good concepts for later hosted mode
- the first `MultiPlanner` build should extract only the parts that support the
  subset-fetch plus LOS loop

## What Exists In The Legacy Repo

### Frontend

The legacy web app already has a working Vite plus Cesium shell:

- `apps/web/package.json`
- `apps/web/src/main.js`
- `apps/web/src/style.css`

It already demonstrates:

- Cesium viewer bootstrapping
- terrain-backed 3D scene setup
- site A and site B interaction flow
- LOS-oriented UI state
- profile panel concepts
- draggable and detachable planning windows
- early import hooks for wind turbines and raw display layers

This is real prototype value, because it confirms the local Cesium interaction
model is viable for planner workflows.

### Backend

The backend is still minimal:

- `apps/api/src/mw_planner/main.py`
- `apps/api/src/mw_planner/core/config.py`

Current backend value is limited to:

- naming conventions
- basic config structure
- package layout hints

It is not yet an API implementation for subset fetch, LOS, or project storage.

### Data Model Draft

The strongest backend asset is the SQLAlchemy draft in:

- `apps/api/src/mw_planner/db/models_step1.py`

Useful ideas already present there:

- `mw_sites`
- site import batches and rows
- flags and flag history
- LOS jobs and job members
- geometry stored as `POINTZ`

These are better treated as domain input, not code to copy directly into v1.
They assume a more mature PostGIS-backed system than the first local-first
release needs.

## Recommended Reuse Strategy

### Reuse Now

Bring these ideas into `MultiPlanner` first:

- Cesium plus Vite local app structure
- site placement interaction pattern
- two-point LOS workflow
- profile panel concept
- environment-based config approach

### Reuse Later

Bring these over only after the local analysis loop is stable:

- PostGIS-oriented SQLAlchemy models
- import batch tracking tables
- planner flags and audit history
- multi-user job tables

### Reference Only

Do not transplant these wholesale into the first build:

- the large monolithic `main.js`
- the full floating-window UI system
- broad hosted-edition assumptions in the database schema

Those pieces are useful for behavior reference, but they add too much structure
before the terrain subset and LOS core is stable.

## Practical Extraction Plan

For the next implementation wave in `MultiPlanner`:

1. create a clean Vite plus Cesium shell in `apps/web`
2. implement only site placement, link drawing, and result display
3. create a clean FastAPI app in `apps/api`
4. move provider fetch and subset logic behind API endpoints
5. add LOS and profile endpoints against local subsets
6. revisit the legacy database draft only when shared persistence becomes real

## Bottom Line

The legacy repo should influence `MultiPlanner`, but it should not define it.
Its main contribution is proving the planner UX direction and preserving domain
thinking for later phases.
