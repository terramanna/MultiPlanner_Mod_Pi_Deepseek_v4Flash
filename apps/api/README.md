# API app

This app hosts the FastAPI backend for MultiPlanner.

Current scaffold:

- FastAPI application entrypoint
- local configuration loading
- CORS setup for the local web app
- `GET /healthz`
- `GET /api/v1/config`
- `GET /api/v1/search/places`
- `GET /api/v1/providers`
- `POST /api/v1/subsets/locate`
- `POST /api/v1/subsets/download`

The current download endpoint saves matching source tiles to the local cache.
With `export_profile: "ellipse_grd"`, it writes DEM layers as Northwood Numeric
Grid `.grd` files plus MapInfo `.TAB` sidecars, and imagery layers as GeoTIFF
`.tif` files plus MapInfo `.TAB` sidecars under `<selection>/utm32_grd/`.
With `export_profile: "ellipse_mapinfo_tab"`, it also attempts a per-dataset
GeoTIFF merge, reprojects it to WGS 84 / UTM zone 32N (`EPSG:32632`), and
writes the GeoTIFF plus MapInfo `.TAB` sidecar to `<selection>/utm32/` for
Ellipse/MapInfo import.
The `ellipse_grd` path uses GDAL's `NWT_GRD` driver for the `DGM1` and `DOM1`
`.grd` outputs. Ellipse rejected the ASCII `.grd` variant in manual import
tests.
The UTM 32N target is intentional for Ellipse compatibility: Ellipse projects
used by this workflow expect one projection, and UTM 33N exports are not loaded
properly even when they would be geographically reasonable.
This requires GDAL tools from the local Ellipse installation.

With `export_profile: "ellipse_semantic_grc"` (2 m) or
`"ellipse_semantic_grc_1m"` (1 m comparison) and provider `ldbv-by`, the
download becomes a Bayern Ellipse bundle. The backend automatically includes
`dgm1`, `dom1`, and `bdom` sources and writes:

- DGM and DOM as WGS 84 / UTM zone 32N GeoTIFF + `.TAB` with pyramids
- separate building and forest GRCs classified by AGL height
- matching continuous Float32 building and tree AGL-height MRRs
- matching `.vse` colour/value tables
- matching Ellipse Height Definition `.xml` tables with numeric metre values

Both classified GRCs use the selected geometry, the selected 1 m or 2 m UTM32N
grid, and No Data outside their own class. Heights are `max(DOM - DGM, 0)` in
metres. Both GRCs use 0.5 m height classes through the observed maximum. The
forest palette interpolates the supplied Ellipse forest table at the added
half-metre steps, while each MRR retains the exact continuous value. A point
selection uses a bounded 1 km work area. Forest class and height-definition
tables always cover at least 0–41 m so an empty or low-canopy selection does
not produce an unusably short reusable table. The
profile currently supports Bayern only; other state providers require their
semantic-source route to be validated before the same option is enabled.

The search endpoint accepts direct coordinates locally and otherwise forwards
free-text place/address search to a configurable Nominatim-compatible geocoder.

Run locally:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
uvicorn multiplanner_api.main:app --reload
```

The backend should keep analysis and provider logic modular so the same core can
support local planner mode and future hosted mode.
