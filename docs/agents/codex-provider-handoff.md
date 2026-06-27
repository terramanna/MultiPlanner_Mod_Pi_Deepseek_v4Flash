# Codex handoff — German provider adapters (south group)

## Context

MultiPlanner is a terrain-tile download tool. It queries state geodata portals,
finds which 1 km tiles intersect a user-drawn geometry, and downloads them for
export. Each German state has a separate adapter module.

**Your assignment:** implement DGM1 adapters for the southern German states,
working north. Suggested order: BY → BW → RP/SL → TH.

**My assignment (Claude Appleton):** MV and city-states (HB, BE), working south.

We merge later. The only file both of us touch is `providers.py`; that will need
a clean 3-way merge — keep your changes isolated to the state entries you add.

---

## Branch strategy

Create one branch per state (or per closely related pair like RP+SL):

```
feat/provider-by
feat/provider-bw
feat/provider-rp-sl
feat/provider-th
```

Base each off `main` once the current `fix/prototype-provider-retry` merges.
Until then, base off `fix/prototype-provider-retry` (HEAD `94642b8`).

Work in a separate git worktree to avoid stepping on Claude.
Always pin the base commit explicitly so the new branch starts from a known
reference point regardless of what is currently checked out:

```powershell
git fetch origin
git worktree add ..\MultiPlanner-by -b feat/provider-by 94642b8
```

`94642b8` is the tip of `fix/prototype-provider-retry` as of this handoff.
If the branch has advanced since then, replace it with the current tip:

```powershell
git rev-parse fix/prototype-provider-retry   # prints the current tip
git worktree add ..\MultiPlanner-by -b feat/provider-by <that hash>
```

Never run `git worktree add` without an explicit base — the implicit form
creates from whatever HEAD happens to be checked out, which may not be
the intended starting point.

---

## Adapter pattern — use sh.py as your model

Every state adapter lives at:
`apps/api/src/multiplanner_api/{state_code}.py`

The module must export exactly four public symbols:

| Symbol | Signature |
|---|---|
| `locate_tiles` | `(dataset, *, config, geometry, geometry_type, timeout) -> list[dict]` |
| `summarize_tiles` | same signature |
| `request_geometry` | `(geometry: str, geometry_type: str) -> shapely geometry` |
| `PROVIDER_ID` | `str` — the registry key, e.g. `"lvermgeo-by"` |

### locate_tiles return shape

```python
[{"tile_id": "by_dgm1_...", "primary_url": "https://...", ...}]
```

### summarize_tiles return shape

```python
[{
    "provider": PROVIDER_ID,
    "dataset": dataset,
    "tile_id": ...,
    "updated": ...,          # date string or None
    "primary_url": ...,
    "source": "https://...", # homepage of the data portal
}]
```

### geometry_type values the API sends

- `"esriGeometryPoint"` — `"lon,lat"` string
- `"esriGeometryEnvelope"` — JSON `{"xmin", "ymin", "xmax", "ymax"}` in WGS84
- `"esriGeometryPolygon"` — JSON `{"rings": [[[lon,lat], ...]]}` in WGS84

Copy `request_geometry` verbatim from `sh.py` and adjust the error string.
Copy `_to_utm32` / `_to_utm33` verbatim — just change the target CRS constant.

---

## Three adapter patterns used so far

### A — WCS 2.0.1 (Hessen, Saxony-Anhalt, Brandenburg)

Best when a state publishes a WCS endpoint. See `he.py` or `st.py`.
Key steps: build a WCS `GetCoverage` request, stream the TIFF response to disk.
CRS is usually EPSG:25832 (UTM32) for western states, EPSG:25833 (UTM33) for eastern.

```python
# Minimal WCS GetCoverage URL pattern
params = {
    "SERVICE": "WCS", "VERSION": "2.0.1", "REQUEST": "GetCoverage",
    "COVERAGEID": coverage_id,
    "SUBSETTINGCRS": f"http://www.opengis.net/def/crs/EPSG/0/{epsg}",
    "SUBSET": [f"x({xmin},{xmax})", f"y({ymin},{ymax})"],
    "FORMAT": "image/tiff",
    "OUTPUTCRS": f"http://www.opengis.net/def/crs/EPSG/0/{epsg}",
}
```

### B — OGC API Features + direct file download (Hamburg)

When the portal has a tile catalog queryable by bbox. See `hh.py`.

### C — GeoJSON index + direct file download (Schleswig-Holstein)

When a full tile catalog GeoJSON is available for download. See `sh.py`.
Cache with a 7-day TTL: `Path(load_settings().cache_root) / "provider_indexes" / "{state}_dgm1.json"`.

---

## providers.py registration

Two edits required per state:

**1. Add import at top of file:**
```python
from multiplanner_api.by import locate_tiles as locate_by_tiles
from multiplanner_api.by import summarize_tiles as summarize_by_tiles
```

