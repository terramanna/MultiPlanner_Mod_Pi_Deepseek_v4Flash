# MultiPlanner × NSP_UBT Hybrid Data Extractor — Integration Report

> **Status:** Planning document — no code changes made.
> **Scope:** Study of how to embed MultiPlanner's terrain tile layers and point
> probe inside NSP_UBT's existing Leaflet map, sharing all existing display
> filters, labels, and status coloring, while both tools remain independent.

---

## 1. Executive Summary

MultiPlanner and NSP_UBT Hybrid Data Extractor already share a common data
foundation: both read from `hybrid_inventory.db` (SQLite) and both render a
Leaflet map of microwave sites and links. Their concerns diverge sharply from
that point:

| Concern | MultiPlanner | NSP_UBT |
| --- | --- | --- |
| Primary purpose | Terrain / LOS planning, DEM/DSM download | Multi-source inventory reconciliation |
| Map role | Download area selection, point probe, terrain tiles | Network inventory visualisation, multi-source inspector |
| Data novelty | German state elevation rasters (16 providers) | Cross-DB reconciliation (Ellipse, NSP, UBT, BNetzA, Site Tracker) |
| Backend | FastAPI (uvicorn), stand-alone process | PySide6 in-process, QWebChannel bridge |
| Frontend | Leaflet in browser | Leaflet in QWebEngineView via `map.html` |

**The recommended integration is overlay-based, not tab-swap-based.**

Rather than switching to a separate MultiPlanner map, terrain tile layers
(DGM, DOM, nDSM) are added as toggleable overlays inside NSP_UBT's existing
Leaflet map. A point probe becomes an additional click mode in that same map.
All existing site/link display filters, link status colours, site status
categories, and name labels are inherited automatically — nothing is ported,
nothing is duplicated.

MultiPlanner's web UI remains a standalone tool for download sessions. Its
FastAPI server is the terrain tile and probe backend for NSP_UBT.

---

## 2. System Profiles

### 2.1 NSP_UBT Hybrid Data Extractor

**Entry point:** `main.py launch-app --db-path ./data/db/hybrid_inventory.db`

**Architecture:**

```text
cli.py  →  gui/app.py  →  UnifiedShellWindow (shell.py)
                               ├── Dashboard
                               ├── Map  ← QWebEngineView + QWebChannel
                               │         map.html / map.js (Leaflet 1.9.4)
                               │         map_bridge.py ↔ JS bridge
                               │         feature data: map_features.py (GeoJSON)
                               │         inspector: map_inspector.py
                               │         layers panel: map_layers_panel.py
                               ├── Source Explorer
                               ├── Import Center
                               ├── Compare Studio
                               ├── Query Constructor
                               └── BNetzA Validation
```

**Map data path:**

```text
hybrid_inventory.db
  ellipse_site_current  →  site Point features
  ellipse_link_resolved_current → link LineString features
  site_tracker_current  →  cross-reference flags
  nsp_asset_current     →  NE presence flag
  bnetza_license_current→  license presence flag
  lagerbestand_current  →  warehouse flag
        ↓
  map_features.build_feature_collection()   (cached by mtime/size)
        ↓
  GeoJSON FeatureCollection
        ↓
  QWebChannel bridge → map.js → Leaflet layer
```

**Existing map display capabilities (all inherited for free in the overlay approach):**

- 11 overlay toggles: ellipse_links, ellipse_sites, partner_sites, pop_sites,
  backbone_sites, nsp_nes, site_tracker, lagerbestand, bnetza, rifu_repeaters,
  diff_highlights
- 5 operator views: operations, site_status, license_status, build_status, quality
- Link colouring by: state, status, license_status, mismatch, focus
- Site name labels with zoom threshold
- Link name labels
- Symbol mode (type icons vs. dot)
- Two-stage inspector: Ellipse + NSP + BNetzA + Site Tracker + Lager in one panel
- Dark/light theme via CSS custom properties
- 4 basemaps: OSM, Esri Imagery, Esri Sat+Labels, Google Satellite, Bing Aerial

### 2.2 MultiPlanner

**Entry point:** `uvicorn multiplanner_api.main:app` (tray app wraps this)

