# Web app

This app hosts the Leaflet planner and the experimental Cesium and MapLibre
comparison renderers.

Current scaffold:

- Vite-based local development shell
- Leaflet planning workflow by default
- compact universal search for sites, links, places, postcodes, and coordinates
- incremental search after two characters, with stale-request cancellation
- All search results balanced as five sites followed by five links; Sites,
  Links, and Places filters provide focused results
- corridor, rectangular-area, and single-point planning modes in the side panel
- area drawing controls shown only in area mode
- geometry-aware provider detection with manual-provider override
- blank-map release for search-selected sites and links, including provider reset
- optional Cesium and MapLibre comparison renderers through query parameters
- optional Cesium world terrain mode through env
- click-to-place Site A and Site B
- simple link visualization
- API bootstrap against the local FastAPI backend
- corridor subset preview against the API
- keep selected subset tiles through the API
- Bayern and Schleswig-Holstein Ellipse bundles containing DGM, DOM, building GRC, and tree GRC
- categorized export picker for source-only, MapInfo-intermediate terrain/surface,
  and semantic height bundles

The Northwood GRD + TAB and UTM32N GeoTIFF + TAB choices are MapInfo
intermediates. They still require a final MapInfo conversion/import step before
the terrain or surface can be used in Ellipse; the picker labels this explicitly.

Run locally:

```powershell
npm install
npm run dev
```

The Vite development server proxies `/api` to `http://127.0.0.1:8000`. This
keeps universal search on the frontend origin and avoids a separate browser CORS
hop. Start the FastAPI backend before using search or provider operations.

For a Bayern or Schleswig-Holstein selection, choose the 2 m or 1 m
`DGM + DOM + building/tree heights` profile under **Ellipse building and tree
heights**. The planner automatically requests DGM, DOM, and the provider's LoD2
dataset even if one of those dataset boxes was not selected. Bayern uses the
logical `bdom` LoD2 slot; Schleswig-Holstein uses `lod2` plus the official
Basis-DLM forest and woodland WFS. Other providers remain rejected until their
building and vegetation sources are validated.

Each semantic bundle contains a height-classified building GRC, a
height-classified forest GRC, exact continuous AGL-height MRRs, and `.vse`
tables. Matching Height Definition `.xml` files populate Ellipse's numeric
height column for each GRC class. Ground Type XML files assign `average_ground`
to building classes and `tree_foliage_medium` to forest classes. The 2 m profile is the practical default; the 1 m profile uses roughly
four times as many semantic cells for the same area.

The link-profile popup does not start raster downloads when it opens. Press
**Calculate profile** to preview the required source-tile count and estimated
first-run size. Large profiles require confirmation, then show streamed sample
progress while uncached DGM/DOM tiles download. Later calculations reuse the
local tile and height cache.

Renderer routes:

- Leaflet planner: `/`
- Cesium comparison: `/?renderer=cesium`
- MapLibre comparison: `/?renderer=maplibre`

Optional environment variables:

- `VITE_API_BASE_URL`
- `VITE_CESIUM_ION_TOKEN`
- `VITE_USE_WORLD_TERRAIN=true`

The frontend should remain thin on provider logic and heavy computation.
