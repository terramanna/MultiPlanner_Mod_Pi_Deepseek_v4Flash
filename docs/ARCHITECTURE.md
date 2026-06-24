# Architecture

## Summary

MultiPlanner is a local-first system with a deployment split that stays stable
as the product evolves:

- `apps/web`: Cesium frontend
- `apps/api`: FastAPI backend
- `src/`: shared Python modules for geodata/provider logic and reusable analysis code

The local edition runs both web and API services on `localhost`. The hosted
edition keeps the same API contracts and moves storage, auth, and collaboration
concerns to shared infrastructure.

## Core modules

### `apps/web`

Responsibilities:

- Cesium viewer bootstrapping
- site, link, corridor, and area selection tools
- layer toggles for terrain, imagery, and analysis outputs
- profile and LOS result presentation
- communication with backend JSON/GeoJSON/raster endpoints

The frontend should not contain provider-specific fetch logic or RF-grade LOS
algorithms.

### `apps/api`

Responsibilities:

- request validation and orchestration
- provider adapter selection
- subset fetch and remote raster access
- LOS, path-profile, and corridor analysis endpoints
- local cache management
- future project/user/workflow APIs

### `src`

Responsibilities:

- provider adapters
- geometry-to-subset resolution
- reusable terrain/surface sampling code
- future analysis primitives that should not depend on FastAPI

## Local-first deployment

### Local planner mode

- frontend served from localhost
- backend served from localhost
- local config and cache
- optional remote reads from public data providers
- no shared project store required

### Hosted team mode

- same web/api boundary
- PostGIS-backed project and geometry storage
- shared users/projects/permissions
- provider fetch and analysis executed centrally

## Initial provider strategy

The product must support provider adapters rather than a single hard-coded data
source. The first implementation will start with Lower Saxony-style remote tile
lookup, then expand toward Saxony and NRW.

Each provider adapter should expose the same conceptual capabilities:

- point subset lookup
- bbox subset lookup
- line corridor subset lookup
- polygon subset lookup
- DTM, DOM, and orthophoto discovery where available

## First technical cutline

The first build should support:

1. import or select two endpoints
2. resolve a corridor subset for DTM/DOM
3. fetch or stream only the needed data
4. run LOS and path-profile analysis
5. visualize results in Cesium

That cutline is deliberately smaller than the legacy product vision. It proves
the terrain-aware planning core before broader telecom workflow expansion.
