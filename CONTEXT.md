# Project context

## Purpose

MultiPlanner exists to give telecom planners a local-first, terrain-aware
planning workspace that can fetch only the required height data, run LOS-style
analysis, and display the result in a Cesium scene.

The first release is for individual planners and very small teams. It does not
try to replace full enterprise planning systems. It aims to prove a clean core:

- provider-based 1 m terrain and surface subset access
- repeatable LOS and path-profile analysis
- a Cesium-first planning experience

Out of scope for the first release:

- enterprise workflow orchestration
- full OSS/BSS integration
- broad multi-domain telecom planning coverage beyond the LOS-centric core
- hosted sync, permissions, and shared PostGIS operations

## Ubiquitous language

| Term | Meaning | Do not confuse with |
| --- | --- | --- |
| `site` | A planning point such as a tower, rooftop, mast, or candidate location | A generic address or map click with no planning semantics |
| `link` | A planned path between two sites for LOS, path profile, or transport design | A UI hyperlink |
| `corridor` | A buffered line area around a planned path used to fetch only required terrain/surface data | A network route already accepted as valid |
| `DTM` | Bare-earth terrain model used for ground elevation analysis | A surface model containing trees/buildings |
| `DOM` | Surface model including structures and vegetation used for obstruction-aware analysis | A bare-earth DEM |
| `subset fetch` | Retrieval of only the required tiles or coverage window for the selected geometry | Bulk download of whole-state or whole-country datasets |
| `local-first` | The same product works on a single planner machine before any hosted deployment exists | Desktop-only forever |
| `hosted mode` | A future deployment shape where the same analysis concepts run server-side for multiple planners | A different product with unrelated APIs |

## Core invariants

- The first product value is DTM/DOM fetch plus LOS-style analysis, not general-purpose GIS.
- Geometry-driven subset access is mandatory. The system must not require downloading all of Germany for local analysis.
- Frontend and backend must stay separable so local and hosted deployments can share the same contracts.
- Terrain and surface provider logic must be isolated behind adapters so additional German state providers can be added incrementally.
- The Cesium frontend must remain consumer-facing; heavy geodata and RF logic belong in backend or shared engine code.

## Important boundaries

- Public geodata providers vary by German state and may expose WCS, tile indexes, direct GeoTIFF URLs, or map services.
- The v1 app may depend on public provider availability, but provider-specific assumptions must stay localized.
- Hosted multi-planner mode will eventually introduce PostGIS, shared projects, authz, and audit requirements; v1 should not hard-code against single-user local storage patterns.
- RF-grade LOS logic, terrain fetching, and product UX are separate concerns and should not collapse into one module.

## Decisions

- `docs/adr/0001-local-first-cesium-fastapi.md`