**Architecture:**

```text
FastAPI (main.py)
  ├── GET /api/v1/network/geojson         ← network_overlay.py (reads hybrid_inventory.db)
  ├── POST /api/v1/probe/multi            ← point_probe.py (gdallocationinfo on GeoTIFFs)
  ├── POST /api/v1/probe/point            ← single-dataset probe
  ├── GET /api/v1/tiles/{p}/{d}/{z}/{x}/{y}.png  ← raster_tiles.py (XYZ tile server)
  ├── POST /api/v1/subsets/locate         ← subsets.py (find tile URLs for bbox)
  ├── POST /api/v1/subsets/download-stream← downloads.py (SSE progress)
  └── GET  /api/v1/config                 ← config / provider mode / cache root

Web frontend (apps/web/src/)
  ├── leaflet-prototype-shell.js          ← sidebar + map layout
  ├── leaflet-prototype.js                ← main orchestration
  ├── leaflet-network-overlay.js          ← site + link overlay (Primary/Nominal only)
  ├── leaflet-point-probe.js              ← click → /api/v1/probe/multi popup
  ├── leaflet-coverage-overlay.js         ← provider coverage polygons
  └── leaflet-basemaps.js                 ← OSM, Esri, Google, Bing
```

**Tile rendering pipeline (raster_tiles.py):**

```text
XYZ tile request (z/x/y)
  → locate_subsets() → find provider tile URLs covering this mercator tile
  → _download_tile_sources() → download GeoTIFF to cache_root/raster_tile_sources/
  → gdalbuildvrt → gdalwarp (bilinear, 256×256, Web Mercator)
  → gdaldem hillshade (dgm1) or gdal_translate (dom1) or numpy diff (ndsm)
  → PNG written to cache_root/raster_tiles/{provider}/{dataset}/{z}/{x}/{y}.png
  → cache hit on repeat requests (file exists check)
```

**Point probe pipeline (point_probe.py):**

```text
POST /api/v1/probe/multi {lon, lat, provider}
  → probe_point(dgm1) → locate_subsets() → download tile if not cached
                       → gdallocationinfo -wgs84 -valonly → float
  → probe_point(dom1)  → same
  → ndsm_m = max(dom_m - dgm_m, 0.0)
  → return {dgm_m, dom_m, ndsm_m}
```

---

## 3. Revised Integration Architecture: Overlay-Based, Not Tab-Swap

### 3.1 Why overlay-based is correct

The original plan (Phase 1 report) proposed a tab-swap: NSP_UBT hosts
MultiPlanner's entire web UI in a second QWebEngineView. The user's follow-up
questions reveal two constraints that make tab-swap the wrong approach:

