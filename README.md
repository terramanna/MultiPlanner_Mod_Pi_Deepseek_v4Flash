# MultiPlanner

MultiPlanner is a local-first telecom planning platform for microwave, cellular,
and wireless network engineers. The v1 product focus is narrow by design:

- fetch only the required 1 m DTM/DOM/orthophoto subsets for an area of interest
- compute LOS and path-profile results against those subsets
- visualize sites, links, terrain context, and analysis results in Cesium

The product is built for an individual planner first, but the architecture keeps
the same core split that a hosted multi-planner edition will need later:

- `apps/web`: Cesium frontend
- `apps/api`: FastAPI backend
- `src/`: shared Python modules that can grow into reusable geodata and RF logic

## Product direction

MultiPlanner is not trying to solve every telecom workflow in the first release.
The first value proposition is:

1. select or import two endpoints, a corridor, or an area
2. fetch only the relevant terrain/surface data
3. run LOS and related terrain-aware analysis locally
4. show the result in a 3D planning workspace

That local-first heartbeat stays valid when the product later grows into a
shared, server-backed planning system with PostGIS and multi-user workflows.

## Repository layout

- `apps/web/`: Cesium application shell and frontend modules
- `apps/api/`: FastAPI service, provider adapters, and analysis endpoints
- `.agents/skills/`: repo-local shared skill set for coding agents
- `assets/`: static product assets
- `config/`: repo and runtime configuration
- `data/`: local cache and development datasets
- `docs/`: architecture, roadmap, ADRs, and legacy research mapping
- `examples/`: sample inputs and outputs
- `src/`: shared Python modules
- `tests/`: repository-level tests

## First build target

The initial build target is:

- local deployment on one planner workstation
- Cesium frontend served from localhost
- FastAPI backend served from localhost
- DTM/DOM/DOP subset access through provider adapters
- point-to-point LOS, path profile, and corridor subset fetch

## Immediate next steps

1. Fill in `CONTEXT.md`.
2. Review `docs/ARCHITECTURE.md` and `docs/ROADMAP.md`.
3. Install git hooks.
4. Review `docs/research/legacy-prototype-review.md`.
5. Start the local scaffolds in `apps/web` and `apps/api`.

## Local setup

Recommended first-time bootstrap from the repo root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .\apps\api pytest httpx
cd .\apps\web
npm install
cd ..\..
```

Or use the helper script:

```powershell
.\scripts\bootstrap_local.ps1
```

VS Code is configured to use `.\.venv` automatically for this workspace.

## Local run

Backend:

```powershell
.\.venv\Scripts\Activate.ps1
cd apps/api
uvicorn multiplanner_api.main:app --reload
```

Frontend:

```powershell
cd apps/web
npm install
npm run dev
```

Default local URLs:

- web: `http://127.0.0.1:5173`
- api: `http://127.0.0.1:8000`

## Current repo state

- The repository currently has no Git remote configured in `.git/config`.
- On this drive, Git also needs a `safe.directory` entry before normal `git status`
  and `git remote` commands will work.

Optional Windows-first Ellipse export setting:

```powershell
$env:MULTIPLANNER_ELLIPSE_GDAL_DIR = "C:\Program Files\InfoVista\Ellipse 9\gdal"
```

Optional geocoder settings:

```powershell
$env:MULTIPLANNER_GEOCODER_URL = "https://nominatim.openstreetmap.org/search"
$env:MULTIPLANNER_GEOCODER_COUNTRYCODES = "de"
$env:MULTIPLANNER_GEOCODER_EMAIL = "you@example.com"
```

## Commit audit

This repo uses the commit actor policy from `docs/COMMIT_AUDIT.md` and the
default identities in `config/commit-actors.json`.
