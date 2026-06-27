# Codex handoff — MapLibre terrain drape spike

**Worktree**: `H:\VSC_Projects\Coding_Projects\MultiPlanner-maplibre-worktree`
**Branch**: `prototype/maplibre-nrw-slice` (unstaged changes in the worktree — do not commit to main)
**Scope**: prototype only — no backend changes, no new API endpoints, no test additions required

---

## What this adds

Replace the NRW DTM hillshade WMS raster overlay with MapLibre's native GPU terrain,
draping existing base layers (OSM, NRW DOP) over a 3D mesh decoded from standard
elevation tiles. This proves the visual pattern without fetching any GeoTIFF.

The WCS-based local tile layers (`nrw-dgm1-local`, `nrw-dom1-local`) are kept as-is
— they are rendered visualization tiles, not terrain-encoded tiles, and remain valid
overlay options in the layer switcher.

---

## File changes

### 1. `apps/web/src/maplibre-prototype-style.js`

Add a `raster-dem` source using AWS Terrarium tiles (free, no key required).

In `rasterSources()`, add this entry alongside the existing sources:

```js
"terrain-aws": {
  type: "raster-dem",
  tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
  tileSize: 256,
  encoding: "terrarium",
  attribution: "Terrain Tiles, Mapzen/Amazon",
},
```

No layer entry is needed for `terrain-aws` — `raster-dem` sources are consumed by
`map.setTerrain()`, not added as a layer.

The existing `"nrw-dtm"` WMS source and its `hiddenRasterLayer("nrw-dtm")` entry stay
unchanged — it remains available in the base layer switcher as a flat 2D option for
when terrain is off.

---

### 2. `apps/web/src/maplibre-prototype-shell.js`

Add a terrain toggle immediately after the `baseLayerSelect` label+select block, inside
`renderProviderControls()`. Insert this after the closing `</select>` of `baseLayerSelect`:

```js
    <label class="prototype-terrain-toggle">
      <input id="terrainToggle" type="checkbox" />
      3D terrain drape (AWS Terrarium, ~30 m)
    </label>
    <label for="terrainExaggeration">Terrain exaggeration</label>
    <input id="terrainExaggeration" type="range" min="0.5" max="3" step="0.1" value="1.0" style="width:100%" />
```

---

### 3. `apps/web/src/maplibre-prototype.js`

Three additions, all small:

#### A — read the new elements

In `readElements()`, add:

```js
terrainToggle: document.getElementById("terrainToggle"),
terrainExaggeration: document.getElementById("terrainExaggeration"),
```

#### B — bind the events

In `bindEvents()`, add after the `baseLayerSelect` change listener:

```js
elements.terrainToggle.addEventListener("change", updateTerrain);
elements.terrainExaggeration.addEventListener("input", updateTerrain);
```

#### C — add the handler

Add this function alongside `updateBaseLayerVisibility`:

```js
function updateTerrain() {
  if (elements.terrainToggle.checked) {
    map.setTerrain({
      source: "terrain-aws",
      exaggeration: parseFloat(elements.terrainExaggeration.value),
    });
  } else {
    map.setTerrain(null);
  }
}
```

No changes are needed to `updateBaseLayerVisibility` — all existing layers
(`osm`, `nrw-dop`, `nrw-topo`, `nrw-dtm`, `nrw-dgm1-local`, `nrw-dom1-local`)
continue to work as flat 2D overlays when terrain is off, and drape correctly
over the terrain mesh when terrain is on.

---

## Behaviour after the change

| Terrain off | Terrain on |
|---|---|
| All existing layers work as before | OSM or DOP is draped over the GPU terrain mesh |
| `nrw-dtm` WMS shows server-side hillshade | `nrw-dtm` WMS still switchable but redundant (GPU hillshade replaces it visually) |
| `nrw-dgm1-local` / `nrw-dom1-local` show color-rendered DTM/DOM tiles flat | Same tiles draped over terrain |
| No 3D pitch / tilt available | NavigationControl already has `visualizePitch: true`, tilt works immediately |

---

## What this does NOT change

- No backend changes — the WCS fetch path, `/api/v1/tiles/…` endpoints, and LOS
  profile JSON responses are untouched.
- No removal of any existing source, layer, or UI control.
- The `raster-dem` source provides visual terrain only. Its resolution (~30 m
  SRTM/Copernicus) is not suitable for LOS computation — that path stays via the
  WCS API returning 1D JSON profiles.
- No new npm dependency — `maplibre-gl` already ships the terrain renderer.

---

## Verification

After applying the changes, run `npm run dev` in `apps/web` (with the API running
on port 8000). Open `http://127.0.0.1:5185/?renderer=maplibre`.

Check:
1. Terrain toggle checkbox appears below the base layer switcher
2. Checking it enables 3D terrain — pitching the map (right-drag) shows relief
3. Switching the base layer to `nrw-dop` while terrain is on shows the ortho
   draped over the mesh
4. The exaggeration slider updates the terrain without a page reload
5. Unchecking terrain returns to flat 2D — existing layers unchanged
6. Point probe, corridor selection, download flow all unaffected

---

## Commit actor

```
Actor: Claude Appleton
```

Commit message suggestion:
```
feat(maplibre-prototype): add AWS Terrarium terrain drape with toggle
```