1. **Display filter inheritance:** NSP_UBT's map already has 2,474 lines of
   Leaflet JS handling link status colouring, site status categories, name
   labels, operator views, and rule trees. If the terrain view lives in a
   separate HTML page (MultiPlanner's UI), none of this is available there.
   Porting it would mean maintaining two parallel implementations that diverge.

2. **Download destination:** Downloaded GeoTIFF/GRD files must live on the
   filesystem (GDAL tools require file paths). What goes into `hybrid_inventory.db`
   is metadata only. That metadata is what makes terrain data visible inside
   NSP_UBT's inspector, and that only works if terrain is part of the same
   map, not a separate tab.

**The right framing:** terrain tiles are just another layer group in NSP_UBT's
existing map — like adding "satellite imagery" or "BNetzA overlay". The toggle
is a layer visibility checkbox in the existing LayersPanel, not a page switch.

### 3.2 How terrain tiles appear in NSP_UBT's Leaflet map

MultiPlanner's tile endpoint produces standard XYZ PNG tiles:

```text
GET http://localhost:8765/api/v1/tiles/{provider}/{dataset}/{z}/{x}/{y}.png
```

These are consumable by Leaflet's `L.tileLayer()` with no modification. In
NSP_UBT's `map.js`, adding a terrain layer is:

```javascript
// Example — actual URLs pass through map_bridge.py for configuration
const dgmLayer = L.tileLayer(
  'http://localhost:8765/api/v1/tiles/geobasis-nrw/dgm1/{z}/{x}/{y}.png',
  { opacity: 0.6, attribution: 'DGM1 © NRW Geobasis', maxZoom: 18 }
);
const domLayer = L.tileLayer(
  'http://localhost:8765/api/v1/tiles/geobasis-nrw/dom1/{z}/{x}/{y}.png',
  { opacity: 0.6, attribution: 'DOM1 © NRW Geobasis', maxZoom: 18 }
);
const ndsmLayer = L.tileLayer(
  'http://localhost:8765/api/v1/tiles/geobasis-nrw/ndsm/{z}/{x}/{y}.png',
  { opacity: 0.8, attribution: 'nDSM © NRW Geobasis', maxZoom: 18 }
);
```

Because these are HTTP requests to `localhost`, they work directly from within
QWebEngineView with no CORS restriction and no QWebChannel bridge — the browser
fetches tiles independently.

The point probe is similarly a direct `fetch()` from map.js to
`http://localhost:8765/api/v1/probe/multi`. No Python bridge involvement.

### 3.3 What the toggle actually is

```text
NSP_UBT Layers Panel (map_layers_panel.py)
  Existing overlay toggles:
    [✓] Ellipse links      [✓] Ellipse sites
    [✓] NSP elements       [  ] Site Tracker
    ...
  NEW terrain layer group (collapsed by default):
    ▼ Terrain (requires MultiPlanner service)
      Provider: [geobasis-nrw ▼]   ← dropdown, populated from /api/v1/providers
      [  ] DGM (hillshade)
      [  ] DOM (surface)
      [  ] nDSM (vegetation/structures)
      Opacity: [━━━━━━━○━━] 60%
      [⛰ Probe mode]               ← toggles probe click handler
```

Checking "DGM" adds the tile layer. Unchecking removes it. This is the same
pattern as the existing overlay toggles — one checkbox per layer. No page
navigation, no tab switch.

### 3.4 Full architecture diagram

```text
NSP_UBT UnifiedShellWindow
  [Map page — unchanged]
    ┌─ LayersPanel ──┬── QWebEngineView (map.html) ──┬─ InspectorPanel ──┐
    │  Existing 11   │                                │  Existing 5-section│
    │  overlay toggle│   Leaflet map (map.js)         │  inspector         │
    │                │   ─ site/link layers            │  ─ Ellipse         │
    │  NEW: Terrain  │   ─ operator view               │  ─ NSP             │
    │  ─ provider    │   ─ status colouring            │  ─ BNetzA          │
    │  ─ DGM □       │   ─ name labels                 │  ─ Site Tracker    │
    │  ─ DOM □       │   ─ zoom-dependent display      │  ─ Lager           │
    │  ─ nDSM □      │                                │                    │
    │  ─ opacity     │   NEW terrain XYZ tile layers  │  NEW: Terrain      │
    │  ─ [Probe]     │   (fetched from localhost:8765) │  ─ DGM  123.4 m   │
    │                │                                │  ─ DOM  129.1 m   │
    │                │   NEW probe popup on click     │  ─ nDSM   5.7 m   │
    └────────────────┴────────────────────────────────┴───────────────────┘

  [Download tab — NEW, lightweight]
    ┌─────────────────────────────────────────────────────┐
    │ QWebEngineView → http://localhost:8765              │
    │ MultiPlanner's download UI (provider, bbox, GRD)   │
    │ Used only when user wants to download terrain data  │
    └─────────────────────────────────────────────────────┘

  [MultiPlanner standalone — unchanged, fully independent]
    uvicorn + browser — works without NSP_UBT running
```

### 3.5 Why the download UI still needs a separate view

The download workflow in MultiPlanner involves:

- Drawing a rectangle/corridor/circle on the map
- Choosing provider and dataset
- SSE streaming progress bar with tile-by-tile updates
- GRD / GeoTIFF export format selection

This is complex interactive UI that doesn't belong in the Layers Panel. The
download tab hosts MultiPlanner's web interface for download sessions only.
Day-to-day map use stays entirely within NSP_UBT's existing map page.

The download tab is rarely visited — it is not the primary integration surface.
The terrain tile overlays in the main map are.

---

## 4. Download Destination: Files + Metadata

### 4.1 What goes where

| Data | Storage | Reason |
| --- | --- | --- |
| Raw GeoTIFF tile (e.g. dgm1_32350_5700_1_nw.tif) | Filesystem: `cache_root/raster_tile_sources/{provider}/{dataset}/` | GDAL tools require filesystem paths; files can be hundreds of MB |
| Rendered tile PNG (256×256, Web Mercator) | Filesystem: `cache_root/raster_tiles/{provider}/{dataset}/{z}/{x}/{y}.png` | Served directly as HTTP response by FastAPI; already cached by MultiPlanner |
| Exported GRD / GeoTIFF + TAB | Filesystem: `cache_root/{job_name}/` (output folder) | User deliverable; opened in Ellipse / mapping software |
| **Download job metadata** | **`hybrid_inventory.db` — new `terrain_cache` table** | Makes terrain data visible in NSP_UBT inspector; queryable |

### 4.2 Proposed `terrain_cache` table

```sql
CREATE TABLE IF NOT EXISTS terrain_cache (
    id              INTEGER PRIMARY KEY,
    job_name        TEXT    NOT NULL,
    provider        TEXT    NOT NULL,
    datasets_csv    TEXT    NOT NULL,          -- "dgm1,dom1,ndsm"
    bbox_west       REAL    NOT NULL,
    bbox_south      REAL    NOT NULL,
    bbox_east       REAL    NOT NULL,
    bbox_north      REAL    NOT NULL,
    file_paths_json TEXT    NOT NULL,          -- JSON array of abs paths
    grd_path        TEXT,                      -- NULL until exported
    tab_path        TEXT,
    downloaded_at   TEXT    NOT NULL,          -- ISO-8601
    resolution_m    REAL,                      -- 1.0 for DGM1, 0.2 for DOP20
    notes           TEXT
);
```

MultiPlanner writes a row here after a successful download. NSP_UBT reads it to:

1. Show a "terrain data available" badge on sites within the bbox.
2. Auto-select the provider for the probe endpoint (site is covered by this bbox
   → use this job's provider).
3. Let the inspector's Terrain section load elevation without requiring a fresh
   probe if DGM/DOM values were already probed and cached.

### 4.3 Who writes to `terrain_cache`

MultiPlanner's `downloads.py` (or a new `terrain_log.py`) opens
`hybrid_inventory.db` read-write after a successful download and inserts the
metadata row. This is the only case where MultiPlanner writes to the DB.

Alternative: NSP_UBT watches a MultiPlanner-maintained sidecar JSON file
(`cache_root/download_log.json`) and imports rows on startup / refresh. This
avoids giving MultiPlanner write access to the main DB. Either approach works;
writing directly to the SQLite is simpler.

---

## 5. Display Filter Inheritance: What Works Automatically

Because terrain tiles are added to NSP_UBT's existing Leaflet map as
`L.tileLayer` objects, all of the following are inherited with zero code
changes:

| Existing capability | Works with terrain tiles? |
| --- | --- |
| Link state colouring (Primary blue, Nominal brown, etc.) | Yes — site/link layers are separate from terrain tiles |
| Operator view switching | Yes — only affects site/link GeoJSON layer styles |
| Site status categories | Yes |
| Site name labels | Yes — rendered on the canvas over all layers including tiles |
| Link name labels | Yes |
| Symbol mode (type icons vs dot) | Yes |
| Zoom-level dependent display | Yes — Leaflet minZoom/maxZoom on tile layer controls when tiles appear |
| Dark/light theme | Partial — dark theme CSS applies to controls; tile colours are fixed (hillshade is greyscale) |
| Inspector panel on site/link click | Yes — click bubbles through tile layer to GeoJSON layer handler |
| LayersPanel overlay toggles | Yes — terrain group follows same toggle pattern |
| Basemap switcher | Yes — terrain tiles composite on top of any basemap |

**Nothing to port. Nothing to duplicate.** The terrain layer is visually on top
of (or behind, depending on z-order) the site/link layers. Opacity control
determines how much the terrain texture bleeds through the network overlay.

### 5.1 Recommended z-order

```text
Layer order (bottom to top):
  1. Basemap tile layer (OSM, Esri, etc.)
  2. DGM hillshade tile layer        ← terrain, semi-transparent
  3. DOM / nDSM tile layer           ← terrain, semi-transparent
  4. Link GeoJSON layer              ← network overlay on top
  5. Site GeoJSON layer              ← site markers above links
  6. Label canvas layer              ← site/link names always readable
```

This ensures network data is always legible regardless of terrain opacity.

### 5.2 Name labels

NSP_UBT's labels are rendered on the Leaflet canvas (or as Leaflet `L.tooltip`
objects). They appear above all tile layers automatically. No changes needed for
labels to work over terrain.

### 5.3 Site status and link status in the probe popup

The probe mode shows a Leaflet popup with DGM/DOM/nDSM values. This popup is
shown at the clicked position. If the click also hits a site or link feature
(because probe mode and normal click mode could co-exist), there's a choice:

**Option A:** Probe mode suppresses the inspector. Click in probe mode → elevation
popup only. Click outside probe mode → inspector as usual.

**Option B:** Probe popup appends to the inspector. Clicking a site in probe mode
opens the inspector AND shows elevation at the top.

Option A is simpler to implement and less surprising. Option B is more useful
(user sees NSP/BNetzA/Tracker data AND elevation at once). Recommend Option B
for Phase 2.

---

## 6. Point Probe: How the JS Calls the API

From NSP_UBT's `map.js`, the probe is a plain `fetch()` — no QWebChannel
involved:

```javascript
async function probeElevation(lon, lat, provider) {
  const resp = await fetch('http://localhost:8765/api/v1/probe/multi', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lon, lat, provider }),
  });
  if (!resp.ok) return null;
  const data = await resp.json();
  // data = { dgm_m: 123.4, dom_m: 129.1, ndsm_m: 5.7, dgm_error: null, ... }
  return data;
}
```

The first probe for a given location triggers a tile download (if not cached)
which may take 5–30 seconds. Subsequent probes at nearby coordinates are
instant (cache hit). NSP_UBT's map.js should show a spinner during the wait.

**Fallback when MultiPlanner is not running:** `fetch()` rejects with a network
error. NSP_UBT catches this and shows "Terrain service unavailable" in the
probe popup. The rest of the map is completely unaffected.

### 6.1 Provider selection for probe

The probe requires a `provider` argument. Options:

**A) User selects provider in the Layers Panel** — same dropdown used to
configure which tile layers are shown. One selection covers both tile display
and probe. Simplest.

