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

Run locally:

```powershell
npm install
npm run dev
```

The Vite development server proxies `/api` to `http://127.0.0.1:8000`. This
keeps universal search on the frontend origin and avoids a separate browser CORS
hop. Start the FastAPI backend before using search or provider operations.

Renderer routes:

- Leaflet planner: `/`
- Cesium comparison: `/?renderer=cesium`
- MapLibre comparison: `/?renderer=maplibre`

Optional environment variables:

- `VITE_API_BASE_URL`
- `VITE_CESIUM_ION_TOKEN`
- `VITE_USE_WORLD_TERRAIN=true`

The frontend should remain thin on provider logic and heavy computation.
