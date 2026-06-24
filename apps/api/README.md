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
With `export_profile: "ellipse_mapinfo_tab"`, it also attempts a per-dataset
GeoTIFF merge and writes a MapInfo `.TAB` sidecar for Ellipse/MapInfo import.
This requires GDAL tools from the local Ellipse installation.

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