**B) Auto-detect from `terrain_cache`** — NSP_UBT queries `terrain_cache` to
find which provider's bbox covers the clicked coordinate. Falls back to "auto"
(let MultiPlanner pick). Works transparently once downloads have been made.

**C) Always use "auto"** — MultiPlanner's `locate_subsets` with `provider=auto`
splits the request by state and picks the correct provider. Slightly slower
but zero configuration. Good default.

Recommend: default to "auto", expose override in the Layers Panel for power users.

---

## 7. Inspector: Terrain Section

A new "Terrain" section in NSP_UBT's `map_inspector.py` shows elevation values
when a site is selected. This is a Phase 2 enhancement.

```text
Inspector (site selected: "WZO-MW-001")
  ── Ellipse  [4 links]
  ── NSP  [2 NEs]
  ── BNetzA  [3 licenses]
  ── Site Tracker  [1 project]
  ── Lager  [no rows]
  ── Terrain  ← NEW
       DGM    123.4 m   (ground elevation)
       DOM    129.1 m   (surface elevation)
       nDSM     5.7 m   (structure height)
       [⟳ Refresh probe]
```

The values are fetched from `POST /api/v1/probe/multi` using the site's
`latitude` / `longitude` from the GeoJSON feature properties. The Python side
of the bridge calls the endpoint:

