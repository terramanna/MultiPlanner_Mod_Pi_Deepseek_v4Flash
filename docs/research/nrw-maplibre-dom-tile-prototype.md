# NRW MapLibre DOM Tile Prototype

## Purpose

This prototype adds a MapLibre view for checking how NRW `DOM1` behaves in the frontend:

- what the map visually returns
- whether the fetch path feels fast or slow while panning and zooming
- whether the existing local raster tile seam is good enough for UI use

## Important caveat

This is **not** a direct NRW WCS client.

The MapLibre prototype uses the existing backend tile endpoint:

- `/api/v1/tiles/geobasis-nrw/dom1/{z}/{x}/{y}.png`

That endpoint currently:

1. locates matching NRW `DOM1` source tiles
2. downloads and expands source TIFFs into cache when needed
3. warps them into the requested Web Mercator tile
4. renders a `256 x 256` grayscale PNG for the browser

So the prototype is measuring the practical frontend experience of the current local-tile architecture, not the performance of NRW WCS itself.

## Related NRW nDOM50 services

NRW also publishes an official `nDOM50` service:

- WMS: `https://www.wms.nrw.de/geobasis/wms_nw_ndom`
- WCS: `https://www.wcs.nrw.de/geobasis/wcs_nw_ndom`

This matters because `nDOM50` is a statewide relative-height product derived from terrain and surface models. It is useful for vegetation/building prominence and land-cover derivation workflows, but it is still **not** a clutter classification layer.

The MapLibre prototype now includes `NRW nDOM50 WMS` as a direct layer option so it can be compared visually against:

- `NRW DOM1 local`
- `NRW DGM1 local`
- `NRW nDSM local`

## NRW source matrix

Use this terminology consistently:

| Product | Meaning | Path in this repo / NRW |
| --- | --- | --- |
| `DOM1 local` | Absolute surface elevation rendered into local PNG map tiles | NRW bulk GeoTIFF `dom1_tiff` plus `/api/v1/tiles/geobasis-nrw/dom1/{z}/{x}/{y}.png` |
| `DOM WCS` | Official NRW DOM coverage service | `https://www.wcs.nrw.de/geobasis/wcs_nw_dom` |
| `nDOM50 WMS` | Official NRW normalized surface model for relative height above terrain | `https://www.wms.nrw.de/geobasis/wms_nw_ndom` |
| `nDOM50 WCS` | Official NRW coverage service for the same relative-height product | `https://www.wcs.nrw.de/geobasis/wcs_nw_ndom` |

This avoids a repeated mistake:

- `dom` is not `ndom`
- `ndom` is not a clutter-classification layer
- the local `DOM1` display path in this repo is currently GeoTIFF-backed, not WCS-backed

## Frontend entry

Use:

- `apps/web/?renderer=maplibre`

Current visible prototype stamp:

- `MapLibre NRW v2026-06-28-r1`

The side panel exposes:

- `NRW DOM1 local` as a direct map-layer choice
- `NRW nDOM50 WMS` as an official NRW relative-height reference
- active layer opacity
- a DOM fetch status block with batch timing and tile counts

## Interpretation

If `NRW DOM1 local` feels too slow, the next question is not "is WCS slow?" but:

- is first-hit TIFF acquisition too expensive?
- is warp/render cost too high?
- do we need pre-generation, better caching, or a different display product?
