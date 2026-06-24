# Roadmap

## Phase 0: Foundation

- establish local-first Cesium + FastAPI repo structure
- define provider adapter model
- capture product boundaries and terminology
- document reuse candidates from the legacy repo
- extract only the smallest useful Cesium prototype behaviors from legacy code

## Phase 1: Terrain-aware core

- DTM/DOM/DOP provider adapters for initial German states
- geometry-driven subset lookup: point, bbox, line corridor, polygon
- remote raster access and local caching
- point-to-point LOS
- path profile generation

## Phase 2: Cesium local planner

- Cesium scene shell
- site placement and import
- link drawing and corridor visualization
- LOS and profile result display
- local project persistence

## Phase 3: Small-team local/server hybrid

- API stabilization
- local project database
- basic export/import
- multi-planner-ready domain model

## Phase 4: Hosted edition groundwork

- PostGIS-backed storage
- user/project separation
- shared caches and provider jobs
- authn/authz and audit trail

## Guardrails

- Do not broaden scope before the subset fetch + LOS value loop is working.
- Keep provider logic isolated from Cesium UI.
- Keep hosted concerns out of the first local planner build except where they affect API shape.