```python
import httpx

def _fetch_terrain_for_site(lat: float, lon: float, api_url: str) -> dict | None:
    try:
        r = httpx.post(f"{api_url}/api/v1/probe/multi",
                       json={"lat": lat, "lon": lon, "provider": "auto"},
                       timeout=60.0)
        return r.json() if r.is_success else None
    except httpx.RequestError:
        return None
```

This call is made lazily when the Terrain section is expanded, not on every
site click. The result is cached per site per session (dict keyed by site_name).

---

## 8. Changes Required

### 8.1 NSP_UBT changes (all additive)

| File | Change |
| --- | --- |
| `gui/map_layers_panel.py` | Add "Terrain" collapsible group: provider dropdown, DGM/DOM/nDSM checkboxes, opacity slider, probe mode button |
| `gui/map_bridge.py` | Add `terrain_api_url()` method returning configured URL; add `terrain_config_changed` signal; add `is_terrain_available()` (calls /healthz) |
| `gui/_map_assets/map.js` | Add `initTerrainLayers(config)` function; add probe mode click handler; manage tile layer lifecycle on checkbox change; show probe popup |
| `gui/map_inspector.py` | Add "Terrain" section card; lazy-load elevation values on expand |
| `gui/map_style.py` | Add `terrain_provider`, `terrain_layers_visible`, `terrain_opacity` fields to MapStyle dataclass |
| `gui/_settings.py` | Add `terrain/api_url` key (default `http://localhost:8765`) |
| `gui/terrain_download_page.py` | New ~60-line page that hosts MultiPlanner's web UI (for download sessions only) |
| `gui/shell_navigation.py` | Register `terrain_download` page (rarely used; not in main nav) |
| `_schema_terrain.py` | New schema module: `terrain_cache` table definition |
| `schema_sql.py` | Import and include terrain schema |

