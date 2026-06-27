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

## Provider adapters

Each provider adapter lives at `apps/api/src/multiplanner_api/{state}.py` and
exposes a uniform `locate_tiles` / `summarize_tiles` interface. Four adapter
patterns are in use:

| Pattern | States | Notes |
|---------|--------|-------|
| **INSPIRE WCS 2.0.1** | HE, ST, SL, MV | `GetCoverage` per 1 km cell; axis labels vary (e/n vs x/y vs E/N) |
| **Metalink4 index** | NRW, RP | Fetch XML tile manifest; parse (x_km, y_km) → URL; 24 h cache |
| **GeoJSON index** | SH, BB, HH | Fetch tile-index GeoJSON; spatial filter by geometry; cache |
| **DAV / direct download** | SN (GeoSN), BY, BW | Pre-signed DAV or Metalink URL per file; polygon-based selection |
| **Bulk ZIPs** | ST (LoD2), HB (LoD2) | Fixed set of state-wide ZIPs returned regardless of geometry |
| **ATOM index** | SH (dom1), BE, TH | Parse INSPIRE ATOM feed to build tile index |
| **OGC API Features** | HH | BBox query against a features endpoint |

### Current provider inventory (2026-06-27)

| Provider ID | State | Module | Datasets | Adapter type |
|-------------|-------|--------|----------|--------------|
| `lgln-ni` | Niedersachsen | *(ArcGIS FS)* | dgm1, dom1, dop20 | ArcGIS FeatureServer |
| `geobasis-nrw` | Nordrhein-Westfalen | `nrw.py` | dgm1, dom1, lod2 | Metalink4 index |
| `geosn-sn` | Sachsen | `geosn.py` | dgm1, dom1, dop20 | DAV direct download |
| `hvbg-he` | Hessen | `he.py` | dgm1, dom1, dop20 | INSPIRE WCS |
| `lvermgeo-st` | Sachsen-Anhalt | `st.py` | dgm1, dom1, dop20, lod2 | INSPIRE WCS + bulk ZIPs |
| `geobasis-bb` | Brandenburg | `bb.py` | dgm1, bdom, lod2 | WCS / GeoJSON index |
| `lgl-bw` | Baden-Württemberg | `bw.py` | dgm1, dom1, dop20, bdom | Grid ZIP |
| `ldbv-by` | Bayern | `by.py` | dgm1, dom1, dop20, bdom | Metalink |
| `lgv-hh` | Hamburg | `hh.py` | dgm1, bdom, lod2 | OGC API Features |
| `lvermgeo-sh` | Schleswig-Holstein | `sh.py` | dgm1, dom1, dop20, lod2 | GeoJSON index |
| `laiv-mv` | Mecklenburg-Vorpommern | `mv.py` | dgm1, dom1 | INSPIRE WCS |
| `lginf-hb` | Bremen | `hb.py` | dgm1, dom1, lod2 | Bulk ZIPs |
| `gdi-be` | Berlin | `be.py` | dgm1, dom1, bdom | ATOM index |
| `tlbg-th` | Thüringen | `th.py` | dgm, dom, lod2 | ATOM index |
| `lvgl-sl` | Saarland | `sl.py` | dgm1 | INSPIRE WCS |
| `lvermgeo-rp` | Rheinland-Pfalz | `rp.py` | dgm1 | Metalink4 index |

States without a backend adapter yet: **NI** (ArcGIS FS, no custom module).
States with WMS-only coverage (no download backend): **RP** (dop20 WMS only),
**SL** (dop20 WMS; dom1 WMS pending licensing agreement).

### Leaflet UI — DOP20 WMS basemap coverage

17 states now have ortho WMS layers in `leaflet-basemaps.js`:
NRW, BY, TH, BB, HH, HB, NI, BE, SN, MV, HE, SH, ST, BW, RP, SL.
HE additionally exposes DGM1 and DOM1 as toggleable AdV-colour overlays.

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