**2. Add entry to SERVICE_PROVIDERS dict:**
```python
"lvermgeo-by": {
    "label": "LVermGeo Bayern",
    "adapter": "lvermgeo_by_wcs",   # choose a unique adapter key
    "datasets": {
        "dgm1": {},
    },
},
```

**3. Add dispatch branches in locate_remote_tiles and summarize_remote_tiles:**
```python
if SERVICE_PROVIDERS[provider].get("adapter") == "lvermgeo_by_wcs":
    return locate_by_tiles(dataset, config=_dataset_config(provider, dataset),
                           geometry=geometry, geometry_type=geometry_type, timeout=timeout)
```

---

## Test pattern

File: `apps/api/tests/test_{state}_provider.py`
Model: copy `tests/test_sh_provider.py` and adapt.

Required coverage:
- Provider lists expected datasets only
- `_parse_*` / tile-catalog parsing extracts all fields
- `request_geometry` for point, envelope, polygon, unsupported type
- `locate_tiles` returns matching tile
- `locate_tiles` returns empty list for geometry outside state
- `locate_tiles` raises `ValueError` for oversized area
- `summarize_tiles` has correct provider/dataset fields
- Cache: uses cached file, fetches when missing, refetches stale (for cached-index adapters)
- WCS: mock `requests.get` to return fake TIFF bytes (for WCS adapters)

Target: 12–18 tests per state.

---

## Commit convention

```
git -c user.name="Brian Codex" -c user.email="brian.codex@terramanna.local" commit -m "..."
```

Every commit message must end with two trailers:
```
Actor: Brian Codex
Co-Authored-By: ...
```

The `Actor:` value must match your entry in `config/commit-actors.json`.

---

## Size policy

- Hard cap: 600 lines per file, 50 logical lines per function.
- Warning band: 480 lines / 40 logical lines.
- Run `python scripts/check_file_size_policy.py --all` before committing.
- `downloads.py` (497 lines) and two web files are already in the warning band —
  do not add code to those files; new providers get their own modules.

---

## Research starting points for southern states

### BY (Bayern)
- BayernAtlas WCS: `https://geoservices.bayern.de/ogc/grids/dgm/wcs`
- GetCapabilities: append `?SERVICE=WCS&REQUEST=GetCapabilities`
- Institution: Landesamt für Digitalisierung, Breitband und Vermessung (LDBV)
- CRS: EPSG:25832 (UTM32); tile size likely 1 km x 1 km
- Provider ID: `ldbv-by`

### BW (Baden-Württemberg)
- LGL BW WCS: `https://owsproxy.lgl-bw.de/owsproxy/ows/WCS_LGL-BW_DGM1-50_EPSG25832`
- Institution: Landesamt für Geoinformation und Landentwicklung (LGL BW)
- CRS: EPSG:25832; tile size: 1 km x 1 km (50 cm resolution DGM)
- Provider ID: `lgl-bw`

### RP (Rhineland-Palatinate) + SL (Saarland)
- RP: `https://geodaten.naturschutz.rlp.de/kartendienste_naturschutz/` — check for WCS
- RP institution: LVermGeo RP (`lvermgeo-rp`)
- SL: likely via `https://geoportal.saarland.de` — check ATOM feed or WCS
- Both are small states; one branch is fine

### TH (Thuringia)
- TLVermGeo WCS: `https://www.geoportal-th.de/geoportal/` — check for WCS or ATOM
- The handoff notes mention "Thüringer WCS pattern" as a reference for MV
- CRS: EPSG:25832 (UTM32); institution: TLVermGeo
- Provider ID: `tlvermgeo-th`

---

## Known issues on this branch (do not fix, just be aware)

- Hamburg (`hh.py`): returns `.xyz` ASCII files, not TIFF. The export pipeline
  passes them to `gdalbuildvrt` which may or may not handle XYZ. Untested
  end-to-end. Do not break the pattern; note it needs manual validation.
- GRD export patches: rely on binary header offsets. Also needs manual validation.
- Widget tests (`tests/test_multiplanner_status_widget.py`): 2 pre-existing
  failures unrelated to provider work — ignore them.

---

## Key files

| Path | Purpose |
|---|---|
| `apps/api/src/multiplanner_api/sh.py` | Model adapter (GeoJSON index pattern) |
| `apps/api/src/multiplanner_api/he.py` | Model adapter (WCS pattern) |
| `apps/api/src/multiplanner_api/providers.py` | Registry + dispatch |
| `apps/api/tests/test_sh_provider.py` | Model test file |
| `apps/api/src/multiplanner_api/config.py` | `load_settings()` — gives `cache_root` |
| `scripts/check_file_size_policy.py --all` | Size gate |
| `config/commit-actors.json` | Actor identities |