**No changes to:** `map_page.py`, `map_features.py`, `map_site_features.py`,
`map_inspector_queries.py`, `map_feature_context.py`, `map_status.py`, or any
other existing map module.

### 8.2 MultiPlanner changes (all additive)

| File | Change |
| --- | --- |
| `downloads.py` | After successful download, write metadata row to `terrain_cache` table in `hybrid_inventory.db` (requires `MULTIPLANNER_NETWORK_DB_PATH` to be set) |
| `config.py` | No change needed — `MULTIPLANNER_NETWORK_DB_PATH` already exposed |
| `main.py` | No change needed |
| `network_overlay.py` | No change needed |
| `raster_tiles.py` | No change needed — tile URL format is already correct |
| `point_probe.py` | No change needed — probe API already works with `provider=auto` |

**MultiPlanner requires zero code changes to serve terrain tiles to NSP_UBT's
Leaflet map.** The tile and probe endpoints exist and work today. NSP_UBT just
needs to point Leaflet at them.

---

## 9. Cross-app UX Flows

### Flow 1: Toggling terrain on the network map (core use case)

```text
User in NSP_UBT Map page
  → Layers panel → expand "Terrain" section
  → Select provider "geobasis-nrw"
  → Check "DGM (hillshade)"
  → Hillshade tiles appear under the site/link network
  → Site names, link colours, operator view — all unchanged
  → Toggle off: layers removed, map returns to network-only view
```

### Flow 2: Point probe on a site

```text
User in NSP_UBT Map page with terrain visible
  → Click "Probe mode" button in Terrain section
  → Cursor changes to crosshair
  → Click on a tower site
  → Popup: "WZO-MW-001  DGM 123.4 m  DOM 129.1 m  nDSM 5.7 m"
  → [Phase 2] Probe data also appears in inspector Terrain section
  → Click "Probe mode" again to deactivate
```

### Flow 3: Download terrain data for a corridor

```text
User in NSP_UBT
  → File menu / toolbar → "Terrain Download" (opens download panel)
  → QWebEngineView loads http://localhost:8765 (MultiPlanner download UI)
  → User draws corridor between two sites, selects DGM+DOM, downloads
  → Download completes → metadata written to terrain_cache table
  → User returns to Map page → probe results load faster (tiles cached)
```

### Flow 4: Standalone MultiPlanner use

```text
User opens MultiPlanner tray app directly (without NSP_UBT)
  Works exactly as today
  Network overlay shows Primary/Nominal sites/links (if MULTIPLANNER_NETWORK_DB_PATH set)
  Download, probe, and tile rendering all function independently
```

