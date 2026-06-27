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

### Phase 1 provider status (2026-06-27) — 257 tests

Backend adapters live: NRW, SN, HE, ST, BB, BW, BY, HH, SH, MV, HB, BE, TH, SL, RP (16 states).
DOP20 WMS basemap: NRW, BY, TH, BB, HH, HB, NI, BE, SN, MV, HE, SH, ST, BW, RP, SL (16 states + NI WMS-only).
HE DGM1/DOM1 AdV-colour WMS overlays: live.
SL DOM1 WMS: pending licensing agreement.

Remaining for full-state backend coverage:
- **NI** — ArcGIS FS adapter (no custom module; queries run against LGLN service)
- **SN LoD2** — ATOM feed URL not yet found
- **SN DOP20** — DAV token confirmed; index parsing not yet validated
- **RP DOM1/DOP20** — no backend adapter (WMS only)
- **SL DOM1** — licensing pending; WCS endpoint exists
- **HE LoD2** — shop-only, not automatable

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
