# Web app

This app hosts the Cesium-based MultiPlanner frontend.

Current scaffold:

- Vite-based local development shell
- fast local map mode by default
- optional world terrain mode through env
- Cesium viewer bootstrapping
- free-text address/business/city search
- direct coordinate search
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

Optional environment variables:

- `VITE_API_BASE_URL`
- `VITE_CESIUM_ION_TOKEN`
- `VITE_USE_WORLD_TERRAIN=true`

The frontend should remain thin on provider logic and heavy computation.