### Flow 5: NSP_UBT without MultiPlanner installed

```text
User opens NSP_UBT on a machine without MultiPlanner
  Map page loads normally — all site/link layers, filters, inspector work
  Terrain section in Layers Panel is present but shows:
    "Terrain service not available (localhost:8765 unreachable)"
  Inspector Terrain section shows: "—" for all values
  No crash, no error dialogs, no missing functionality in existing features
```

---

## 10. What Stays Independent

| Guarantee | How enforced |
| --- | --- |
| NSP_UBT works without MultiPlanner | Terrain fetch errors are caught; existing map is unaffected |
| MultiPlanner works without NSP_UBT | No import dependency; just optional env var for network overlay |
| No DB write conflicts | MultiPlanner writes only to `terrain_cache` table; NSP_UBT reads it but doesn't write it via the terrain path |
| No shared Python modules | Each app is a separate virtualenv/package |
| No shared port | NSP_UBT's Python never listens on 8765; it only calls it |
| Independent release cycles | Separate repos, separate changelogs, no version coupling |
| Tile display is optional | Terrain layers are off by default; user opts in |

---

## 11. Implementation Phases

### Phase 0 — Smoke test (no code, ~30 min)

1. Start MultiPlanner API server: `uvicorn multiplanner_api.main:app --port 8765`
2. Open `hybrid_inventory.db` in a test NSP_UBT session.
3. Open `http://localhost:8765/api/v1/tiles/geobasis-nrw/dgm1/12/2176/1340.png`
   in a browser while NSP_UBT is running — confirm tile renders and DB is not locked.
4. Confirm `POST /api/v1/probe/multi` returns values for a known coordinate.

### Phase 1 — Terrain tile overlay in NSP_UBT map (~2 days)

1. Add "Terrain" group to `map_layers_panel.py` (provider select, 3 checkboxes, opacity slider).
2. Extend `map_style.py` dataclass with terrain fields.
3. Add `initTerrainLayers(config)` to `map.js` — creates/destroys `L.tileLayer` on toggle.
4. Add `terrain/api_url` QSettings key.
5. Add `/healthz` check to `map_bridge.py`; disable terrain controls if unreachable.

*Result: DGM/DOM/nDSM tiles visible in NSP_UBT's map, under the network overlay,
with all existing filters and labels working.*

### Phase 2 — Point probe in the map (~1 day)

1. Add probe mode button to Layers Panel terrain group.
2. Add probe click handler to `map.js` (fetch → popup with DGM/DOM/nDSM).
3. Add Terrain section to `map_inspector.py` (lazy-load on expand via `httpx` call in bridge).
4. Add `_schema_terrain.py` with `terrain_cache` table.
5. Wire `terrain_cache` write into MultiPlanner's `downloads.py`.

*Result: Click anywhere → elevation values in a popup; site click → elevation
in inspector alongside NSP/BNetzA data.*

### Phase 3 — Download panel and terrain coverage badge (~1 day)

1. Add `terrain_download_page.py` (QWebEngineView → localhost:8765).
2. Register in `shell_navigation.py` as a non-primary page (accessible from
   toolbar button, not main nav).
3. Query `terrain_cache` to show coverage badge on sites within downloaded bboxes.
4. Auto-select provider for probe from coverage match.

### Phase 4 — Optional polish

- Opacity slider per layer (DGM, DOM, nDSM independently).
- Viewport hand-off: when opening download panel, pass current map centre/zoom
  as URL params so MultiPlanner opens at the same view.
- Dark theme injection: pass `?theme=dark` to download panel when NSP_UBT is
  in dark mode; MultiPlanner CSS responds to it.

---

## 12. Files to Read Before Implementation

### NSP_UBT side

| File | Why |
| --- | --- |
| `gui/map_layers_panel.py` | Existing toggle pattern to follow for terrain group |
| `gui/map_style.py` | MapStyle dataclass — add terrain fields here |
| `gui/_map_assets/map.js` | Tile layer API and existing layer management patterns |
| `gui/map_bridge.py` | QWebChannel bridge — add `terrain_api_url` and healthz check |
| `gui/map_inspector.py` | Two-stage inspector — add Terrain section card |
| `gui/webengine_runtime.py` | QWebEngine setup — needed for download panel too |
| `schema_sql.py` | Schema assembly — add terrain schema import |

### MultiPlanner side

| File | Why |
| --- | --- |
| `apps/api/src/multiplanner_api/raster_tiles.py` | Tile URL format, cache paths |
| `apps/api/src/multiplanner_api/point_probe.py` | Probe request/response shape |
| `apps/api/src/multiplanner_api/downloads.py` | Where to add `terrain_cache` write |
| `apps/api/src/multiplanner_api/config.py` | `MULTIPLANNER_NETWORK_DB_PATH` env var |

---

## 13. Risks and Open Questions

### Risk: First probe is slow (tile download on demand)

First probe for an uncached coordinate downloads the source tile (may take
10–60s on a slow network). NSP_UBT's probe popup should show a "loading…"
state. Pre-downloading tiles for relevant areas via the Download panel (Phase 3)
mitigates this for known coverage areas.

### Risk: MultiPlanner not on the same machine

In a multi-machine deployment, MultiPlanner might run on a different host. The
`terrain/api_url` QSettings key allows configuring a non-localhost URL. Tile
layer and probe URLs both use this base URL. No code change needed — just
configuration.

### Risk: Tile provider selection mismatch

`raster_tiles.py` currently validates against `geobasis-nrw` only
(`_validate_request` raises `ValueError` for any other provider). The tile
overlay in NSP_UBT must respect which providers are actually available. The
Layers Panel should populate its provider dropdown from
`GET /api/v1/providers` (already implemented in MultiPlanner's `main.py`)
and only enable tile layers for providers that support the selected dataset.

### Open question: Who manages the MultiPlanner process lifecycle?

The current recommendation is that MultiPlanner runs independently (tray app
or manually started). NSP_UBT calls it but does not manage its process.

If the user wants NSP_UBT to auto-start MultiPlanner:

- NSP_UBT checks `/healthz` on startup.
- If unreachable and a MultiPlanner executable/script path is configured, spawn it.
- On NSP_UBT close, terminate it only if NSP_UBT spawned it.

This is optional — most deployments will have MultiPlanner's tray app running
already. The terrain overlay just silently stays disabled until the service
is up.

### Open question: `terrain_cache` in `hybrid_inventory.db` or a sidecar?

Writing to `hybrid_inventory.db` from MultiPlanner gives NSP_UBT instant
read access with no sync step. But it means MultiPlanner must open the DB
read-write (not the current read-only mode). A sidecar
(`cache_root/terrain_cache.db`) avoids this — MultiPlanner writes to its own
DB, NSP_UBT reads it as an ATTACH'd database or via a separate connection.

Recommend the sidecar approach: MultiPlanner creates and owns
`terrain_cache.db`; NSP_UBT opens it read-only as `ATTACH DATABASE ? AS terrain`.
No change to MultiPlanner's existing read-only posture toward the main DB.

---

## 14. Summary

| Integration surface | Approach | Code change |
| --- | --- | --- |
| Terrain tiles in NSP_UBT map | `L.tileLayer` pointing at localhost:8765 | NSP_UBT map.js + layers panel |
| Point probe | `fetch()` from map.js to probe/multi endpoint | NSP_UBT map.js |
| Site inspector elevation | httpx call in map_bridge.py on section expand | NSP_UBT inspector |
| Download workflow | QWebEngineView → localhost:8765 (rarely opened) | NSP_UBT new page (~60 lines) |
| Download metadata | `terrain_cache.db` sidecar written by MultiPlanner | MultiPlanner downloads.py |
| Display filters, labels, status colours | Inherited automatically | Zero |
| Provider selection | Populated from `/api/v1/providers` at runtime | NSP_UBT layers panel |
| Process lifecycle | MultiPlanner runs independently; NSP_UBT calls it | Zero |

**The entire integration surface is approximately 300 lines of new code across
NSP_UBT (layers panel group + map.js tile/probe handlers + inspector section)
and 30 lines in MultiPlanner (terrain_cache.db write after download). No
existing file in NSP_UBT's map stack is modified.**
